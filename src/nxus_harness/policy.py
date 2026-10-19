"""Décisions déterministes : le LLM ne peut ni accorder ni élargir une permission."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any
from urllib.parse import urlparse
import ipaddress
import socket

from .models import PlanManifest, PolicyDenied, RiskLevel, RunState, TaskContract, TaskProfile

# [AJOUTÉ 18/10/2026] Sous-commandes rea statiques/lecture seule uniquement
# (confirmées via `rea --help` : jamais d'install, de debug interactif, de
# push/flash, ni d'exécution du binaire analysé). Volontairement une
# allowlist courte plutôt qu'une blocklist : toute sous-commande RÉELLE de
# rea absente de cette liste est refusée par défaut, y compris une future
# sous-commande qu'une mise à jour de rea ajouterait.
_REA_SAFE_SUBCOMMANDS = frozenset({
    "analyze", "inspect", "inspect-artifact", "inspect-binary-layout",
    "inspect-android-package", "inspect-android-class", "inspect-android-method",
    "decode-android-resources", "identify-flutter-build",
})


# [AJOUTÉ 18/10/2026] Traçabilité OWASP LLM Top-10 (révision 2025) par règle.
# Trouvé en comparant ce projet à des gateways d'approbation publiques
# (AgentGate, github.com/agentkitai) qui taguent chaque entrée d'audit avec
# le risque OWASP qu'elle mitige. Annotation pure : ne change aucune
# décision, sert uniquement à savoir, en lisant l'audit, QUEL risque de la
# liste OWASP chaque refus/autorisation couvre réellement.
_OWASP_LLM_RISK = {
    "P-KILL-001": "LLM06:2025 Excessive Agency",
    "P-STATE-001": "LLM06:2025 Excessive Agency",
    "P-RISK-001": "LLM06:2025 Excessive Agency",
    "P-PROFILE-001": "LLM06:2025 Excessive Agency",
    "P-CONTRACT-001": "LLM06:2025 Excessive Agency",
    "P-MANIFEST-001": "LLM05:2025 Improper Output Handling",
    "P-PATH-001": "LLM05:2025 Improper Output Handling",
    "P-PATH-002": "LLM05:2025 Improper Output Handling",
    "P-PATH-003": "LLM05:2025 Improper Output Handling",
    "P-URL-001": "LLM05:2025 Improper Output Handling",
    "P-URL-002": "LLM05:2025 Improper Output Handling",
}


@dataclass(frozen=True)
class PolicyDecision:
    outcome: str
    rule_id: str
    reason: str

    @property
    def owasp_llm_risk(self) -> str | None:
        """None pour une autorisation (P-ALLOW-001) : il n'y a pas de risque
        OWASP à annoter quand rien n'a été refusé."""
        return _OWASP_LLM_RISK.get(self.rule_id)


class PolicyEngine:
    VERSION = "mvp-1.0"
    _profile_tools = {
        TaskProfile.QA_READONLY: {"read_fixture", "retrieve_fixture"},
        TaskProfile.DECISION_CHALLENGE: {"read_fixture"},
        TaskProfile.RESEARCH_READONLY: {"read_fixture", "retrieve_fixture"},
        TaskProfile.CODE_CHANGE: {"read_fixture", "retrieve_fixture", "write_workspace_draft", "run_declared_check"},
        TaskProfile.SECURITY_REVIEW: {"read_fixture", "run_declared_check"},
        TaskProfile.EXTERNAL_ACTION: set(),
        # [AJOUTÉ 18/10/2026 — R2] Seul profil avec execute_python/fetch_url.
        # Il reprend aussi les outils R0/R1 (brouillon, vérification) : une
        # tâche d'exécution de code a généralement aussi besoin d'écrire un
        # fichier et de vérifier un résultat déclaré.
        TaskProfile.AGENTIC_EXECUTION: {"read_fixture", "retrieve_fixture", "write_workspace_draft",
                                       "run_declared_check", "execute_python", "fetch_url",
                                       "request_rea_analysis", "rea_inspect", "smokinggun_scan", "jacobian_verify"},
    }

    def __init__(self) -> None:
        self.kill_switch = False

    def stop(self) -> None:
        self.kill_switch = True

    def authorize(self, *, contract: TaskContract, manifest: PlanManifest, state: RunState,
                  tool_id: str, arguments: dict[str, Any], tool_risk: RiskLevel) -> PolicyDecision:
        if self.kill_switch:
            return PolicyDecision("deny", "P-KILL-001", "kill switch actif")
        if state != RunState.EXECUTING:
            return PolicyDecision("deny", "P-STATE-001", "outil interdit hors phase EXECUTING")
        # [AJOUTÉ 18/10/2026 — R2] Plafond relevé de R1 à R2 pour
        # execute_python/fetch_url. contract.max_risk reste le VRAI plafond
        # par tâche : un contrat CODE_CHANGE classique (max_risk=R1) ne peut
        # toujours pas déclencher un outil R2, quel que soit ce plafond MVP.
        if tool_risk > contract.max_risk or tool_risk > RiskLevel.R2:
            return PolicyDecision("deny", "P-RISK-001", "niveau de risque non activé dans le MVP")
        if tool_id not in self._profile_tools[contract.profile]:
            return PolicyDecision("deny", "P-PROFILE-001", "outil absent du profil de tâche")
        if contract.allowed_tools and tool_id not in contract.allowed_tools:
            return PolicyDecision("deny", "P-CONTRACT-001", "outil absent du contrat")
        if not any(operation.tool_id == tool_id and operation.arguments == arguments for operation in manifest.operations):
            return PolicyDecision("deny", "P-MANIFEST-001", "arguments différents du manifeste approuvé")
        if tool_id == "write_workspace_draft":
            raw_path = arguments.get("path", "")
            try:
                normalized = PurePosixPath(raw_path)
            except TypeError:
                return PolicyDecision("deny", "P-PATH-001", "chemin invalide")
            if normalized.is_absolute() or ".." in normalized.parts:
                return PolicyDecision("deny", "P-PATH-002", "chemin sortant du workspace")
            if raw_path not in manifest.allowed_paths or raw_path not in contract.allowed_paths:
                return PolicyDecision("deny", "P-PATH-003", "chemin hors périmètre autorisé")
        if tool_id == "fetch_url":
            # [AJOUTÉ 18/10/2026 — R2] Même logique que write_workspace_draft
            # pour les chemins : allowlist EXACTE (pas de wildcard de
            # domaine), dans le manifeste ET dans le contrat. Garde SSRF
            # minimale : refuse tout hôte non public avant même de vérifier
            # l'allowlist, pour qu'une allowlist mal écrite par erreur
            # (ex. "http://169.254.169.254/...") ne puisse pas quand même
            # passer. Ce n'est pas un remplacement de la checklist complète
            # "Conditions avant un connecteur R2+" de threat-model.md.
            raw_url = arguments.get("url", "")
            try:
                parsed = urlparse(raw_url)
            except ValueError:
                return PolicyDecision("deny", "P-URL-001", "URL invalide")
            if parsed.scheme not in ("http", "https") or not parsed.hostname:
                return PolicyDecision("deny", "P-URL-001", "URL invalide")
            host = parsed.hostname.lower()
            # [AJOUTÉ 18/10/2026 — DNS rebinding, trouvé via security-audit
            # skill (finding "confirmed", run-1) et confirmé par la
            # littérature (ex. arXiv 2605.24309 : les gardes déterministes
            # statiques vieillissent mal face à la surface réelle d'un
            # outil). Le contrôle ci-dessous ne regarde QUE la chaîne du
            # hostname — un domaine autorisé en apparence ("exemple.com")
            # peut résoudre vers 169.254.169.254 ou 127.0.0.1 au moment de
            # l'appel réel (DNS rebinding) et passer ce filtre sans jamais
            # être détecté. On résout donc le hostname ICI, avant le
            # contrôle de chaîne, et on refuse si UNE SEULE des IP résolues
            # est privée/loopback/link-local/réservée — défense en
            # profondeur : la chaîne reste vérifiée plus bas pour les hosts
            # qui ne résolvent pas (ex. déjà une IP littérale).
            try:
                resolved_ips = {info[4][0] for info in socket.getaddrinfo(host, None)}
            except socket.gaierror:
                # Hôte qui ne résout pas : pas exploitable en SSRF (rien à
                # atteindre), et des hôtes volontairement non résolvables
                # (ex. example.invalid, RFC 2606) sont utilisés par les
                # tests pour éviter tout accès réseau réel — laisser
                # _execute gérer l'erreur réseau comme avant, ne pas refuser ici.
                resolved_ips = set()
            for ip in resolved_ips:
                addr = ipaddress.ip_address(ip)
                if addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved or addr.is_multicast:
                    return PolicyDecision("deny", "P-URL-001", f"hôte résolu vers une IP non publique ({ip}) — garde SSRF (DNS rebinding)")
            if (host in ("localhost", "127.0.0.1", "0.0.0.0", "::1")
                    or host.startswith("127.") or host.startswith("10.")
                    or host.startswith("192.168.") or host.startswith("169.254.")
                    or host.startswith("172.16.") or host.startswith("172.17.")
                    or host.startswith("172.18.") or host.startswith("172.19.")
                    or host.startswith("172.2") or host.startswith("172.30.") or host.startswith("172.31.")):
                return PolicyDecision("deny", "P-URL-001", "hôte non public refusé (garde SSRF)")
            if raw_url not in manifest.allowed_urls or raw_url not in contract.allowed_urls:
                return PolicyDecision("deny", "P-URL-002", "URL hors périmètre autorisé")
        if tool_id == "rea_inspect":
            # [AJOUTÉ 18/10/2026 — pont vers la VRAIE CLI rea (morluto/rea)]
            # rea a des dizaines de sous-commandes, certaines destructrices
            # ou interactives (install-adb-package, debug-with-gdb,
            # debug-with-rizin, execute-rizin-command, cutter-command...).
            # Allowlist EXPLICITE des seules sous-commandes statiques/lecture
            # seule (texte exact de leur description `rea --help` : "without
            # executing", "without loading target code", etc.) -- tout le
            # reste est refusé par défaut, y compris une sous-commande réelle
            # de rea qui n'est juste pas sur cette liste.
            subcommand = arguments.get("subcommand", "")
            if subcommand not in _REA_SAFE_SUBCOMMANDS:
                return PolicyDecision("deny", "P-REA-001", f"sous-commande rea non autorisée (lecture seule uniquement) : {subcommand!r}")
            target = arguments.get("target", "")
            if target not in manifest.allowed_paths or target not in contract.allowed_paths:
                return PolicyDecision("deny", "P-REA-002", "cible rea hors périmètre autorisé")
        if tool_id == "smokinggun_scan":
            target = arguments.get("target", "")
            if target not in manifest.allowed_paths or target not in contract.allowed_paths:
                return PolicyDecision("deny", "P-SCAN-001", "cible smokinggun hors périmètre autorisé")
        return PolicyDecision("allow", "P-ALLOW-001", "opération conforme au contrat et au manifeste")

    @staticmethod
    def require(decision: PolicyDecision) -> None:
        if decision.outcome != "allow":
            raise PolicyDenied(f"{decision.rule_id}: {decision.reason}")

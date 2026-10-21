"""Décisions déterministes : le LLM ne peut ni accorder ni élargir une permission."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any
from urllib.parse import urlparse
import threading
import ipaddress
import socket

from .models import (PlanManifest, PolicyDenied, RiskLevel, RunState, TaskContract, TaskProfile, ValidationError,
                     is_drive_absolute_path)

# [AJOUTÉ 18/10/2026] Sous-commandes rea statiques/lecture seule uniquement
# (confirmées via `rea --help` : jamais d'install, de debug interactif, de
# push/flash, ni d'exécution du binaire analysé). Volontairement une
# allowlist courte plutôt qu'une blocklist : toute sous-commande RÉELLE de
# rea absente de cette liste est refusée par défaut, y compris une future
# sous-commande qu'une mise à jour de rea ajouterait.
def resolve_public_ips(host: str) -> set[str]:
    """[AJOUTÉ 19/10/2026 — extrait depuis authorize() pour que tools.py
    puisse réutiliser EXACTEMENT la même logique de validation au moment
    de la vraie connexion (voir fetch_url dans tools.py) -- une fonction
    séparée qui ne ferait QUE revalider sans que la connexion soit forcée
    vers l'adresse validée laisserait un TOCTOU : urllib résout à nouveau
    au moment de connecter, et rien ne garantit que c'est la même adresse.
    Lève ValidationError si une IP résolue n'est pas publique ; renvoie
    l'ensemble des IP publiques résolues (vide si l'hôte ne résout pas)."""
    try:
        resolved_ips = {info[4][0] for info in socket.getaddrinfo(host, None)}
    except socket.gaierror:
        return set()
    for ip in resolved_ips:
        addr = ipaddress.ip_address(ip)
        if addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved or addr.is_multicast:
            raise ValidationError(f"hôte résolu vers une IP non publique ({ip}) — garde SSRF (DNS rebinding)")
    return resolved_ips


# [AJOUTÉ 19/10/2026 — défense en profondeur signalée par un audit externe]
# rea_inspect/smokinggun_scan passent par shell=True sur Windows (wrapper
# npm .CMD, voir tools.py). target doit déjà correspondre EXACTEMENT à une
# entrée allowed_paths pré-approuvée par l'opérateur -- jamais un texte
# libre du modèle -- ce qui limite déjà fortement la surface. Cette liste
# refuse en plus les caractères que l'invite de commandes Windows (cmd.exe)
# interprète spécialement, au cas où un chemin autorisé en contiendrait
# par erreur ou qu'une future évolution assouplisse la contrainte exacte.
_SHELL_METACHARACTERS = frozenset('&|%^"<>()')


def _has_shell_metacharacters(value: str) -> bool:
    return any(char in _SHELL_METACHARACTERS for char in value)


# [AJOUTE 20/10/2026 -- angle mort trouve par un agent : rea_inspect
# (P-REA-001/002/003) et smokinggun_scan (P-SCAN-001/002) ont chacun une
# validation dediee dans authorize() ; jacobian_verify n'en avait AUCUNE --
# operation_id/args_json tombaient directement sur la regle generique
# P-ALLOW-001, poussant TOUTE la frontiere de securite sur l'analyseur
# d'arguments du binaire externe jacobian (tools.py le justifie par
# "fonctions mathematiques pures, pas des commandes shell", mais rien ne
# garantit qu'un futur jacobian n'ajoute jamais une option exploitable via
# ce point d'entree). Aucun exploit reel trouve contre le CLI jacobian
# installe (Click bloque les formes testees), mais le gain est gratuit et
# sans impact sur l'usage legitime : un operation_id reel (ex.
# "abelian_group.element.equal.decide") ne commence jamais par "-" et ne
# contient jamais de metacaractere shell -- meme filet de securite que les
# deux autres outils, en ceinture-et-bretelles plutot qu'en reaction a un
# exploit prouve.
def _looks_like_cli_flag_injection(value: str) -> bool:
    return value.startswith("-") or _has_shell_metacharacters(value)


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
    "P-SCREEN-001": "LLM05:2025 Improper Output Handling",
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
    # [CORRIGÉ 19/10/2026 — biais de conception trouvé en relecture : chaque
    # nouvel outil R0/R1 ajouté cette session (jacobian_verify,
    # smokinggun_scan, rea_inspect) n'a été câblé que sur AGENTIC_EXECUTION
    # (le profil utilisé pour les tester), jamais sur les profils dont le
    # niveau de risque leur correspond réellement -- violation du moindre
    # privilège : une tâche QA_READONLY/RESEARCH_READONLY qui veut juste
    # vérifier un calcul (jacobian_verify, R0, zéro effet de bord prouvé)
    # devait escalader vers AGENTIC_EXECUTION, qui débloque AUSSI
    # execute_python/fetch_url (R2) -- bien plus que nécessaire. jacobian_verify
    # et smokinggun_scan (tous deux R0, sans accès fichier/réseau/exécution
    # arbitraire, vérifiés en conditions réelles) sont maintenant disponibles
    # partout où un outil R0 de lecture l'est déjà ; smokinggun_scan rejoint
    # aussi SECURITY_REVIEW, dont c'est exactement l'usage prévu.
    _profile_tools = {
        TaskProfile.QA_READONLY: {"read_fixture", "retrieve_fixture", "jacobian_verify"},
        TaskProfile.DECISION_CHALLENGE: {"read_fixture", "jacobian_verify"},
        TaskProfile.RESEARCH_READONLY: {"read_fixture", "retrieve_fixture", "jacobian_verify", "smokinggun_scan"},
        TaskProfile.CODE_CHANGE: {"read_fixture", "retrieve_fixture", "write_workspace_draft", "run_declared_check",
                                  "jacobian_verify", "smokinggun_scan"},
        TaskProfile.SECURITY_REVIEW: {"read_fixture", "run_declared_check", "smokinggun_scan"},
        TaskProfile.EXTERNAL_ACTION: set(),
        # [AJOUTÉ 18/10/2026 — R2] Seul profil avec execute_python/fetch_url.
        # Il reprend aussi les outils R0/R1 (brouillon, vérification) : une
        # tâche d'exécution de code a généralement aussi besoin d'écrire un
        # fichier et de vérifier un résultat déclaré.
        TaskProfile.AGENTIC_EXECUTION: {"read_fixture", "retrieve_fixture", "write_workspace_draft",
                                       "run_declared_check", "execute_python", "fetch_url",
                                       "request_rea_analysis", "rea_inspect", "smokinggun_scan", "jacobian_verify",
                                       "capture_screen"},
    }

    def __init__(self) -> None:
        self.kill_switch = False
        # [AJOUTÉ 19/10/2026 — faille réelle signalée par un audit externe]
        # kill_switch (bool) n'était consulté QUE lors de l'autorisation de
        # la PROCHAINE opération -- un sous-processus déjà lancé (execute_python,
        # rea_inspect, smokinggun_scan, jacobian_verify) continuait jusqu'à son
        # propre timeout, sans aucun moyen pour stop() de l'atteindre.
        # threading.Event (pas juste un bool) : observable depuis un thread
        # séparé (ex. un watchdog dans _run_capped qui attend ce signal),
        # contrairement à un bool qu'il faudrait sonder en boucle serrée.
        self.cancel_event = threading.Event()

    def stop(self) -> None:
        self.kill_switch = True
        self.cancel_event.set()

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
        # [AJOUTÉ 19/10/2026 — angle mort trouvé en comparant notre checklist
        # de test à celle d'un autre harnais (catégorie "entrées trop
        # grandes") : AUCUNE limite de taille n'existait sur le contenu
        # proposé pour write_workspace_draft/execute_python -- un modèle
        # (ou un futur modèle plus capable, voire compromis) pourrait
        # proposer plusieurs centaines de Mo de contenu/code et le harnais
        # l'acceptait tel quel avant exécution. Plafonds arbitraires mais
        # documentés et largement suffisants pour un brouillon/un script
        # généré par un LLM (jamais vu dépasser quelques Ko en conditions
        # réelles cette session).
        _MAX_DRAFT_CONTENT_CHARS = 1_000_000
        _MAX_CODE_CHARS = 200_000
        if tool_id == "write_workspace_draft" and len(arguments.get("content", "")) > _MAX_DRAFT_CONTENT_CHARS:
            return PolicyDecision("deny", "P-SIZE-001", f"contenu dépasse {_MAX_DRAFT_CONTENT_CHARS} caractères")
        if tool_id == "execute_python" and len(arguments.get("code", "")) > _MAX_CODE_CHARS:
            return PolicyDecision("deny", "P-SIZE-002", f"code dépasse {_MAX_CODE_CHARS} caractères")
        if tool_id == "write_workspace_draft":
            raw_path = arguments.get("path", "")
            try:
                normalized = PurePosixPath(raw_path)
            except TypeError:
                return PolicyDecision("deny", "P-PATH-001", "chemin invalide")
            # [AJOUTE 20/10/2026 -- faille reelle trouvee ET REPRODUITE :
            # PurePosixPath("C:/Windows/Temp/evil.txt").is_absolute() vaut
            # False (aucune notion de lettre de lecteur en POSIX) et ne
            # contient aucun ".." -- ce chemin passait ce controle, puis
            # tools.py._resolve_workspace_path() (pathlib NATIF) resolvait
            # hors du workspace sur Windows, sans le moindre "../". Voir
            # models.py (is_drive_absolute_path) pour la meme regle
            # partagee avec TaskContract.validate().
            if normalized.is_absolute() or ".." in normalized.parts or is_drive_absolute_path(raw_path):
                return PolicyDecision("deny", "P-PATH-002", "chemin sortant du workspace")
            if raw_path not in manifest.allowed_paths or raw_path not in contract.allowed_paths:
                return PolicyDecision("deny", "P-PATH-003", "chemin hors périmètre autorisé")
        if tool_id == "capture_screen":
            # [AJOUTÉ 21/10/2026 — même contrôle que write_workspace_draft
            # (P-PATH-001/002/003), sous un rule_id dédié pour que l'audit
            # distingue clairement un refus de capture d'écran d'un refus
            # d'écriture de brouillon.
            raw_path = arguments.get("path", "")
            try:
                normalized = PurePosixPath(raw_path)
            except TypeError:
                return PolicyDecision("deny", "P-SCREEN-001", "chemin invalide")
            if normalized.is_absolute() or ".." in normalized.parts or is_drive_absolute_path(raw_path):
                return PolicyDecision("deny", "P-SCREEN-001", "chemin sortant du workspace")
            if raw_path not in manifest.allowed_paths or raw_path not in contract.allowed_paths:
                return PolicyDecision("deny", "P-SCREEN-001", "chemin hors périmètre autorisé")
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
                resolve_public_ips(host)
            except ValidationError as exc:
                return PolicyDecision("deny", "P-URL-001", str(exc))
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
            if _has_shell_metacharacters(target):
                return PolicyDecision("deny", "P-REA-003", "cible rea contient un métacaractère shell interdit")
        if tool_id == "smokinggun_scan":
            target = arguments.get("target", "")
            if target not in manifest.allowed_paths or target not in contract.allowed_paths:
                return PolicyDecision("deny", "P-SCAN-001", "cible smokinggun hors périmètre autorisé")
            if _has_shell_metacharacters(target):
                return PolicyDecision("deny", "P-SCAN-002", "cible smokinggun contient un métacaractère shell interdit")
        if tool_id == "jacobian_verify":
            operation_id = arguments.get("operation_id", "")
            if not operation_id or _looks_like_cli_flag_injection(operation_id):
                return PolicyDecision("deny", "P-JAC-001", "operation_id jacobian invalide ou ressemble à une option CLI")
            if _has_shell_metacharacters(arguments.get("args_json", "")):
                return PolicyDecision("deny", "P-JAC-002", "args_json jacobian contient un métacaractère shell interdit")
        return PolicyDecision("allow", "P-ALLOW-001", "opération conforme au contrat et au manifeste")

    @staticmethod
    def require(decision: PolicyDecision) -> None:
        if decision.outcome != "allow":
            raise PolicyDenied(f"{decision.rule_id}: {decision.reason}")

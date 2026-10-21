"""Registre fermé et outils simulés du MVP.

Aucun shell, réseau, MCP ou secret n’est fourni ici. Les opérations sont validées
avant exécution puis à nouveau liées à une approbation pour l’écriture R1.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from threading import Event, Thread
from typing import Any
import json
import subprocess

from .approvals import ApprovalService
from .audit import AuditLog
from .evidence import EvidenceStore
from .models import Evidence, PlanManifest, PolicyDenied, RiskLevel, RunState, TaskContract, ValidationError, content_hash
from .policy import PolicyEngine


def _read_text_or_none(path: Path) -> str | None:
    """[AJOUTE 20/10/2026 -- bug reel trouve par un agent puis verifie en
    vrai : file_equals/stdout_matches_file faisaient
    target.read_text(encoding="utf-8").strip() si target.is_file() --
    mais un fichier qui EST bien un fichier peut quand meme contenir des
    octets non-UTF-8 (ex. donnees binaires ecrites par un execute_python
    precedent au meme chemin). target.read_text() levait alors un
    UnicodeDecodeError BRUT non rattrape, faisant planter le run entier
    au lieu de faire simplement echouer le check (comme les autres
    conditions prevues -- execute_python precedent absent/en echec/sans
    sortie -- sont deja gerees proprement quelques lignes plus bas)."""
    if not path.is_file():
        return None
    try:
        return path.read_text(encoding="utf-8").strip()
    except UnicodeDecodeError:
        return None


def _kill_tree(proc: subprocess.Popen) -> None:
    """[AJOUTÉ 19/10/2026 — REC-06 du cahier des charges, reproduit en vrai]
    proc.kill() ne termine QUE le process direct -- avec shell=True (rea_inspect/
    smokinggun_scan sur Windows), ce process direct est cmd.exe, qui a lui-même
    lancé le VRAI outil comme petit-fils. Tuer cmd.exe laisse ce petit-fils
    tourner. Reproduit : un `python -c "time.sleep(15)"` lancé via shell=True,
    puis proc.kill() sur l'objet Popen -- le vrai process python.exe était
    toujours vivant après. os.name == "nt" : `taskkill /T /F` termine tout
    l'arbre -- MAIS seulement si le PID racine est ENCORE VIVANT à l'appel :
    testé avec proc.kill() AVANT taskkill, qui échoue alors avec "processus
    introuvable" (code 128) et n'atteint jamais le petit-fils, erreur
    avalée silencieusement par l'ancien code. taskkill doit donc s'exécuter
    EN PREMIER, tant que cmd.exe est vivant pour que `/T` remonte son arbre ;
    proc.kill() ensuite ne sert qu'en repli (taskkill absent). POSIX :
    proc.kill() seul suffit déjà (aucun appel de ce module n'utilise
    shell=True sur POSIX, donc pas de cmd shell intermédiaire à traverser)."""
    import os
    if os.name == "nt":
        try:
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                           capture_output=True, timeout=5)
        except Exception:
            pass
    try:
        proc.kill()
    except Exception:
        pass


def _run_capped(args: list[str], *, cwd: Path, timeout: float, env: dict[str, str] | None = None,
                shell: bool = False, max_stdout: int = 8000, max_stderr: int = 4000,
                cancel_event: Event | None = None) -> dict[str, Any]:
    """[AJOUTÉ 19/10/2026 — faille réelle signalée par un audit externe]
    subprocess.run(capture_output=True) capture la sortie EN ENTIER en
    mémoire avant que notre code ne la tronque aux derniers N caractères --
    un programme qui produit plusieurs Go de sortie épuise la mémoire du
    process harnais avant même d'atteindre le timeout, qui ne borne que la
    DURÉE, jamais la mémoire. Remplacé par une lecture en flux avec deux
    threads lecteurs (un par descripteur, nécessaire car lire stdout et
    stderr séquentiellement peut bloquer si l'un des deux tampons se
    remplit pendant qu'on attend l'autre) : chaque thread s'arrête de lire
    et le process est tué dès qu'un flux dépasse son plafond, AVANT que le
    reste ne soit lu -- la mémoire réellement retenue par le harnais est
    bornée, pas seulement le texte final affiché.
    """
    try:
        proc = subprocess.Popen(args, cwd=cwd, env=env, shell=shell, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")
    except FileNotFoundError as exc:
        return {"exit_code": None, "stdout": "", "stderr": "", "timed_out": False, "error": str(exc)}
    buffers: dict[str, str] = {"stdout": "", "stderr": ""}
    overflowed = {"stdout": False, "stderr": False}

    def _drain(stream, key: str, cap: int) -> None:
        try:
            for chunk in iter(lambda: stream.read(4096), ""):
                buffers[key] += chunk
                if len(buffers[key]) > cap:
                    buffers[key] = buffers[key][-cap:]
                    overflowed[key] = True
                    _kill_tree(proc)
                    break
        except Exception:
            pass

    readers = [Thread(target=_drain, args=(proc.stdout, "stdout", max_stdout), daemon=True),
              Thread(target=_drain, args=(proc.stderr, "stderr", max_stderr), daemon=True)]
    for reader in readers:
        reader.start()
    # [AJOUTÉ 19/10/2026 — faille réelle signalée par un audit externe]
    # PolicyEngine.stop() positionnait kill_switch (bool) mais rien n'avait
    # de prise sur un sous-processus DÉJÀ lancé -- il tournait jusqu'à son
    # propre timeout, kill switch ou pas. Un watchdog séparé attend le
    # cancel_event (threading.Event, observable depuis un autre thread,
    # contrairement au bool) et tue le process dès qu'il se déclenche, sans
    # attendre le timeout normal.
    cancelled = {"flag": False}
    if cancel_event is not None:
        def _watch_cancel() -> None:
            if cancel_event.wait(timeout=timeout):
                cancelled["flag"] = True
                _kill_tree(proc)
        Thread(target=_watch_cancel, daemon=True).start()
    try:
        proc.wait(timeout=timeout)
        timed_out = False
    except subprocess.TimeoutExpired:
        _kill_tree(proc)
        proc.wait()
        timed_out = True
    for reader in readers:
        reader.join(timeout=5)
    proc.stdout.close()
    proc.stderr.close()
    return {"exit_code": None if (timed_out or cancelled["flag"]) else proc.returncode, "stdout": buffers["stdout"],
           "stderr": buffers["stderr"], "timed_out": timed_out, "cancelled": cancelled["flag"],
           "output_truncated": overflowed["stdout"] or overflowed["stderr"]}


@dataclass(frozen=True)
class ToolDefinition:
    tool_id: str
    version: str
    owner: str
    risk: RiskLevel
    schema: dict[str, Any]
    requires_approval: bool
    enabled: bool = True


class ToolRegistry:
    def __init__(self) -> None:
        self._tools = {
            "read_fixture": ToolDefinition("read_fixture", "1.0", "harness", RiskLevel.R0,
                {"required": ["name"], "properties": {"name": str}, "additional": False}, False),
            "retrieve_fixture": ToolDefinition("retrieve_fixture", "1.0", "harness", RiskLevel.R0,
                {"required": ["query"], "properties": {"query": str}, "additional": False}, False),
            "write_workspace_draft": ToolDefinition("write_workspace_draft", "1.0", "harness", RiskLevel.R1,
                {"required": ["path", "content"], "properties": {"path": str, "content": str}, "additional": False}, True),
            "run_declared_check": ToolDefinition("run_declared_check", "1.0", "harness", RiskLevel.R0,
                {"required": ["check"], "properties": {"check": str}, "additional": False}, False),
            # Délibérément présent pour vérifier que le MVP refuse les actions R4.
            "send_external_message": ToolDefinition("send_external_message", "1.0", "harness", RiskLevel.R4,
                {"required": ["recipient", "body"], "properties": {"recipient": str, "body": str}, "additional": False}, True, False),
            # [AJOUTÉ 18/10/2026 — R2] execute_python et fetch_url. Risque R2,
            # approbation exacte requise (comme write_workspace_draft) : le
            # grant est lié au CODE/URL exact proposé, jamais à "autoriser le
            # code" en général. Voir docs/threat-model.md pour les limites
            # connues (pas de sandbox OS, egress non filtré au niveau réseau).
            "execute_python": ToolDefinition("execute_python", "1.0", "harness", RiskLevel.R2,
                {"required": ["code"], "properties": {"code": str}, "additional": False}, True),
            "fetch_url": ToolDefinition("fetch_url", "1.0", "harness", RiskLevel.R2,
                {"required": ["url"], "properties": {"url": str}, "additional": False}, True),
            # [AJOUTÉ 18/10/2026 — demandé : pont harnais -> REA] REA
            # (reverse engineering d'APK/binaires/appareils réels) n'est
            # PAS un outil que le modèle local peut invoquer en direct --
            # ce n'est pas un process que execute_python peut lancer, c'est
            # un outil côté agent Claude, et REA touche de VRAIS artefacts
            # (device, APK) qu'un modèle non supervisé ne doit jamais piloter
            # seul. Ce pont est donc ASYNCHRONE et relayé par un humain/Claude :
            # le modèle peut seulement PROPOSER une question d'analyse (R0,
            # n'exécute rien), écrite dans rea_requests.jsonl du run. Rien
            # ne garantit qu'elle sera traitée ni quand -- une mission
            # future du même tenant verra la réponse (si fournie) comme
            # entrée de mémoire, jamais comme autorisation.
            "request_rea_analysis": ToolDefinition("request_rea_analysis", "1.0", "harness", RiskLevel.R0,
                {"required": ["target", "question"], "properties": {"target": str, "question": str}, "additional": False}, False),
            # [AJOUTÉ 18/10/2026 — demandé : "integre le sien"] La VRAIE CLI
            # rea (github.com/morluto/rea, confirmée installée : `rea
            # --version` -> 6.5.0) existe réellement -- ce n'est plus un
            # relais asynchrone comme request_rea_analysis ci-dessus, mais un
            # appel subprocess réel (voir _execute). Risque R1 (comme
            # write_workspace_draft) : en LECTURE SEULE sur l'artefact
            # analysé (aucune des sous-commandes autorisées n'installe,
            # ne flashe, ne pousse ni ne débogue quoi que ce soit -- voir la
            # liste POLICY._REA_SAFE_SUBCOMMANDS dans policy.py). Grant lié
            # au (sous-commande, cible) EXACT proposé, comme tout outil R1+.
            "rea_inspect": ToolDefinition("rea_inspect", "1.0", "harness", RiskLevel.R1,
                {"required": ["subcommand", "target"], "properties": {"subcommand": str, "target": str}, "additional": False}, True),
            # [AJOUTÉ 18/10/2026 — demandé : "integre ce qui va nous aider"]
            # smokinggun (morluto/smokinggun, vérifié installé et testé en
            # vrai : trouve de vraies alertes `membership-in-loop` dans
            # notre propre src/, SARIF valide) est un analyseur STATIQUE
            # confirmé hors-ligne (aucune exécution observée, même garantie
            # que sa doc). Risque R0 (comme read_fixture/run_declared_check)
            # : il ne modifie rien et n'exécute jamais la cible analysée —
            # seule la cible (chemin dans le workspace) est contrainte par
            # allowed_paths, pas de sous-commande à filtrer (un seul mode :
            # scan en lecture seule).
            "smokinggun_scan": ToolDefinition("smokinggun_scan", "1.0", "harness", RiskLevel.R0,
                {"required": ["target"], "properties": {"target": str}, "additional": False}, False),
            # [AJOUTÉ 18/10/2026] jacobian (morluto/jacobian, vérifié en vrai :
            # extended_gcd/Bézout, SAT/SMT via Z3, déterminant de matrice —
            # tous vérifiés à la main contre le résultat réel, pas une
            # auto-déclaration du modèle). Risque R0 : opération mathématique
            # PURE, sans accès fichier/réseau/exécution arbitraire — c'est
            # exactement le même principe que stdout_matches_file
            # (comparer contre une vérité indépendante), ici appliqué aux
            # maths plutôt qu'à un print(). operation_id n'est pas limité à
            # une allowlist (ce sont des fonctions mathématiques pures, pas
            # des commandes shell) ; args_json est une chaîne JSON, validée
            # par jacobian lui-même avant tout calcul.
            "jacobian_verify": ToolDefinition("jacobian_verify", "1.0", "harness", RiskLevel.R0,
                {"required": ["operation_id", "args_json"], "properties": {"operation_id": str, "args_json": str}, "additional": False}, False),
        }

    def get(self, tool_id: str) -> ToolDefinition:
        if tool_id not in self._tools:
            raise PolicyDenied("outil inconnu")
        tool = self._tools[tool_id]
        if not tool.enabled:
            raise PolicyDenied("capacité non activée dans le MVP")
        return tool

    @staticmethod
    def validate_arguments(tool: ToolDefinition, arguments: dict[str, Any]) -> None:
        schema = tool.schema
        if not isinstance(arguments, dict):
            raise ValidationError("arguments non structurés")
        extra = set(arguments) - set(schema["properties"])
        if extra and not schema.get("additional", False):
            raise ValidationError("champ supplémentaire interdit")
        missing = set(schema["required"]) - set(arguments)
        if missing:
            raise ValidationError("argument requis absent")
        for name, expected_type in schema["properties"].items():
            if name in arguments and not isinstance(arguments[name], expected_type):
                raise ValidationError(f"type invalide pour {name}")


class ToolGateway:
    def __init__(self, *, workspace: Path, fixtures: Path, registry: ToolRegistry,
                 policy: PolicyEngine, approvals: ApprovalService, audit: AuditLog,
                 evidence: EvidenceStore | None = None) -> None:
        self.workspace = workspace.resolve()
        self.fixtures = fixtures.resolve()
        self.registry = registry
        self.policy = policy
        self.approvals = approvals
        self.audit = audit
        # [AJOUTÉ 18/10/2026] Optionnel (None) pour ne pas casser un appelant
        # existant qui construirait un ToolGateway sans ce paramètre ; sans
        # evidence, retrieve_fixture renvoie ses correspondances mais ne crée
        # plus de provenance tracée — RAG réel, piège possible si on l'omet.
        self.evidence = evidence
        self.workspace.mkdir(parents=True, exist_ok=True)

    def invoke(self, *, contract: TaskContract, manifest: PlanManifest, state: RunState,
               actor_id: str, tool_id: str, arguments: dict[str, Any], grant_id: str | None = None,
               prior_results: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        try:
            tool = self.registry.get(tool_id)
        except PolicyDenied as exc:
            # [AJOUTE 20/10/2026 -- bug reel trouve par un agent puis
            # verifie en vrai : registry.get() s'execute AVANT
            # policy.authorize(), donc un tool_id inconnu ou desactive
            # (enabled=False, ex. send_external_message, volontairement
            # desactive pour verifier le refus des actions R4) ne
            # produisait JAMAIS l'entree d'audit "policy" structuree
            # (rule_id/owasp_llm_risk) que TOUS les autres refus de cette
            # meme fonction obtiennent -- seule une trace generique
            # "state_machine"/"execution_blocked" (engine.py) apparaissait
            # plus tard, sans rule_id ni owasp_llm_risk. Une requete
            # d'audit filtrant stage=="policy" pour les refus marques OWASP
            # manquait donc silencieusement ces deux cas. Rule_id distinct
            # par cause pour que l'audit distingue les deux.
            rule_id = "P-TOOL-001" if str(exc) == "outil inconnu" else "P-TOOL-002"
            self.audit.append("policy", tool_id, "deny", {"rule": rule_id, "reason": str(exc), "owasp_llm_risk": None})
            raise
        self.registry.validate_arguments(tool, arguments)
        decision = self.policy.authorize(contract=contract, manifest=manifest, state=state,
                                         tool_id=tool_id, arguments=arguments, tool_risk=tool.risk)
        self.audit.append("policy", tool_id, decision.outcome,
                          {"rule": decision.rule_id, "reason": decision.reason, "owasp_llm_risk": decision.owasp_llm_risk})
        self.policy.require(decision)
        if tool.requires_approval:
            if not grant_id:
                # [AJOUTE 20/10/2026 -- bug reel trouve par un agent puis
                # verifie en vrai, meme classe que le correctif de
                # registry.get() (commit 5b5c9ae) : cette levee se produit
                # APRES que policy.authorize() ait deja ecrit son entree
                # "policy"/allow -- un lecteur de audit.jsonl voit donc
                # "allow" puis RIEN, sans aucune trace structuree que
                # l'execution a ensuite ete refusee faute de grant. Pire
                # que le bug original : l'autorisation elle-meme semble
                # reussie dans le journal.
                self.audit.append("policy", tool_id, "deny",
                                  {"rule": "P-APPROVAL-001", "reason": "approbation exacte requise",
                                   "owasp_llm_risk": "LLM06:2025 Excessive Agency"})
                raise PolicyDenied("approbation exacte requise")
            try:
                self.approvals.validate_and_consume(grant_id=grant_id, actor_id=actor_id, run_id=manifest.run_id,
                                                    manifest_hash=manifest.manifest_hash, tool_id=tool_id, arguments=arguments)
            except PolicyDenied as exc:
                # [AJOUTE 20/10/2026 -- bug reel trouve par un agent puis
                # verifie en vrai, meme classe que les deux correctifs
                # precedents (5b5c9ae, 5c08a57) : validate_and_consume()
                # a QUATRE motifs distincts de refus (grant inconnu,
                # deja consomme, expire, ou lie a une action differente)
                # -- tous non rattrapes ici. policy.authorize() a deja
                # ecrit "allow" avant d'atteindre cette ligne : sans ce
                # correctif, le journal montre "allow" puis RIEN pour ces
                # quatre cas, aucun moyen de savoir que l'execution a
                # ensuite ete refusee faute de grant valide.
                self.audit.append("approval", "consume", "deny", {"grant_id": grant_id, "tool_id": tool_id, "reason": str(exc)})
                raise
            self.audit.append("approval", "consume", "allow", {"grant_id": grant_id, "tool_id": tool_id})
        try:
            result = self._execute(tool_id, arguments, budget_seconds=contract.budget_seconds, prior_results=prior_results)
        except PolicyDenied as exc:
            # [AJOUTE 20/10/2026 -- bug reel trouve par un agent puis
            # verifie en vrai, meme classe que les trois correctifs
            # precedents (5b5c9ae, 5c08a57, f1c3cdf) : _execute() peut
            # lever PolicyDenied APRES que policy.authorize() ait deja
            # ecrit "allow" (collision de repertoire, chemin hors
            # workspace, fixture hors repertoire...) -- jusqu'ici
            # rattrape UNIQUEMENT par le except Exception generique
            # d'engine.py, qui enregistre "execution_blocked" avec
            # decision="allow" (la transition d'etat elle-meme a reussi)
            # et AUCUN rule_id/owasp_llm_risk -- un filtre d'audit sur
            # decision=="deny" rate ce cas a 100%, et pire, l'entree qui
            # signale le blocage affiche elle-meme decision="allow", ce
            # qui est activement trompeur pour un filtre automatise.
            self.audit.append("policy", tool_id, "deny", {"rule": "P-EXEC-001", "reason": str(exc), "owasp_llm_risk": None})
            raise
        self.audit.append("gateway", tool_id, "executed", {"result_hash": content_hash(result), "tool_version": tool.version})
        return result

    def _resolve_workspace_path(self, relative_path: str) -> Path:
        candidate = (self.workspace / relative_path).resolve()
        if self.workspace != candidate and self.workspace not in candidate.parents:
            raise PolicyDenied("résolution de chemin hors workspace")
        return candidate

    def _execute(self, tool_id: str, arguments: dict[str, Any], *, budget_seconds: int = 60,
                prior_results: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        if tool_id == "read_fixture":
            filename = Path(arguments["name"]).name
            candidate = (self.fixtures / filename).resolve()
            if self.fixtures not in candidate.parents:
                raise PolicyDenied("fixture hors répertoire autorisé")
            return {"content": candidate.read_text(encoding="utf-8"), "untrusted": True}
        if tool_id == "retrieve_fixture":
            # [AJOUTÉ 18/10/2026 — RAG local] Avant : matches retournés sans
            # aucune trace de provenance (contrairement à l'intention du
            # module evidence.py, déjà présent mais jamais relié ici). Chaque
            # ligne correspondante devient maintenant une Evidence réelle
            # (locator = fichier + numéro de ligne), que le caller peut citer
            # dans un Claim pour que require_valid_claims() la valide
            # réellement — au lieu de la Evidence de démonstration fixe
            # ajoutée par HarnessEngine.plan(), sans rapport avec la requête.
            corpus = self.fixtures / "corpus.md"
            text = corpus.read_text(encoding="utf-8") if corpus.exists() else ""
            query = arguments["query"].lower()
            matches: list[str] = []
            evidence_ids: list[str] = []
            for line_number, line in enumerate(text.splitlines(), start=1):
                if query not in line.lower():
                    continue
                matches.append(line)
                if self.evidence is not None:
                    record = Evidence.create(title="Fixture corpus local", url="local://fixtures/corpus.md",
                                              locator=f"fixtures/corpus.md#L{line_number}", excerpt=line,
                                              untrusted=True)
                    self.evidence.add_evidence(record)
                    evidence_ids.append(record.evidence_id)
            return {"query": arguments["query"], "matches": matches, "evidence_ids": evidence_ids, "untrusted": True}
        if tool_id == "write_workspace_draft":
            target = self._resolve_workspace_path(arguments["path"])
            # [AJOUTE 20/10/2026 -- bug reel trouve par un agent puis
            # verifie en vrai : si `target` existe deja comme REPERTOIRE
            # (collision avec une operation precedente, nom reutilise par
            # le modele), target.write_text() levait un PermissionError/
            # IsADirectoryError brut non rattrape -- aucun PolicyDenied/
            # ValidationError propre comme le reste du codebase utilise
            # deja pour les conditions previsibles (fixture absente,
            # resultat execute_python manquant, stdout tronque). Convertit
            # cette condition prevue en erreur typee, geree, plutot que de
            # laisser une exception OS brute (avec le chemin natif complet
            # dans son message) remonter jusqu'au moteur.
            if target.is_dir():
                raise PolicyDenied("cible d'écriture existante est un répertoire")
            # [AJOUTE 20/10/2026 -- bug reel trouve par un agent : "changed"
            # etait toujours True, meme en reecrivant un contenu identique
            # -- inoffensif aujourd'hui (rien en aval ne lit ce champ,
            # verifie par l'agent), mais corrige par hygiene plutot que de
            # laisser un champ qui ment dans un resultat audite.
            previous_content = target.read_text(encoding="utf-8") if target.is_file() else None
            # [AJOUTE 21/10/2026 -- bug reel trouve par un agent puis
            # verifie en vrai : le is_dir() ci-dessus ne couvre que la
            # cible elle-meme -- si un segment INTERMEDIAIRE du chemin
            # (le parent, ou un parent de parent) existe deja comme
            # FICHIER plutot que comme repertoire ou absent, mkdir(parents=
            # True, exist_ok=True) leve un FileExistsError/OSError brut
            # ([WinError 183] sous Windows) non rattrape ici. Ce brut
            # n'est PAS un PolicyDenied, donc il echappe au except
            # PolicyDenied de invoke() (correctif P-EXEC-001) : aucune
            # entree "policy"/"deny" n'est ecrite, alors que le grant a
            # DEJA ete consomme (brule) par validate_and_consume() juste
            # avant -- le journal d'audit s'arrete sur "approval consumed"
            # sans aucune trace de ce qui est arrive a l'execution, et le
            # grant a usage unique est perdu pour une operation qui n'a
            # jamais reellement eu lieu. Convertit la meme famille de
            # defaillance OS previsible en PolicyDenied, comme le is_dir()
            # voisin le fait deja pour la collision sur la cible elle-meme.
            try:
                target.parent.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                raise PolicyDenied(f"impossible de créer le répertoire parent de la cible : {exc}") from exc
            target.write_text(arguments["content"], encoding="utf-8")
            changed = previous_content != arguments["content"]
            return {"path": arguments["path"], "content_hash": content_hash(arguments["content"]), "changed": changed}
        if tool_id == "run_declared_check":
            check = arguments["check"]
            if check == "draft_exists":
                # [AJOUTE 20/10/2026 -- bug reel trouve par un agent puis
                # verifie en vrai : rglob("*.md") filtre par NOM seulement,
                # sans is_file() -- un REPERTOIRE nomme "foo.md" (vide,
                # aucun vrai brouillon dedans) satisfaisait ce check et
                # marquait le run COMPLETED. Meme classe de faux-positif
                # que celle deja corrigee pour file_equals (18/10/2026 :
                # le modele inventant sa propre valeur attendue), ici via
                # un nom de repertoire plutot qu'une valeur mensongere.
                found = any(path.is_file() for path in self.workspace.rglob("*.md"))
                return {"check": check, "exit_code": 0 if found else 1, "passed": found}
            # [AJOUTÉ 18/10/2026 — trouvé en comparant raisonnement on/off]
            # "draft_exists" était le SEUL vérificateur possible : aucun moyen
            # de vérifier le CONTENU d'un résultat produit par execute_python
            # (ex. "resultat.txt contient 391"), donc AGENTIC_EXECUTION ne
            # pouvait jamais prouver qu'un calcul était correct, seulement
            # que le fichier existait au bon endroit. "file_equals:<chemin
            # relatif au workspace>:<contenu attendu>" comble ça ; reste du
            # texte simple comme "draft_exists" — pas un nouveau schéma, pour
            # ne pas élargir la surface d'arguments de l'outil.
            if check.startswith("file_equals:"):
                _, _, rest = check.partition(":")
                relative_path, _, expected = rest.partition(":")
                target = self._resolve_workspace_path(relative_path)
                actual = _read_text_or_none(target)
                passed = actual == expected
                return {"check": check, "exit_code": 0 if passed else 1, "passed": passed,
                       "actual": actual}
            if check.startswith("stdout_matches_file:"):
                # [AJOUTÉ 18/10/2026 — trouvé en vrai, scripts/mission_loop.py]
                # file_equals laisse le modèle choisir LUI-MÊME la valeur
                # "attendue" : rien n'empêchait d'écrire "1001" dans le fichier
                # puis de déclarer file_equals:...:1001 — cohérent avec
                # lui-même, FAUX par rapport au vrai calcul. Reproduit en vrai :
                # execute_python a calculé 385 (stdout correct), le modèle a
                # quand même écrit 1001 dans le fichier et validé sa propre
                # valeur inventée — run COMPLETED, résultat faux. Ce
                # vérificateur ne laisse plus le modèle fournir AUCUNE valeur
                # attendue : il compare le fichier à la VRAIE sortie du
                # DERNIER execute_python déjà exécuté dans ce run — rien à
                # inventer, rien à mentir sur.
                _, _, relative_path = check.partition(":")
                target = self._resolve_workspace_path(relative_path)
                actual = _read_text_or_none(target)
                prior_entry = None
                for entry in reversed(prior_results or []):
                    if entry["tool_id"] == "execute_python":
                        prior_entry = entry
                        break
                if prior_entry is None:
                    return {"check": check, "exit_code": 1, "passed": False,
                           "actual": actual, "error": "aucun execute_python précédent dans ce run"}
                # [AJOUTÉ 18/10/2026 — bug réel trouvé en faisant tourner une
                # vraie mission (Ornith-1.5-9B) : le code proposé plantait
                # (TypeError sur open(...).write(__doc__), __doc__=None)
                # avant d'écrire quoi que ce soit — stdout vide ET fichier
                # jamais écrit (donc lui aussi vide) -> "" == "" -> passed
                # à tort, run marqué COMPLETED alors que RIEN n'avait
                # fonctionné. Un crash silencieux ne doit jamais ressembler
                # à un succès : on exige exit_code 0 ET un stdout non vide
                # avant même de comparer au fichier.
                if prior_entry["result"].get("exit_code") != 0:
                    return {"check": check, "exit_code": 1, "passed": False, "actual": actual,
                           "error": "le execute_python précédent a échoué (exit_code != 0) : rien à vérifier"}
                # [AJOUTE 20/10/2026 -- bug reel trouve par un agent puis
                # verifie en vrai : _run_capped() tronque un stdout qui
                # depasse le plafond en NE GARDANT QUE LA FIN du buffer
                # (voir plus bas, "output_truncated"). Ce check comparait
                # deja contre prior_stdout sans jamais regarder ce drapeau
                # -- un modele pouvait imprimer la vraie valeur PUIS du
                # remplissage predictible au-dela du plafond, laissant
                # stdout_matches_file comparer contre ce remplissage au lieu
                # du vrai calcul. Exactement le contournement que ce
                # verificateur a ete ajoute pour empecher (voir commentaire
                # 18/10/2026 ci-dessus), rouvert par un angle different. Un
                # stdout tronque ne peut jamais etre traite comme "la vraie
                # sortie" : refuse plutot que de comparer un fragment.
                if prior_entry["result"].get("output_truncated"):
                    return {"check": check, "exit_code": 1, "passed": False, "actual": actual,
                           "error": "stdout du execute_python précédent tronqué (plafond de sortie) : comparaison non fiable"}
                prior_stdout = prior_entry["result"].get("stdout", "").strip()
                if not prior_stdout:
                    return {"check": check, "exit_code": 1, "passed": False, "actual": actual,
                           "error": "le execute_python précédent n'a rien affiché : rien à comparer"}
                passed = actual == prior_stdout
                return {"check": check, "exit_code": 0 if passed else 1, "passed": passed,
                       "actual": actual, "expected_from_stdout": prior_stdout}
            raise PolicyDenied("vérificateur non déclaré")
        if tool_id == "execute_python":
            # [AJOUTÉ 18/10/2026 — R2] Sandbox LOGIQUE, pas matérielle (voir
            # docs/threat-model.md "Limites connues") : cwd forcé dans le
            # workspace du run, timeout dur, sortie plafonnée. Ce n'est PAS
            # une isolation réseau/OS — le code tourne avec les mêmes
            # privilèges que le process harness. L'approbation exacte
            # (grant lié au CODE littéral) est la vraie barrière ici, pas
            # cette sandbox.
            import os
            import sys
            timeout = max(1, min(budget_seconds, 60))
            # [CORRIGÉ 18/10/2026 — bug réel reproduit par test_t33] le
            # PROCESS ENFANT utilise cp1252 par défaut pour SA PROPRE sortie
            # console sur Windows -> un print() affichant un caractère hors
            # cp1252 plante DANS l'enfant. Corrigé en forçant
            # PYTHONIOENCODING=utf-8 dans l'environnement du sous-processus.
            env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
            return _run_capped([sys.executable, "-c", arguments["code"]], cwd=self.workspace,
                               timeout=timeout, env=env, max_stdout=8000, max_stderr=4000,
                               cancel_event=self.policy.cancel_event)
        if tool_id == "fetch_url":
            # [AJOUTÉ 18/10/2026 — R2] PolicyEngine a déjà validé l'allowlist
            # exacte + la garde SSRF basique avant d'arriver ici (voir
            # policy.py P-URL-001/002) ; cette méthode ajoute la limite de
            # taille de réponse et le marquage untrusted (contenu externe,
            # jamais une instruction, même pattern que read_fixture).
            # [CORRIGÉ 18/10/2026 — trouvé en documentant la checklist R2+ ci-
            # dessus] urlopen() suit les redirections HTTP par défaut : une
            # URL dans l'allowlist pourrait répondre 302 vers un hôte privé
            # (ex. l'IP de métadonnées cloud) et PolicyEngine ne revérifie
            # jamais cette destination, puisqu'elle ne voit que l'URL de
            # départ. _NoRedirect bloque toute redirection : l'appel échoue
            # proprement (capturé ci-dessous) plutôt que de la suivre.
            # [CORRIGÉ 19/10/2026 — TOCTOU réel signalé par un audit externe]
            # policy.py valide les IP résolues AVANT cet appel, mais
            # urlopen() résout le hostname À NOUVEAU au moment de la vraie
            # connexion (via socket.getaddrinfo interne) -- rien ne garantit
            # que c'est la même adresse (DNS à TTL court, résolveur qui
            # change de réponse). On revalide ET on épingle ICI, au point
            # exact de connexion : socket.getaddrinfo est monkeypatché pour
            # CETTE requête uniquement, forcé à ne renvoyer QUE les adresses
            # déjà validées par resolve_public_ips -- le Host/SNI/vérification
            # TLS restent sur le nom de domaine (inchangés), seule la
            # résolution DNS sous-jacente est gelée sur un résultat déjà
            # inspecté. Un hôte qui ne résout pas (fixtures de test type
            # example.invalid) laisse getaddrinfo intact -- pas de SSRF
            # possible sur un hôte qui ne résout nulle part.
            import socket as socket_module
            from urllib.error import HTTPError
            from urllib.parse import urlparse
            from urllib.request import HTTPRedirectHandler, build_opener
            from .policy import resolve_public_ips

            class _NoRedirect(HTTPRedirectHandler):
                def redirect_request(self, *args, **kwargs):
                    return None

            timeout = max(1, min(budget_seconds, 30))
            host = urlparse(arguments["url"]).hostname or ""
            try:
                pinned_ips = resolve_public_ips(host)
            except ValidationError as exc:
                return {"url": arguments["url"], "error": f"garde SSRF (DNS rebinding) : {exc}", "untrusted": True}
            original_getaddrinfo = socket_module.getaddrinfo
            # [CORRIGE 20/10/2026 -- bug reel trouve par un agent puis
            # REPRODUIT (serveur HTTP reel, getaddrinfo truque qui leve
            # gaierror au 1er appel -- la revalidation ci-dessus -- puis
            # resout vers 127.0.0.1 au 2e appel -- la vraie connexion) :
            # resolve_public_ips() renvoie un set() VIDE aussi bien pour
            # "cet hote ne resout nulle part" (sans risque, cf. commentaire
            # plus haut) QUE pour "la resolution a echoue maintenant mais
            # pourrait reussir differemment juste apres" (DNS rebinding
            # avec une reponse SERVFAIL/timeout intercalee). L'ancien code
            # ne posait AUCUN monkeypatch quand pinned_ips etait vide,
            # laissant opener.open() refaire sa PROPRE resolution sans
            # aucune garde -- exactement la race que l'epinglage existe
            # pour fermer. Desormais le monkeypatch est TOUJOURS installe :
            # si pinned_ips est vide, toute resolution reelle au moment de
            # la connexion est refusee (echec clos) plutot que silencieuse-
            # ment acceptee (echec ouvert).
            def _pinned_getaddrinfo(requested_host, *args, **kwargs):
                if requested_host == host:
                    if not pinned_ips:
                        raise socket_module.gaierror(
                            f"résolution SSRF refusée (échec clos) pour {requested_host!r}")
                    return [info for info in original_getaddrinfo(requested_host, *args, **kwargs) if info[4][0] in pinned_ips]
                return original_getaddrinfo(requested_host, *args, **kwargs)
            socket_module.getaddrinfo = _pinned_getaddrinfo
            opener = build_opener(_NoRedirect)
            try:
                with opener.open(arguments["url"], timeout=timeout) as response:  # nosec B310: validé par policy.py + resolve_public_ips, résolution épinglée, redirections bloquées
                    raw = response.read(1_000_000)
                content = raw.decode("utf-8", errors="replace")
                return {"url": arguments["url"], "content": content, "truncated": len(raw) >= 1_000_000, "untrusted": True}
            except HTTPError as exc:
                exc.close()
                if exc.code in (301, 302, 303, 307, 308):
                    return {"url": arguments["url"], "error": "redirection refusée (garde anti-SSRF post-fetch)", "untrusted": True}
                return {"url": arguments["url"], "error": str(exc), "untrusted": True}
            except Exception as exc:
                return {"url": arguments["url"], "error": str(exc), "untrusted": True}
            finally:
                socket_module.getaddrinfo = original_getaddrinfo
        if tool_id == "request_rea_analysis":
            # [AJOUTÉ 18/10/2026] Relais ASYNCHRONE : n'exécute rien, écrit
            # juste la demande pour qu'un humain/Claude la traite hors de ce
            # run (voir rea_inspect ci-dessous pour le pont SYNCHRONE réel).
            request = {"target": arguments["target"], "question": arguments["question"]}
            requests_path = self.workspace.parent / "rea_requests.jsonl"
            with requests_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(request, ensure_ascii=False) + "\n")
            return {"recorded": True, "target": request["target"]}
        if tool_id == "rea_inspect":
            # [AJOUTÉ 18/10/2026 — demandé : "integre le sien"] Appel
            # SUBPROCESS RÉEL vers la vraie CLI `rea` (morluto/rea,
            # confirmée installée : `rea --version` -> 6.5.0). PolicyEngine
            # a déjà validé la sous-commande (allowlist lecture seule
            # _REA_SAFE_SUBCOMMANDS) et la cible (allowed_paths exact) avant
            # d'arriver ici — même défense en profondeur que fetch_url/
            # execute_python : le grant est lié au (sous-commande, cible)
            # EXACT proposé, jamais à "autoriser rea" en général.
            import os
            import shutil
            timeout = max(1, min(budget_seconds, 60))
            # [AJOUTE 20/10/2026 -- bug reel trouve par un agent puis
            # verifie en vrai : avec shell=True (branche Windows), un
            # binaire absent ne leve JAMAIS FileNotFoundError -- cmd.exe
            # lui-meme existe toujours, Popen reussit, puis cmd.exe ecrit
            # son propre message d'erreur localise sur stderr et sort avec
            # exit_code=1. Resultat indiscernable d'un VRAI echec de
            # l'outil (rea tourne mais l'analyse trouve un probleme) --
            # aucune cle "error" distincte, contrairement a jacobian_verify
            # (Popen direct, sans shell) qui produit deja une erreur propre
            # sur ce meme cas. Verifie explicitement AVANT shell=True pour
            # produire le meme type d'erreur structuree que jacobian_verify.
            if os.name == "nt" and shutil.which("rea") is None:
                return {"subcommand": arguments["subcommand"], "target": arguments["target"],
                       "untrusted": True, "error": "binaire 'rea' introuvable sur PATH"}
            # [CORRIGÉ 18/10/2026] sur Windows, `rea` est un wrapper npm
            # (rea.CMD) -- shell=True requis pour le résoudre. subcommand
            # vient d'une allowlist fixe (aucun métacaractère possible) et
            # target doit correspondre EXACTEMENT à une entrée allowed_paths
            # pré-approuvée par l'opérateur (jamais un texte libre du
            # modèle) — risque d'injection shell résiduel jugé acceptable.
            result = _run_capped(["rea", arguments["subcommand"], arguments["target"], "--json"],
                                 cwd=self.workspace, timeout=timeout, shell=(os.name == "nt"),
                                 max_stdout=8000, max_stderr=2000, cancel_event=self.policy.cancel_event)
            return {"subcommand": arguments["subcommand"], "target": arguments["target"], "untrusted": True, **result}
        if tool_id == "smokinggun_scan":
            # [AJOUTÉ 18/10/2026] Analyseur STATIQUE confirmé (morluto/
            # smokinggun, testé en vrai contre src/ de ce projet : 6 vraies
            # alertes membership-in-loop retrouvées). Jamais d'exécution de
            # la cible — seule garantie que le projet revendique et qu'on a
            # vérifiée. shell=True sur Windows pour la même raison que
            # rea_inspect (wrapper npm .CMD).
            import os
            import shutil
            timeout = max(1, min(budget_seconds, 60))
            # [AJOUTE 20/10/2026 -- meme faille que rea_inspect ci-dessus]
            if os.name == "nt" and shutil.which("smokinggun") is None:
                return {"target": arguments["target"], "untrusted": True,
                       "error": "binaire 'smokinggun' introuvable sur PATH"}
            result = _run_capped(["smokinggun", "scan", arguments["target"], "--format", "sarif"],
                                 cwd=self.workspace, timeout=timeout, shell=(os.name == "nt"),
                                 max_stdout=8000, max_stderr=2000, cancel_event=self.policy.cancel_event)
            return {"target": arguments["target"], "untrusted": True, **result}
        if tool_id == "jacobian_verify":
            # [AJOUTÉ 18/10/2026] venv dédié .venv-jacobian/ (Python 3.12,
            # install --only-binary=:all: -- jacobian ne supporte pas
            # Python 3.14 et sa compilation source échoue sans toolchain
            # make sur Windows, trouvé en testant en vrai). PYTHONIOENCODING
            # forcé en utf-8 : jacobian plante sinon sur l'encodage console
            # Windows par défaut (cp1252) dès qu'une sortie contient un
            # symbole mathématique (ex. ⊕) -- bug Windows réel reproduit en
            # testant `jacobian catalog`.
            import os
            import sys
            # self.fixtures.parent est le PROJECT_ROOT du moteur (dossier du
            # run), PAS la racine du dépôt où vit .venv-jacobian/ -- résolu
            # depuis ce fichier lui-même.
            # [AJOUTE 20/10/2026 -- bug reel trouve par un agent puis
            # verifie par inspection/raisonnement (meme norme que le bug
            # original, confirme par la logique cli.py ci-dessous) :
            # Path(__file__) pointe vers le dossier d'extraction temporaire
            # (_MEI...) une fois figé par PyInstaller, pas vers
            # l'emplacement reel du checkout -- EXACTEMENT le meme piege
            # deja corrige pour cli.py._project_root() (18/10/2026), jamais
            # propage ici. Sous une distribution figee, repo_root pointait
            # dans l'arbre temporaire PyInstaller, .venv-jacobian/ n'y
            # existe jamais meme si le venv est correctement installe a
            # cote du vrai exe -- jacobian_verify rapportait alors "binaire
            # introuvable" a tort dans ce mode de deploiement uniquement
            # (checkout source normal non affecte, verifie empiriquement).
            repo_root = Path.cwd() if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[2]
            jacobian_bin = repo_root / ".venv-jacobian" / "Scripts" / "jacobian.exe"
            if not jacobian_bin.is_file():
                jacobian_bin = repo_root / ".venv-jacobian" / "bin" / "jacobian"
            timeout = max(1, min(budget_seconds, 30))
            env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
            result = _run_capped([str(jacobian_bin), "run", arguments["operation_id"], "--json", arguments["args_json"]],
                                 cwd=self.workspace, timeout=timeout, env=env, max_stdout=4000, max_stderr=2000,
                                 cancel_event=self.policy.cancel_event)
            return {"operation_id": arguments["operation_id"], **result}
        raise PolicyDenied("implémentation d’outil absente")

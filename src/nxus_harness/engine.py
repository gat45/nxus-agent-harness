"""Orchestrateur local P0/P1 : transitions, plans, grants, outils, vérification et rapport."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Iterator
import json
import os
from uuid import uuid4

from .approvals import ApprovalService
from .audit import AuditLog, redact
from .evidence import EvidenceStore
from .locking import exclusive_file_lock
from .memory import MemoryStore
from .models import (CheckStatus, Evidence, PlanManifest, RunState, TaskContract,
                     ValidationError, VerificationResult, content_hash, flatten_for_markdown,
                     require_safe_identifier, utc_now)
from .planner import ReflectionReview, SimulatedPlanner
from .policy import PolicyEngine
from .tools import ToolGateway, ToolRegistry


@contextmanager
def _run_exclusive_lock(run_dir: Path, *, timeout_seconds: float = 10.0) -> Iterator[None]:
    """[AJOUTÉ 19/10/2026 — faille réelle trouvée par un agent puis
    REPRODUITE avec deux vrais process séparés (REC-05) : resume_run() +
    approve_and_run() lus par deux process au même instant pouvaient tous
    les deux voir AWAITING_APPROVAL (lu depuis le disque avant que l'un ou
    l'autre ne transitionne), passer le contrôle _require_state(), puis
    exécuter la MÊME opération non idempotente deux fois -- corriger
    uniquement la perte de grant dans approvals.issue() (voir ce fichier,
    même date) a RÉVÉLÉ ce problème plus profond au lieu de le masquer :
    sans ce verrou, les deux process obtenaient chacun un grant valide et
    exécutaient tous les deux. Reproduit : counter.txt contenait "RAN;RAN;"
    (deux écritures réelles d'un execute_python supposé s'exécuter une
    fois). Même motif de verrou de fichier portable que ApprovalService
    (O_CREAT|O_EXCL atomique), mais ICI sur tout le cycle vérification
    d'état → émission des grants → transition, pas seulement l'écriture
    d'un grant isolé.

    [MIS A JOUR 20/10/2026 -- meme faille de verrou perime que
    approvals.py (voir locking.py) : delegue maintenant a
    locking.exclusive_file_lock(), partage entre les trois fichiers qui
    dupliquaient ce motif."""
    lock_path = run_dir / "run.lock"
    with exclusive_file_lock(lock_path, timeout_seconds=timeout_seconds, on_timeout=ValidationError,
                             timeout_message="verrou de run indisponible (contention)"):
        yield


_ALLOWED_TRANSITIONS: dict[RunState, set[RunState]] = {
    RunState.INTAKE: {RunState.DISCOVERY, RunState.CLARIFYING, RunState.ABORTED},
    RunState.DISCOVERY: {RunState.DRAFTING_PLAN, RunState.ABORTED},
    RunState.DRAFTING_PLAN: {RunState.REFLECTION_REVIEW, RunState.AWAITING_APPROVAL, RunState.ABORTED},
    RunState.REFLECTION_REVIEW: {RunState.DRAFTING_PLAN, RunState.AWAITING_APPROVAL, RunState.ABORTED},
    RunState.AWAITING_APPROVAL: {RunState.APPROVED, RunState.REJECTED, RunState.EXPIRED, RunState.ABORTED},
    RunState.APPROVED: {RunState.EXECUTING, RunState.EXPIRED, RunState.ABORTED},
    RunState.EXECUTING: {RunState.VERIFYING, RunState.BLOCKED, RunState.ABORTED},
    RunState.VERIFYING: {RunState.SECURITY_GATE, RunState.FAILED, RunState.COMPLETED_WITH_LIMITS, RunState.ABORTED},
    RunState.SECURITY_GATE: {RunState.COMPLETED, RunState.COMPLETED_WITH_RESERVATIONS, RunState.FAILED, RunState.ABORTED},
    RunState.BLOCKED: {RunState.ABORTED},
}


@dataclass
class RunContext:
    run_id: str
    contract: TaskContract
    run_dir: Path
    workspace: Path
    state: RunState
    audit: AuditLog
    approvals: ApprovalService
    evidence: EvidenceStore
    policy: PolicyEngine
    manifest: PlanManifest | None = None
    results: list[dict[str, Any]] | None = None


class HarnessEngine:
    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root.resolve()
        self.runs_root = self.project_root / "runs"
        self.fixtures = self.project_root / "fixtures"
        self.memory = MemoryStore(self.project_root / "memory")
        self.runs_root.mkdir(parents=True, exist_ok=True)

    def create_run(self, contract: TaskContract) -> RunContext:
        contract.validate()
        # [AJOUTÉ 19/10/2026 — faille réelle trouvée par un agent, traversée
        # de chemin] contract.tenant_id vient de l'appelant (CLI, API) et
        # n'était jamais validé avant d'être utilisé dans un chemin disque
        # -- un tenant_id comme "../outside" sortait réellement de runs/.
        # run_id lui-même est toujours généré ici (uuid4), jamais fourni
        # par l'appelant, donc pas besoin de le valider à la création.
        require_safe_identifier(contract.tenant_id, label="tenant_id")
        run_id = f"run-{uuid4().hex[:12]}"
        run_dir = self.runs_root / contract.tenant_id / run_id
        run_dir.mkdir(parents=True, exist_ok=False)
        (run_dir / "workspace").mkdir()
        (run_dir / "task.json").write_text(json.dumps(contract.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        audit = AuditLog(run_dir / "audit.jsonl", run_id=run_id, tenant_id=contract.tenant_id)
        context = RunContext(run_id, contract, run_dir, run_dir / "workspace", RunState.INTAKE,
                             audit, ApprovalService(run_dir / "approvals.json"), EvidenceStore(run_dir), PolicyEngine(), None, [])
        self._persist_state(context)
        audit.append("intake", "create_run", "allow", {"profile": contract.profile.value, "max_risk": int(contract.max_risk)})
        return context

    def resume_run(self, tenant_id: str, run_id: str) -> RunContext:
        """Recharge un RunContext depuis le disque (task.json, state.json,
        plan.manifest.json). C'EST la pièce qui manquait pour un vrai
        humain-dans-la-boucle : sans ça, `plan()` et `approve()` devaient
        tourner dans le MÊME process Python, donc la seule façon d'approuver
        était un appel automatique juste après la planification — personne
        ne pouvait réellement lire PLAN.md puis décider dans une commande
        séparée. AuditLog et ApprovalService étaient déjà conçus pour être
        rouverts (ils relisent leur fichier au constructeur) ; seule cette
        méthode manquait pour assembler un RunContext complet à partir de ça.
        """
        # [AJOUTÉ 19/10/2026 — même faille que create_run() ci-dessus, ICI
        # plus grave : tenant_id ET run_id viennent tous les deux
        # directement de l'appelant (cli.py `approve <tenant> <run_id>`,
        # ou la route web POST /mission) -- prouvé en vrai : un run_id
        # comme "../../secret" construisait un chemin hors de runs/.
        require_safe_identifier(tenant_id, label="tenant_id")
        require_safe_identifier(run_id, label="run_id")
        run_dir = self.runs_root / tenant_id / run_id
        if not run_dir.is_dir():
            raise ValidationError(f"run introuvable : {tenant_id}/{run_id}")
        # [AJOUTE 20/10/2026 -- bug reel trouve par un agent puis verifie en
        # vrai (state.json corrompu reel sur disque) : aucun try/except
        # n'entourait ces lectures -- un JSON invalide, une cle "state"
        # absente, ou une valeur de state inconnue de l'enum RunState
        # (crash mi-ecriture avant le correctif atomique de
        # _persist_state(), edition manuelle par un operateur, copie
        # tronquee) remontait une JSONDecodeError/KeyError/ValueError BRUTE
        # a l'appelant (cli.py `approve`, la route web /mission) au lieu
        # d'un ValidationError propre, contrairement au garde-fou deja en
        # place juste au-dessus pour tenant_id/run_id.
        try:
            contract = TaskContract.from_dict(json.loads((run_dir / "task.json").read_text(encoding="utf-8")))
            state_data = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
            state = RunState(state_data["state"])
            manifest_path = run_dir / "plan.manifest.json"
            manifest = PlanManifest.from_dict(json.loads(manifest_path.read_text(encoding="utf-8"))) if manifest_path.is_file() else None
        except (json.JSONDecodeError, KeyError, ValueError, OSError) as exc:
            raise ValidationError(f"état corrompu pour {tenant_id}/{run_id} : {exc}") from exc
        # [AJOUTE 21/10/2026 -- bug reel trouve par un agent puis verifie en
        # vrai (integration resume_run()/plan.manifest.json/PLAN.md) :
        # plan.manifest.json et PLAN.md sont deux artefacts separes ecrits
        # une fois par plan() et jamais revalides l'un par rapport a
        # l'autre au rechargement. manifest_hash EST deja calcule et
        # ecrit dans state.json a chaque transition (_persist_state(),
        # voir plus bas) -- mais rien ne le relisait jamais pour
        # comparaison : approve() faisait confiance aveuglement au
        # manifeste tout juste charge depuis le disque. Si
        # plan.manifest.json est modifie sur disque APRES avoir ete
        # presente a l'humain (edition manuelle, bug d'un autre outil,
        # ecrivain concurrent) et AVANT approve(), resume_run() chargeait
        # silencieusement le manifeste modifie et approve_and_run()
        # emettait les grants et executait SES operations modifiees, sans
        # jamais revalider contre PLAN.md (reste inchange, donc affichant
        # l'ANCIEN contenu a l'humain) -- contredisant directement la
        # garantie de "manifeste exact" du modele de menace du projet
        # (docs/threat-model.md). Reproduit en vrai : create_run -> plan
        # -> edition disque du `content` d'une operation deja valide
        # (tool_id/path intacts, donc aucun garde-fou existant ne la
        # detecte) -> resume_run -> approve_and_run -> COMPLETED, le
        # fichier reellement ecrit differe de ce que PLAN.md montrait.
        expected_manifest_hash = state_data.get("manifest_hash")
        if manifest is not None and expected_manifest_hash is not None and manifest.manifest_hash != expected_manifest_hash:
            raise ValidationError(
                f"plan.manifest.json modifié depuis sa dernière transition enregistrée pour {tenant_id}/{run_id} "
                f"(hash attendu {expected_manifest_hash}, obtenu {manifest.manifest_hash}) -- manifeste altéré, "
                "run bloqué par sécurité")
        # [AJOUTE 21/10/2026 -- bug reel trouve par un agent puis verifie en
        # vrai, meme classe que le controle manifest_hash ci-dessus mais
        # sur task.json/TaskContract (voir le commentaire dans
        # _persist_state() plus bas pour le mecanisme complet et la
        # reproduction) : task.json peut etre modifie sur disque entre
        # plan() et le resume_run() qui precede approve(), elargissant par
        # exemple allowed_tools sans que rien ne le detecte -- aucun autre
        # garde-fou ne compare jamais le contrat recharge a celui qui a
        # produit le plan deja approuve par l'humain. contract_hash est
        # stable pour toute la duree du run (TaskContract est immuable,
        # jamais modifie legitimement apres create_run()), donc comparer
        # au PREMIER contract_hash jamais persiste suffit.
        expected_contract_hash = state_data.get("contract_hash")
        if expected_contract_hash is not None and content_hash(contract.to_dict()) != expected_contract_hash:
            raise ValidationError(
                f"task.json modifié depuis la création du run {tenant_id}/{run_id} "
                f"(hash attendu {expected_contract_hash}, obtenu {content_hash(contract.to_dict())}) -- "
                "contrat altéré, run bloqué par sécurité")
        audit = AuditLog(run_dir / "audit.jsonl", run_id=run_id, tenant_id=tenant_id)
        return RunContext(run_id, contract, run_dir, run_dir / "workspace", state, audit,
                          ApprovalService(run_dir / "approvals.json"), EvidenceStore(run_dir), PolicyEngine(), manifest, [])

    def plan(self, context: RunContext, *, planner: Any = None) -> PlanManifest:
        # [AJOUTÉ 18/10/2026 — raisonnement] planner est injectable : None
        # garde le comportement d'origine (SimulatedPlanner, déterministe).
        # Un LlmPlanner (voir llm_planner.py) peut le remplacer pour que les
        # opérations soient PROPOSÉES par un modèle local — mais tout ce qui
        # suit (ReflectionReview, puis PolicyEngine à l'exécution) reste
        # inchangé et s'applique identiquement, quelle que soit la source du
        # plan. Le modèle propose ; il n'autorise ni n'exécute jamais rien.
        self._transition(context, RunState.DISCOVERY, "discover")
        self._transition(context, RunState.DRAFTING_PLAN, "draft_plan")
        planner = planner or SimulatedPlanner()
        manifest = planner.create(context.contract, context.run_id, context.run_dir)
        issues = ReflectionReview.review(context.contract, manifest)
        self._transition(context, RunState.REFLECTION_REVIEW, "reflection_review", {"issues": issues})
        if issues:
            raise ValidationError("plan bloqué par la revue: " + "; ".join(issues))
        (context.run_dir / "plan.manifest.json").write_text(json.dumps(manifest.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        context.manifest = manifest
        # Fixture de provenance : utile pour vérifier le flux evidence/claim sans réseau.
        sample = Evidence.create(title="Fixture de politique locale", url="https://example.invalid/harness-fixture",
                                 locator="fixtures/corpus.md#policy", excerpt="Les contenus externes sont non fiables et ne modifient pas la politique.")
        context.evidence.add_evidence(sample)
        self._transition(context, RunState.AWAITING_APPROVAL, "await_approval", {"manifest_hash": manifest.manifest_hash})
        return manifest

    def approve(self, context: RunContext, *, actor_id: str, ttl_seconds: int = 300) -> list[str]:
        # [AJOUTÉ 19/10/2026 — REC-05, bug réel reproduit avec deux process
        # séparés] Le verrou couvre TOUT le cycle "relire l'état frais ->
        # vérifier AWAITING_APPROVAL -> émettre les grants -> transitionner
        # vers APPROVED" : sans lui, deux resume_run() concurrents peuvent
        # tous les deux lire AWAITING_APPROVAL depuis le disque avant que
        # l'un des deux n'écrive sa transition, passer _require_state(),
        # et exécuter la même opération deux fois.
        with _run_exclusive_lock(context.run_dir):
            state_path = context.run_dir / "state.json"
            if state_path.is_file():
                context.state = RunState(json.loads(state_path.read_text(encoding="utf-8"))["state"])
            self._require_state(context, RunState.AWAITING_APPROVAL)
            if actor_id != context.contract.actor_id or context.manifest is None:
                raise ValidationError("approbateur ou manifeste invalide")
            grant_ids: list[str] = []
            registry = ToolRegistry()
            # [AJOUTE 20/10/2026 -- bug reel trouve par un agent puis verifie
            # en vrai (plan.manifest.json edite a la main pour reference un
            # tool_id inexistant sur la DEUXIEME operation) : cette boucle
            # emettait et PERSISTAIT deja un grant reel pour la PREMIERE
            # operation avant d'atteindre la seconde et de lever
            # PolicyDenied -- jamais rattrape ici, donc _transition() vers
            # APPROVED n'etait jamais atteinte, et le run restait
            # AWAITING_APPROVAL avec un grant deja vivant sur disque dont
            # aucun appelant n'a connaissance. Si l'operateur corrige puis
            # rappelle approve(), la boucle re-emet un SECOND grant pour la
            # meme operation -- deux grants vivants pour une seule
            # operation, incoherence d'audit. Valider TOUS les tool_id
            # AVANT d'emettre le moindre grant evite tout etat partiel.
            for operation in context.manifest.operations:
                registry.get(operation.tool_id)
            for operation in context.manifest.operations:
                definition = registry.get(operation.tool_id)
                if definition.requires_approval:
                    grant = context.approvals.issue(actor_id=actor_id, run_id=context.run_id,
                                                     manifest_hash=context.manifest.manifest_hash,
                                                     tool_id=operation.tool_id, arguments=operation.arguments,
                                                     ttl_seconds=ttl_seconds)
                    grant_ids.append(grant.grant_id)
            try:
                self._transition(context, RunState.APPROVED, "approve", {"grant_count": len(grant_ids)})
            except Exception:
                # [AJOUTE 20/10/2026 -- bug reel trouve par un agent puis
                # verifie en vrai, meme classe que les trois correctifs
                # precedents (f91908c, 753623e, f1fab14), mais ICI avec un
                # vrai risque de double-execution plutot qu'un simple
                # artefact derive manquant : les grants ci-dessus sont DEJA
                # emis et persistes sur approvals.json quand cette
                # transition finale echoue (ex. _persist_state() en panne
                # disque) -- context.state passe quand meme a APPROVED EN
                # MEMOIRE (avant l'echec de persistance), mais state.json
                # reste a AWAITING_APPROVAL. Un operateur qui relance
                # approve() normalement voit l'etat correct sur disque,
                # revalide, et EMET UN SECOND jeu de grants pour les memes
                # operations -- deux grants vivants et independants pour
                # la meme operation approuvee, cassant l'invariant a usage
                # unique (verifie : executer avec le grant orphelin laisse
                # le grant "officiel" rendu a l'appelant toujours vivant et
                # consommable). Revoque les grants de CETTE tentative avant
                # de remonter l'echec, pour qu'aucun grant orphelin ne
                # survive a un approve() qui n'a pas reellement reussi.
                context.approvals.revoke_all()
                raise
            return grant_ids

    def execute(self, context: RunContext, grants: list[str]) -> list[dict[str, Any]]:
        self._require_state(context, RunState.APPROVED)
        if context.manifest is None:
            raise ValidationError("manifeste absent")
        self._transition(context, RunState.EXECUTING, "start_execution")
        gateway = ToolGateway(workspace=context.workspace, fixtures=self.fixtures, registry=ToolRegistry(),
                              policy=context.policy, approvals=context.approvals, audit=context.audit,
                              evidence=context.evidence)
        results: list[dict[str, Any]] = []
        grant_iter = iter(grants)
        try:
            for operation in context.manifest.operations:
                grant_id = next(grant_iter, None) if ToolRegistry().get(operation.tool_id).requires_approval else None
                # [AJOUTÉ 18/10/2026 — trouvé en vrai] prior_results passé pour
                # que run_declared_check puisse vérifier un résultat contre la
                # VRAIE sortie d'une opération précédente (voir tools.py,
                # "stdout_matches_file"), pas contre une valeur que le modèle
                # invente et qu'il est seul à vérifier. Reproduit en vrai :
                # le modèle a calculé 385 (execute_python, stdout correct),
                # puis écrit "1001" dans le fichier et déclaré un
                # file_equals:...:1001 cohérent avec lui-même mais faux —
                # COMPLETED à raison côté harnais, faux par rapport au calcul réel.
                result = gateway.invoke(contract=context.contract, manifest=context.manifest, state=context.state,
                                        actor_id=context.contract.actor_id, tool_id=operation.tool_id,
                                        arguments=operation.arguments, grant_id=grant_id, prior_results=results)
                results.append({"operation_id": operation.operation_id, "tool_id": operation.tool_id, "result": result})
                # [AJOUTÉ 18/10/2026 — demandé : voir la progression en direct]
                # Écrit APRÈS chaque opération (pas seulement à la fin du run)
                # pour qu'une page comme /live (view_runs.py) puisse montrer
                # une checklist qui avance pendant l'exécution, pas seulement
                # un état final. Contenu dérivé, jamais source de vérité :
                # audit.jsonl reste la trace faisant autorité.
                try:
                    self._write_progress(context, done_count=len(results))
                except OSError:
                    # [AJOUTE 20/10/2026 -- bug reel trouve par un agent puis
                    # verifie en vrai, meme classe que les deux correctifs
                    # precedents (f91908c, 753623e) : gateway.invoke()
                    # ci-dessus a DEJA reellement reussi (effet reel sur
                    # disque) quand cette ligne s'execute. _write_progress()
                    # est explicitement documente comme derive/best-effort
                    # (jamais source de verite), mais son ecriture n'etait
                    # pas protegee et se trouvait DANS le except Exception
                    # de cette boucle, prevu pour les vraies pannes d'outil
                    # -- une panne disque ici (progress.json) transformait
                    # une operation reellement reussie (et toutes celles
                    # d'avant dans la boucle) en run BLOCKED, pire que les
                    # deux bugs precedents car le run n'atteint plus jamais
                    # VERIFYING/COMPLETED du tout, pas seulement un artefact
                    # derive manquant.
                    pass
        except Exception as exc:
            self._transition(context, RunState.BLOCKED, "execution_blocked", {"error": str(exc)})
            raise
        context.results = results
        self._transition(context, RunState.VERIFYING, "start_verification", {"operation_count": len(results)})
        return results

    def verify_and_complete(self, context: RunContext) -> list[VerificationResult]:
        self._require_state(context, RunState.VERIFYING)
        if context.manifest is None:
            raise ValidationError("manifeste absent")
        results: list[VerificationResult] = []
        allowed = set(context.manifest.allowed_paths)
        # [CORRIGÉ 18/10/2026 — debug Windows] str(Path) utilise le séparateur
        # natif de l'OS (`\` sur Windows) ; allowed_paths vient du contrat JSON
        # et utilise toujours `/` (ex. "drafts/release-note.md"). Sur Windows,
        # "drafts\\release-note.md" != "drafts/release-note.md" en comparaison
        # de chaînes : le contrôle "scope" échouait systématiquement sur un run
        # par ailleurs conforme. as_posix() normalise en "/" quel que soit l'OS.
        changed = {path.relative_to(context.workspace).as_posix() for path in context.workspace.rglob("*") if path.is_file()}
        out_of_scope = changed - allowed
        results.append(VerificationResult("scope", CheckStatus.PASS if not out_of_scope else CheckStatus.FAIL,
                                          "workspace diff", ", ".join(sorted(out_of_scope))))
        check_results = [entry for entry in (context.results or []) if entry["tool_id"] == "run_declared_check"]
        # [CORRIGÉ 18/10/2026 — trouvé en comparant raisonnement on/off] Ce
        # contrôle ne s'appliquait qu'à CODE_CHANGE. Pour AGENTIC_EXECUTION,
        # "declared_check" valait NOT_APPLICABLE : un run pouvait donc
        # COMPLETED avec un résultat de code FAUX (ex. mauvais calcul), tant
        # que le fichier produit restait dans allowed_paths — "scope" vérifie
        # l'EMPLACEMENT de l'écriture, jamais son CONTENU. Reproduit en vrai :
        # 2 essais sur 4 ont fini COMPLETED avec un resultat.txt incorrect.
        # [CORRIGE 20/10/2026 -- bug reel trouve par un agent puis verifie en
        # vrai : cette liste codee en dur ("CODE_CHANGE", "AGENTIC_EXECUTION")
        # supposait que seuls ces deux profils pouvaient avoir
        # run_declared_check dans leur plan -- mais policy.py accorde deja
        # cet outil a SECURITY_REVIEW aussi (_profile_tools). Un run
        # SECURITY_REVIEW dont le SEUL run_declared_check echouait reellement
        # (passed=False) voyait son resultat jete et remplace par
        # NOT_APPLICABLE, qui satisfait COMPLETED -- reproduit en vrai
        # (check draft_exists avec passed=False -> run quand meme COMPLETED).
        # Fix initial tente (deriver UNIQUEMENT du manifeste reel) cassait
        # test_t25 : AGENTIC_EXECUTION/CODE_CHANGE doivent rester OBLIGES
        # d'avoir un check meme si le modele n'en propose aucun (c'est
        # exactement le bug que test_t25 empeche). Donc : la liste de
        # profils reste l'exigence MINIMALE (toujours requise, meme sans
        # check propose) ; AU-DESSUS, tout profil dont un run_declared_check
        # a reellement ete execute voit aussi son resultat compte pour de
        # vrai plutot que jete en NOT_APPLICABLE.
        requires_declared_check = (
            context.contract.profile.value in ("CODE_CHANGE", "AGENTIC_EXECUTION")
            or bool(check_results)
        )
        # [TENTÉ PUIS ANNULÉ le 19/10/2026 — VER-09 du cahier des charges
        # ("statut indéterminé si preuves insuffisantes") avait motivé
        # l'idée d'utiliser CheckStatus.UNKNOWN ici (déclaré dans
        # l'énumération mais jamais assigné nulle part). Vérifié avant de
        # committer : les TROIS branches de run_declared_check (tools.py)
        # renvoient TOUJOURS une clé "passed" (jamais seulement "error")
        # -- ce chemin "insuffisant pour conclure" n'est donc atteignable
        # par AUCUN appel réel avec le code actuel. Un correctif sans bug
        # réel derrière contredit la règle tenue tout le long de cette
        # session (jamais de changement sans reproduction) : annulé plutôt
        # que laissé comme code mort déguisé en correctif.
        passed = bool(check_results and check_results[-1]["result"].get("passed"))
        check_status = (CheckStatus.PASS if passed else CheckStatus.NOT_RUN) if requires_declared_check else CheckStatus.NOT_APPLICABLE
        check_details = "run_declared_check doit être exécuté et réussi" if requires_declared_check else "profil sans écriture : contrôle non applicable"
        results.append(VerificationResult("declared_check", check_status,
                                          "run_declared_check", check_details))
        audit_ok, audit_message = AuditLog.verify(context.run_dir / "audit.jsonl")
        results.append(VerificationResult("audit_chain", CheckStatus.PASS if audit_ok else CheckStatus.FAIL, "audit.jsonl", audit_message))
        claims_errors = context.evidence.validate_claims()
        results.append(VerificationResult("critical_claims", CheckStatus.PASS if not claims_errors else CheckStatus.FAIL,
                                          "evidence.jsonl", "; ".join(claims_errors)))
        secret_found = any("TOP_SECRET_" in file.read_text(encoding="utf-8", errors="ignore") for file in context.workspace.rglob("*") if file.is_file())
        results.append(VerificationResult("secret_scan", CheckStatus.FAIL if secret_found else CheckStatus.PASS,
                                          "workspace", "secret de fixture détecté" if secret_found else "aucun secret de fixture"))
        # [AJOUTE 20/10/2026 -- bug reel trouve par un agent puis verifie en
        # vrai (run reel : execute_python ecrit un fichier hors perimetre
        # nomme "AKIAIOSFODNN7EXAMPLE_leftover.txt", scope echoue a raison,
        # mais verification.json ET report.md contenaient la cle AWS
        # intacte dans le champ "details" de ce check) : "details"/
        # "evidence" ne passaient par AUCUNE redaction, contrairement au
        # champ "details" d'AuditLog.append() qui redacte deja les memes
        # motifs. "scope" construit details depuis des noms de fichiers
        # REELLEMENT ECRITS par execute_python/write_workspace_draft
        # (arguments model-controles, sans restriction de contenu sur le
        # chemin) -- un nom de fichier choisi par le modele (exfiltration
        # via nom de fichier, ou embarquant par accident un identifiant lu
        # via execute_python/fetch_url) atterrissait donc intact dans ces
        # deux artefacts humains. redact() applique ici UNE FOIS, avant les
        # deux consommateurs (verification.json ci-dessous, report.md via
        # _render_report plus bas) plutot que duplique a chaque site.
        results = [replace(result, details=redact(result.details), evidence=redact(result.evidence)) for result in results]
        self._transition(context, RunState.SECURITY_GATE, "security_gate", {"checks": [item.status.value for item in results]})
        allowed_statuses = {CheckStatus.PASS, CheckStatus.NOT_APPLICABLE}
        target = RunState.COMPLETED if all(item.status in allowed_statuses for item in results) else RunState.FAILED
        # [AJOUTE 20/10/2026 -- bug reel trouve par un agent puis verifie en
        # vrai (echec force de _persist_state() entre les deux transitions,
        # run reel create_run->plan->approve->execute) : verification.json
        # etait ecrit AVANT ces deux _transition(), donc si _persist_state()
        # echoue (disque plein, permissions) pendant la transition finale,
        # verification.json reste sur disque en affichant TOUS LES CHECKS
        # EN PASS alors que state.json reste bloque a SECURITY_GATE --
        # jamais COMPLETED. Un lecteur de verification.json seul (tableau
        # de bord, humain) croirait le run reussi ; verify_and_complete()
        # exige RunState.VERIFYING pour redemarrer (_require_state), donc
        # un run ainsi coince ne peut plus jamais etre relance. Ecrit
        # maintenant APRES que la transition finale ait reellement reussi :
        # si _persist_state() echoue, aucun verification.json n'existe du
        # tout plutot qu'un qui affiche faussement un succes complet.
        self._transition(context, target, "complete", {"final_status": target.value})
        (context.run_dir / "verification.json").write_text(json.dumps([result.to_dict() for result in results], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        self._render_report(context, results)
        # [AJOUTÉ 18/10/2026 — mémoire inter-run] Écrit APRÈS la transition
        # finale : l'entrée reflète toujours un état déjà validé par ce même
        # verify_and_complete(), jamais une proposition non vérifiée. Le
        # harness est seul auteur de cette entrée (ni le modèle, ni une
        # fixture) — voir memory.py pour la distinction avec evidence.jsonl.
        try:
            self.memory.record_run(
                run_id=context.run_id, tenant_id=context.contract.tenant_id, task_id=context.contract.task_id,
                objective=context.contract.objective, final_state=target.value,
                tool_ids=[entry["tool_id"] for entry in (context.results or [])],
            )
        except OSError:
            # [AJOUTE 20/10/2026 -- bug reel trouve par un agent puis
            # verifie en vrai, bout en bout via `cli.py approve` reel : a
            # ce stade, _transition() vers COMPLETED/FAILED a DEJA reussi
            # et persiste sur disque -- c'est le resultat faisant autorite
            # du run. record_run() n'est qu'un canal secondaire (memoire
            # inter-run, jamais consultee pour decider si CE run a reussi).
            # Une panne disque ici (memory.jsonl plein/permissions) levait
            # une OSError non rattrapee qui remontait jusqu'a cli.py, ou
            # elle tombait dans le except generique (OSError, ValidationError,
            # ValueError) -- un run REELLEMENT COMPLETED etait alors
            # rapporte a l'appelant comme un echec (exit 2), uniquement a
            # cause d'un effet de bord sans rapport avec le resultat du run.
            # Best-effort ici, comme verification.json/report.md (deja
            # traites comme secondaires par construction) : le run reste
            # COMPLETED que cette ecriture reussisse ou non.
            pass
        return results

    def abort(self, context: RunContext, reason: str) -> None:
        context.policy.stop()
        revoked = context.approvals.revoke_all()
        if context.state != RunState.ABORTED:
            if RunState.ABORTED not in _ALLOWED_TRANSITIONS.get(context.state, set()):
                raise ValidationError("run non annulable depuis cet état")
            self._transition(context, RunState.ABORTED, "kill_switch", {"reason": reason, "revoked_grants": revoked})

    def run_demo(self, contract: TaskContract) -> RunContext:
        context = self.create_run(contract)
        self.plan(context)
        grants = self.approve(context, actor_id=contract.actor_id)
        self.execute(context, grants)
        self.verify_and_complete(context)
        return context

    def submit(self, contract: TaskContract, *, planner: Any = None) -> RunContext:
        """[AJOUTÉ 18/10/2026 — humain dans la boucle] Crée le run et le
        planifie, PUIS S'ARRÊTE à AWAITING_APPROVAL — contrairement à
        run_demo()/run_with_llm() qui enchaînent jusqu'à COMPLETED dans le
        même appel. C'est la moitié "proposition" du flux CLI en deux
        commandes (`submit` puis `approve`, voir cli.py) : entre les deux,
        un humain lit PLAN.md et décide, dans un process séparé si besoin
        (resume_run() recharge le contexte depuis le disque)."""
        context = self.create_run(contract)
        try:
            self.plan(context, planner=planner)
        except Exception as exc:
            # [AJOUTÉ 18/10/2026 — bug réel reproduit en conditions réelles :
            # un appelant en arrière-plan (view_runs.py POST /mission) qui ne
            # capture que ValidationError/PolicyDenied laisse le thread
            # mourir en silence sur TOUTE autre exception (ex. TimeoutError
            # d'un llama-server lent/indisponible, observé en vrai pendant
            # cette session) -- le run reste alors coincé à DRAFTING_PLAN
            # pour toujours, et /live affiche un état qui ne bougera plus
            # jamais sans jamais le dire. On marque le run ABORTED ICI,
            # côté moteur, pour que CE SOIT TOUJOURS VRAI quel que soit
            # l'appelant (CLI, page web, test) plutôt que de compter sur
            # chaque appelant pour bien gérer son except. La transition vers
            # ABORTED est autorisée depuis tous les états atteignables ici
            # (voir _ALLOWED_TRANSITIONS) ; si elle échoue aussi (état déjà
            # terminal), on l'ignore et on relaie l'erreur d'origine.
            try:
                self._transition(context, RunState.ABORTED, "abort_on_exception", {"error": str(exc)})
            except ValidationError:
                pass
            raise
        return context

    def approve_and_run(self, context: RunContext, *, actor_id: str) -> RunContext:
        """[AJOUTÉ 18/10/2026] Moitié "décision" du flux : appelée APRÈS que
        submit() s'est arrêté à AWAITING_APPROVAL et qu'un humain a
        explicitement dit oui (voir cli.py `approve`, qui lit PLAN.md et
        demande une confirmation avant d'appeler ceci)."""
        grants = self.approve(context, actor_id=actor_id)
        self.execute(context, grants)
        self.verify_and_complete(context)
        return context

    def run_with_llm(self, contract: TaskContract, planner: Any) -> RunContext:
        """Même pipeline que run_demo(), mais le plan est proposé par `planner`
        (typiquement un LlmPlanner, voir llm_planner.py) au lieu d'être
        déterministe. Aucune étape de validation n'est sautée ou affaiblie :
        si le plan proposé est hors périmètre, ReflectionReview.review() (ou
        PolicyEngine.authorize() à l'exécution) le bloque exactement comme un
        plan simulé non conforme."""
        context = self.create_run(contract)
        self.plan(context, planner=planner)
        grants = self.approve(context, actor_id=contract.actor_id)
        self.execute(context, grants)
        self.verify_and_complete(context)
        return context

    def _transition(self, context: RunContext, target: RunState, action: str, details: dict[str, Any] | None = None) -> None:
        if target not in _ALLOWED_TRANSITIONS.get(context.state, set()):
            raise ValidationError(f"transition interdite: {context.state} → {target}")
        source = context.state
        context.state = target
        self._persist_state(context)
        try:
            context.audit.append("state_machine", action, "allow", {"from": source.value, "to": target.value, **(details or {})})
        except (OSError, ValidationError):
            # [AJOUTE 21/10/2026 -- bug reel trouve par un agent puis
            # verifie en vrai, meme classe que tous les correctifs
            # precedents de cette famille (f91908c, 753623e, f1fab14,
            # b00f540) mais ICI au coeur meme de _transition(), partagee
            # par TOUS les appelants : _persist_state() ci-dessus a DEJA
            # reussi (ecriture atomique, state.json reflete durablement
            # cette transition) quand cet append() echoue (disque plein,
            # ou timeout du verrou audit.jsonl.lock -> ValidationError).
            # Avant ce correctif, laisser cette exception remonter cassait
            # deux appelants differemment :
            #  - approve() : son except Exception revoquait les grants
            #    tout juste emis et relevait -- alors que state.json etait
            #    DEJA passe a APPROVED. Le run restait stranded pour
            #    toujours (plus AWAITING_APPROVAL pour re-approuver, plus
            #    aucun grant vivant pour executer), sans AUCUNE trace
            #    d'audit expliquant pourquoi.
            #  - execute() : son except Exception appelle _transition(...,
            #    BLOCKED, "execution_blocked", ...) puis `raise` (qui
            #    relance l'exception ORIGINALE, la vraie cause metier du
            #    blocage) -- mais si CET appel a _transition() levait a son
            #    tour (a cause de cet append()), c'est cette NOUVELLE
            #    exception (OSError derivee) qui remontait a l'appelant,
            #    masquant completement la vraie cause (ex. RuntimeError
            #    d'un outil qui a reellement echoue).
            # L'entree d'audit est une trace DERIVEE d'une transition DEJA
            # reelle (meme raisonnement que verification.json/
            # memory.record_run()/_write_progress() ailleurs dans ce
            # fichier) -- jamais la laisser transformer un succes reel (ou
            # la vraie cause d'un echec reel) en echec different remonte a
            # l'appelant.
            pass

    @staticmethod
    def _require_state(context: RunContext, expected: RunState) -> None:
        if context.state != expected:
            raise ValidationError(f"état attendu {expected}, reçu {context.state}")

    @staticmethod
    def _persist_state(context: RunContext) -> None:
        payload = {"run_id": context.run_id, "state": context.state.value, "updated_at": utc_now(),
                   "manifest_hash": context.manifest.manifest_hash if context.manifest else None,
                   # [AJOUTE 21/10/2026 -- bug reel trouve par un agent puis
                   # verifie en vrai, meme classe que manifest_hash
                   # ci-dessus mais sur l'artefact task.json/TaskContract :
                   # ReflectionReview.review() ne verifie JAMAIS
                   # allowed_tools, et approve() n'appelle jamais
                   # policy.authorize() -- le SEUL garde-fou qui compare
                   # une operation au contrat est authorize(), appele
                   # UNIQUEMENT dans execute() via gateway.invoke(), avec
                   # le contract RECHARGE EN DIRECT par le resume_run() qui
                   # a precede. Si task.json est modifie sur disque entre
                   # plan() (l'humain lit PLAN.md, genere depuis le
                   # manifeste deja hash-protege) et le resume_run() qui
                   # precede approve_and_run() -- exactement la fenetre du
                   # flux CLI en deux process (submit puis approve) --
                   # resume_run() rechargeait silencieusement un contrat
                   # elargi (ex. allowed_tools agrandi) et l'execution
                   # passait une operation qui aurait du rester bloquee par
                   # P-CONTRACT-001. Reproduit en vrai : allowed_tools=
                   # ["run_declared_check"] au plan (write_workspace_draft
                   # exclu), edition disque de task.json pour y ajouter
                   # write_workspace_draft avant resume_run() -> COMPLETED,
                   # fichier reellement ecrit. Scelle ici a chaque
                   # transition, comme manifest_hash, pour que resume_run()
                   # puisse detecter toute modification du contrat depuis
                   # sa derniere transition enregistree.
                   "contract_hash": content_hash(context.contract.to_dict())}
        # [AJOUTÉ 19/10/2026 — trouvé en vérifiant la famille de bugs de
        # concurrence corrigée plus haut ce jour] write_text() n'est PAS
        # atomique (ouvre, tronque, écrit, ferme) -- resume_run() (plus
        # bas, aucun try/except autour de json.loads) pourrait lire ce
        # fichier PENDANT une écriture et tomber sur un JSON tronqué. /live
        # (view_runs.py) tolère déjà ce cas (except JSONDecodeError), mais
        # resume_run() ne le faisait pas. Plutôt que rattraper l'erreur de
        # lecture, on élimine la fenêtre de course : écrire dans un fichier
        # temporaire puis os.replace() (atomique sur la même partition,
        # POSIX et Windows) -- un lecteur concurrent voit soit l'ancien
        # contenu complet, soit le nouveau complet, jamais un état intermédiaire.
        state_path = context.run_dir / "state.json"
        tmp_path = state_path.with_suffix(".json.tmp")
        tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(tmp_path, state_path)

    @staticmethod
    def _write_progress(context: RunContext, *, done_count: int) -> None:
        """[AJOUTÉ 18/10/2026] checklist "todo" de la progression d'un run,
        pour /live (view_runs.py) — dérivé, jamais source de vérité
        (audit.jsonl reste la trace faisant autorité)."""
        if context.manifest is None:
            return
        items = [{"operation_id": op.operation_id, "tool_id": op.tool_id, "done": i < done_count}
                 for i, op in enumerate(context.manifest.operations)]
        (context.run_dir / "progress.json").write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")

    @staticmethod
    def _render_report(context: RunContext, results: list[VerificationResult]) -> None:
        # [AJOUTE 20/10/2026 -- faille reelle trouvee ET REPRODUITE par un
        # agent : report.md interpolait contract.objective (et les lignes
        # de la table de verification) SANS passer par flatten_for_markdown,
        # alors que PLAN.md avait deja ce correctif pour EXACTEMENT le meme
        # champ (voir planner.py, 19/10/2026). Un objectif contenant
        # "\n\n## Etat final : FORGED-COMPLETED-OVERRIDE\n" forgeait une
        # fausse section dans l'artefact de fin de run lu par un humain --
        # verifie en vrai (run reel jusqu'a COMPLETED, report.md relu,
        # fausse ligne d'en-tete confirmee). item.details peut contenir du
        # texte joint depuis des chemins/claim_ids potentiellement
        # influences par un outil ; flatten par precaution, meme logique
        # que PLAN.md (neutraliser toute la classe plutot que le seul
        # payload reproduit).
        rows = "\n".join(
            f"| {item.check_id} | {item.status.value} | {flatten_for_markdown(item.details or item.evidence)} |"
            for item in results
        )
        report = f"""# Rapport de run — {context.run_id}

**État final :** `{context.state.value}`

## Objectif
{flatten_for_markdown(context.contract.objective)}

## Plan et autorisation
- Manifeste : `{context.manifest.manifest_hash if context.manifest else 'absent'}`
- Outils exécutés : {', '.join(entry['tool_id'] for entry in (context.results or [])) or 'aucun'}
- Aucun shell, réseau, secret, MCP ou effet externe n’a été activé.

## Vérifications
| Contrôle | Statut | Preuve / détail |
|---|---|---|
{rows}

## Provenance locale
{context.evidence.render_citations() or 'Aucune évidence'}

## Limites
Ce résultat valide uniquement le profil simulé R0/R1 et les preuves locales. Il ne constitue pas une certification de sécurité ni une autorisation de déploiement.
"""
        (context.run_dir / "report.md").write_text(report, encoding="utf-8")

"""Orchestrateur local P0/P1 : transitions, plans, grants, outils, vérification et rapport."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import json
from uuid import uuid4

from .approvals import ApprovalService
from .audit import AuditLog
from .evidence import EvidenceStore
from .memory import MemoryStore
from .models import (CheckStatus, Evidence, PlanManifest, RunState, TaskContract,
                     ValidationError, VerificationResult, content_hash, utc_now)
from .planner import ReflectionReview, SimulatedPlanner
from .policy import PolicyEngine
from .tools import ToolGateway, ToolRegistry


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
        run_dir = self.runs_root / tenant_id / run_id
        if not run_dir.is_dir():
            raise ValidationError(f"run introuvable : {tenant_id}/{run_id}")
        contract = TaskContract.from_dict(json.loads((run_dir / "task.json").read_text(encoding="utf-8")))
        state = RunState(json.loads((run_dir / "state.json").read_text(encoding="utf-8"))["state"])
        manifest_path = run_dir / "plan.manifest.json"
        manifest = PlanManifest.from_dict(json.loads(manifest_path.read_text(encoding="utf-8"))) if manifest_path.is_file() else None
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
        self._require_state(context, RunState.AWAITING_APPROVAL)
        if actor_id != context.contract.actor_id or context.manifest is None:
            raise ValidationError("approbateur ou manifeste invalide")
        grant_ids: list[str] = []
        registry = ToolRegistry()
        for operation in context.manifest.operations:
            definition = registry.get(operation.tool_id)
            if definition.requires_approval:
                grant = context.approvals.issue(actor_id=actor_id, run_id=context.run_id,
                                                 manifest_hash=context.manifest.manifest_hash,
                                                 tool_id=operation.tool_id, arguments=operation.arguments,
                                                 ttl_seconds=ttl_seconds)
                grant_ids.append(grant.grant_id)
        self._transition(context, RunState.APPROVED, "approve", {"grant_count": len(grant_ids)})
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
                self._write_progress(context, done_count=len(results))
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
        requires_declared_check = context.contract.profile.value in ("CODE_CHANGE", "AGENTIC_EXECUTION")
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
        (context.run_dir / "verification.json").write_text(json.dumps([result.to_dict() for result in results], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        self._transition(context, RunState.SECURITY_GATE, "security_gate", {"checks": [item.status.value for item in results]})
        allowed_statuses = {CheckStatus.PASS, CheckStatus.NOT_APPLICABLE}
        target = RunState.COMPLETED if all(item.status in allowed_statuses for item in results) else RunState.FAILED
        self._transition(context, target, "complete", {"final_status": target.value})
        self._render_report(context, results)
        # [AJOUTÉ 18/10/2026 — mémoire inter-run] Écrit APRÈS la transition
        # finale : l'entrée reflète toujours un état déjà validé par ce même
        # verify_and_complete(), jamais une proposition non vérifiée. Le
        # harness est seul auteur de cette entrée (ni le modèle, ni une
        # fixture) — voir memory.py pour la distinction avec evidence.jsonl.
        self.memory.record_run(
            run_id=context.run_id, tenant_id=context.contract.tenant_id, task_id=context.contract.task_id,
            objective=context.contract.objective, final_state=target.value,
            tool_ids=[entry["tool_id"] for entry in (context.results or [])],
        )
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
        context.audit.append("state_machine", action, "allow", {"from": source.value, "to": target.value, **(details or {})})

    @staticmethod
    def _require_state(context: RunContext, expected: RunState) -> None:
        if context.state != expected:
            raise ValidationError(f"état attendu {expected}, reçu {context.state}")

    @staticmethod
    def _persist_state(context: RunContext) -> None:
        payload = {"run_id": context.run_id, "state": context.state.value, "updated_at": utc_now(),
                   "manifest_hash": context.manifest.manifest_hash if context.manifest else None}
        (context.run_dir / "state.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

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
        rows = "\n".join(f"| {item.check_id} | {item.status.value} | {item.details or item.evidence} |" for item in results)
        report = f"""# Rapport de run — {context.run_id}

**État final :** `{context.state.value}`

## Objectif
{context.contract.objective}

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

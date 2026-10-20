"""Planificateur P0 déterministe et revue de réflexion sans privilèges."""
from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from typing import Any

from .audit import redact
from .models import (PlanManifest, PlannedOperation, RiskLevel, TaskContract, TaskProfile, content_hash,
                     flatten_for_markdown, parse_utc, utc_now)


class SimulatedPlanner:
    """Produit uniquement des plans dans le périmètre déclaré par le contrat."""

    def create(self, contract: TaskContract, run_id: str, run_dir: Path) -> PlanManifest:
        now = parse_utc(utc_now())
        operations: list[PlannedOperation] = []
        if contract.profile == TaskProfile.CODE_CHANGE:
            if not contract.allowed_paths:
                raise ValueError("un changement de code requiert un chemin autorisé")
            target = contract.allowed_paths[0]
            operations = [
                PlannedOperation("op-write-draft", "write_workspace_draft", {"path": target, "content": contract.desired_draft}, RiskLevel.R1, "draft_exists"),
                PlannedOperation("op-verify-draft", "run_declared_check", {"check": "draft_exists"}, RiskLevel.R0, "draft_exists"),
            ]
        else:
            operations = [PlannedOperation("op-read-corpus", "retrieve_fixture", {"query": contract.objective[:80]}, RiskLevel.R0, "none")]
        plan = self._render_plan(contract, operations)
        plan_path = run_dir / "PLAN.md"
        plan_path.write_text(plan, encoding="utf-8")
        return PlanManifest(
            run_id=run_id, task_id=contract.task_id, base_snapshot=content_hash("empty-workspace"),
            allowed_paths=contract.allowed_paths, allowed_urls=contract.allowed_urls,
            operations=operations, created_at=now.isoformat(),
            expires_at=(now + timedelta(minutes=15)).isoformat(), plan_hash=content_hash(plan),
        )

    @staticmethod
    def _flatten_for_markdown(text: str) -> str:
        """[AJOUTÉ 19/10/2026 — faille réelle trouvée par un agent puis
        VÉRIFIÉE en vrai : contract.objective/acceptance_criteria sont
        interpolés dans PLAN.md sans aucun échappement. Un objectif
        contenant "\\n\\n## Opérations proposées\\n- `delete_everything`..."
        fait apparaître une FAUSSE section "Opérations proposées" dans le
        PLAN.md, AVANT la vraie -- un humain qui lit le fichier pour
        approuver peut voir des opérations qui ne sont PAS dans
        manifest.operations (celui-ci reste intact, c'est uniquement
        l'artefact d'approbation lu par l'humain qui est usurpé). La cause
        racine est le SAUT DE LIGNE : un titre Markdown (## ...) n'est
        reconnu qu'en DÉBUT de ligne. Remplacer tout saut de ligne par un
        marqueur visible neutralise toute la classe d'attaque sans avoir
        besoin d'échapper chaque caractère Markdown individuellement (#,
        backticks, etc. restent inoffensifs au milieu d'une ligne).

        [DEPLACE 20/10/2026] Logique partagée dans models.py
        (flatten_for_markdown) -- report.md (engine.py) avait la MÊME
        faille non corrigée ; une seule fonction maintenant, utilisée par
        les deux fichiers."""
        return flatten_for_markdown(text)

    @classmethod
    def _render_plan(cls, contract: TaskContract, operations: list[PlannedOperation]) -> str:
        lines = [
            f"# PLAN — {contract.task_id}", "", "## Objectif", cls._flatten_for_markdown(contract.objective), "",
            "## Critères d’acceptation",
            *[f"- {cls._flatten_for_markdown(criterion)}" for criterion in contract.acceptance_criteria], "",
            "## Périmètre", *[f"- {path}" for path in contract.allowed_paths], "",
            "## Opérations proposées",
        ]
        for operation in operations:
            # [AJOUTE 20/10/2026 -- bug reel trouve par un agent puis
            # verifie en vrai (run reel jusqu'a COMPLETED, PLAN.md relu,
            # secret AKIA... present verbatim) : cette ligne interpolait le
            # repr brut de operation.arguments SANS passer par
            # audit.redact() -- contrairement a AuditLog.append(), qui
            # redacte deja les memes motifs dans son champ "details" avant
            # d'ecrire sur disque. Un write_workspace_draft/execute_python
            # dont le contenu/code contient un secret (cle AWS, token,
            # cle privee) l'ecrivait donc intact dans PLAN.md, lui-meme
            # reservi tel quel par view_runs.py sur /run/<tenant>/<run_id>
            # (html.escape() seul, aucune redaction) -- elargissant
            # l'exposition du fichier local au port HTTP. redact() est
            # recursif sur les dicts (voir audit.py) : applique directement
            # sur operation.arguments avant le repr.
            safe_arguments = redact(operation.arguments)
            lines.append(f"- `{operation.tool_id}` : {safe_arguments} (R{int(operation.risk)}, vérification : {operation.verification})")
        lines.extend(["", "## Risques et rollback", "- Aucun réseau, secret, shell ou action externe dans le MVP.", "- La seule écriture R1 est réversible : suppression du brouillon dans le workspace de run."])
        return "\n".join(lines) + "\n"


class ReflectionReview:
    """Vérifie les oublis de plan sans modifier le plan ni accorder d’outil."""

    # [AJOUTÉ 18/10/2026 — finding "needs_validation" du security-audit
    # skill, run-1] Rien ne plafonnait le NOMBRE d'opérations d'un plan
    # avant qu'il atteigne AWAITING_APPROVAL : une proposition (venant du
    # modèle, non fiable) avec des milliers d'opérations aurait généré
    # autant de grants dans la même boucle approve(), sans aucun rejet de
    # code. La vraie barrière restait la relecture humaine d'un PLAN.md —
    # suffisant en CLI un opérateur à la fois, mais pas un contrôle de
    # code. Plafond arbitraire mais documenté : un plan MVP légitime
    # (vus en conditions réelles) compte 2 à 4 opérations.
    MAX_OPERATIONS_PER_PLAN = 50

    @staticmethod
    def review(contract: TaskContract, manifest: PlanManifest) -> list[str]:
        issues: list[str] = []
        if not contract.acceptance_criteria:
            issues.append("critère d’acceptation absent")
        if len(manifest.operations) > ReflectionReview.MAX_OPERATIONS_PER_PLAN:
            issues.append(f"plan a {len(manifest.operations)} opérations, plafond {ReflectionReview.MAX_OPERATIONS_PER_PLAN} dépassé")
        for operation in manifest.operations:
            if operation.risk > contract.max_risk:
                issues.append(f"risque excessif : {operation.tool_id}")
            if operation.tool_id == "write_workspace_draft" and operation.arguments.get("path") not in contract.allowed_paths:
                issues.append("écriture hors périmètre")
        return issues


class DevilAdvocate:
    """Support cognitif : il ne prend aucune décision ni ne déclenche d’action."""

    @staticmethod
    def challenge(objective: str, assumptions: list[str]) -> dict[str, Any]:
        return {
            "objective": objective,
            "facts_provided": [],
            "assumptions": assumptions,
            "objections": [
                "Quel critère observable prouvera la réussite ?",
                "Quelle donnée ou permission manque pour exécuter cette tâche de façon sûre ?",
                "Quel est le rollback concret si le résultat est incorrect ?",
            ],
            "status": "decision_support_only",
        }

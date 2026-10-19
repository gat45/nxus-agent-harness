"""Contrats internes du harness.

Le modèle ne possède aucune autorité : ces objets sont validés et consommés par
le plan de contrôle déterministe.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import IntEnum, StrEnum
from hashlib import sha256
import json
from typing import Any
from uuid import uuid4


class HarnessError(Exception):
    """Erreur contrôlée, sans détail sensible."""


class ValidationError(HarnessError):
    """Contrat ou schéma invalide."""


class PolicyDenied(HarnessError):
    """Appel refusé par la politique."""


class RunState(StrEnum):
    INTAKE = "INTAKE"
    CLARIFYING = "CLARIFYING"
    DISCOVERY = "DISCOVERY"
    DRAFTING_PLAN = "DRAFTING_PLAN"
    REFLECTION_REVIEW = "REFLECTION_REVIEW"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    APPROVED = "APPROVED"
    EXECUTING = "EXECUTING"
    VERIFYING = "VERIFYING"
    SECURITY_GATE = "SECURITY_GATE"
    COMPLETED = "COMPLETED"
    COMPLETED_WITH_RESERVATIONS = "COMPLETED_WITH_RESERVATIONS"
    COMPLETED_WITH_LIMITS = "COMPLETED_WITH_LIMITS"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"
    ABORTED = "ABORTED"


class TaskProfile(StrEnum):
    QA_READONLY = "QA_READONLY"
    DECISION_CHALLENGE = "DECISION_CHALLENGE"
    RESEARCH_READONLY = "RESEARCH_READONLY"
    CODE_CHANGE = "CODE_CHANGE"
    SECURITY_REVIEW = "SECURITY_REVIEW"
    EXTERNAL_ACTION = "EXTERNAL_ACTION"
    # [AJOUTÉ 18/10/2026 — R2] Seul profil qui donne accès à execute_python
    # et fetch_url (voir policy.py, tools.py, docs/threat-model.md). Isolé
    # dans son propre profil plutôt qu'ajouté à CODE_CHANGE : une tâche qui
    # ne demande qu'un brouillon de fichier ne doit jamais, par défaut,
    # pouvoir exécuter du code ou toucher le réseau.
    AGENTIC_EXECUTION = "AGENTIC_EXECUTION"


class RiskLevel(IntEnum):
    R0 = 0
    R1 = 1
    R2 = 2
    R3 = 3
    R4 = 4


class CheckStatus(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    NOT_RUN = "not_run"
    BLOCKED = "blocked"
    NOT_APPLICABLE = "not_applicable"
    UNKNOWN = "unknown"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def content_hash(value: Any) -> str:
    if not isinstance(value, str):
        value = canonical_json(value)
    return sha256(value.encode("utf-8")).hexdigest()


def parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


# [AJOUTÉ 19/10/2026 — trouvé en relisant models.py/llm_planner.py après
# les correctifs de concurrence du jour] Cette chaîne était dupliquée TROIS
# fois, codée en dur indépendamment dans TaskContract (deux fois ici) et
# dans llm_planner.py (comparaison pour décider d'afficher ou non
# desired_draft comme un vrai contenu demandé -- voir ce fichier, 18/10/2026,
# le bug réel qui avait fait échouer une mission SSRF en recopiant ce texte
# tel quel). Si quelqu'un changeait ce défaut ici sans toucher la
# comparaison codée en dur dans llm_planner.py, ce bug reviendrait en
# silence. Une seule constante nommée, importée là où elle est comparée.
DEFAULT_DESIRED_DRAFT = "Brouillon contrôlé par le harness."


@dataclass(frozen=True)
class TaskContract:
    task_id: str
    tenant_id: str
    actor_id: str
    objective: str
    acceptance_criteria: list[str]
    profile: TaskProfile
    max_risk: RiskLevel
    allowed_paths: list[str] = field(default_factory=list)
    allowed_tools: list[str] = field(default_factory=list)
    # [AJOUTÉ 18/10/2026 — R2] Allowlist exacte d'URLs pour fetch_url, même
    # logique que allowed_paths pour write_workspace_draft : une URL hors de
    # cette liste est refusée par PolicyEngine, jamais par "approximation de
    # domaine" (pas de wildcard, pas de sous-domaine implicite).
    allowed_urls: list[str] = field(default_factory=list)
    data_classification: str = "synthetic"
    budget_seconds: int = 60
    desired_draft: str = DEFAULT_DESIRED_DRAFT

    def validate(self) -> None:
        if not self.task_id or not self.tenant_id or not self.actor_id:
            raise ValidationError("task_id, tenant_id et actor_id sont requis")
        if not self.objective.strip() or not self.acceptance_criteria:
            raise ValidationError("objectif et critère d’acceptation sont requis")
        if self.budget_seconds <= 0 or self.budget_seconds > 3600:
            raise ValidationError("budget_seconds doit être compris entre 1 et 3600")
        # [AJOUTÉ 18/10/2026 — R2] Le MVP original refusait tout contrat
        # au-delà de R1 ; execute_python et fetch_url sont R2 (voir
        # docs/threat-model.md, section "Conditions avant un connecteur R2+"
        # pour ce qui a été vérifié avant cet élargissement).
        if self.max_risk > RiskLevel.R2:
            raise ValidationError("le MVP refuse les contrats au-delà de R2")
        for path in self.allowed_paths:
            if path.startswith("/") or ".." in path.split("/"):
                raise ValidationError("un chemin autorisé doit être relatif et normalisé")

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "TaskContract":
        try:
            result = cls(
                task_id=value["task_id"], tenant_id=value["tenant_id"], actor_id=value["actor_id"],
                objective=value["objective"], acceptance_criteria=list(value["acceptance_criteria"]),
                profile=TaskProfile(value["profile"]), max_risk=RiskLevel(value["max_risk"]),
                allowed_paths=list(value.get("allowed_paths", [])),
                allowed_tools=list(value.get("allowed_tools", [])),
                allowed_urls=list(value.get("allowed_urls", [])),
                data_classification=value.get("data_classification", "synthetic"),
                budget_seconds=int(value.get("budget_seconds", 60)),
                desired_draft=value.get("desired_draft", DEFAULT_DESIRED_DRAFT),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValidationError("TaskContract invalide") from exc
        result.validate()
        return result

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["profile"] = self.profile.value
        result["max_risk"] = int(self.max_risk)
        return result


@dataclass(frozen=True)
class PlannedOperation:
    operation_id: str
    tool_id: str
    arguments: dict[str, Any]
    risk: RiskLevel
    verification: str

    def to_dict(self) -> dict[str, Any]:
        return {"operation_id": self.operation_id, "tool_id": self.tool_id,
                "arguments": self.arguments, "risk": int(self.risk),
                "verification": self.verification}

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "PlannedOperation":
        return cls(operation_id=value["operation_id"], tool_id=value["tool_id"],
                   arguments=value["arguments"], risk=RiskLevel(value["risk"]),
                   verification=value["verification"])


@dataclass(frozen=True)
class PlanManifest:
    run_id: str
    task_id: str
    base_snapshot: str
    allowed_paths: list[str]
    operations: list[PlannedOperation]
    created_at: str
    expires_at: str
    plan_hash: str
    # [AJOUTÉ 18/10/2026 — R2] Même défense en profondeur que allowed_paths :
    # PolicyEngine vérifie fetch_url contre CE champ ET contract.allowed_urls.
    allowed_urls: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id, "task_id": self.task_id, "base_snapshot": self.base_snapshot,
            "allowed_paths": self.allowed_paths, "allowed_urls": self.allowed_urls,
            "operations": [operation.to_dict() for operation in self.operations],
            "created_at": self.created_at, "expires_at": self.expires_at, "plan_hash": self.plan_hash,
        }

    @property
    def manifest_hash(self) -> str:
        return content_hash(self.to_dict())

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "PlanManifest":
        return cls(
            run_id=value["run_id"], task_id=value["task_id"], base_snapshot=value["base_snapshot"],
            allowed_paths=list(value["allowed_paths"]), allowed_urls=list(value.get("allowed_urls", [])),
            operations=[PlannedOperation.from_dict(item) for item in value["operations"]],
            created_at=value["created_at"], expires_at=value["expires_at"], plan_hash=value["plan_hash"],
        )


@dataclass(frozen=True)
class ApprovalGrant:
    grant_id: str
    actor_id: str
    run_id: str
    manifest_hash: str
    tool_id: str
    arguments_hash: str
    expires_at: str
    nonce: str
    consumed: bool = False

    @classmethod
    def create(cls, *, actor_id: str, run_id: str, manifest_hash: str,
               tool_id: str, arguments: dict[str, Any], expires_at: str) -> "ApprovalGrant":
        return cls(str(uuid4()), actor_id, run_id, manifest_hash, tool_id,
                   content_hash(arguments), expires_at, str(uuid4()))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Evidence:
    evidence_id: str
    source_id: str
    title: str
    url: str
    collected_at: str
    locator: str
    excerpt: str
    content_hash: str

    @classmethod
    def create(cls, *, title: str, url: str, locator: str, excerpt: str) -> "Evidence":
        source_id = content_hash(url)
        return cls(str(uuid4()), source_id, title, url, utc_now(), locator, excerpt, content_hash(excerpt))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Claim:
    claim_id: str
    text: str
    critical: bool
    evidence_ids: list[str]
    status: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class VerificationResult:
    check_id: str
    status: CheckStatus
    evidence: str
    details: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"check_id": self.check_id, "status": self.status.value,
                "evidence": self.evidence, "details": self.details}

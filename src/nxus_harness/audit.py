"""Journal JSONL append-only avec chaînage et redaction minimale."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import json
import re
from uuid import uuid4

from .models import ValidationError, canonical_json, content_hash, utc_now

# Les motifs masquent les secrets de démonstration et les formes courantes.
_SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|token|secret|password)\s*([:=])\s*([^\s,;]+)"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._-]+", re.I),
    re.compile(r"\bTOP_SECRET_[A-Za-z0-9_-]+\b"),
]


def redact(value: Any) -> Any:
    """Masque récursivement les valeurs potentiellement sensibles."""
    if isinstance(value, dict):
        return {key: redact(item) for key, item in value.items()}
    if isinstance(value, list):
        return [redact(item) for item in value]
    if not isinstance(value, str):
        return value
    clean = value
    clean = _SECRET_PATTERNS[0].sub(lambda match: f"{match.group(1)}{match.group(2)}[REDACTED]", clean)
    for pattern in _SECRET_PATTERNS[1:]:
        clean = pattern.sub("[REDACTED]", clean)
    return clean


@dataclass(frozen=True)
class AuditEvent:
    event_id: str
    timestamp: str
    run_id: str
    tenant_id: str
    component: str
    action: str
    decision: str
    details: dict[str, Any]
    previous_hash: str
    event_hash: str


class AuditLog:
    """Append-only local ; la vérification détecte une altération ultérieure."""

    def __init__(self, path: Path, *, run_id: str, tenant_id: str) -> None:
        self.path = path
        self.run_id = run_id
        self.tenant_id = tenant_id
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._previous_hash = self._tail_hash()

    def _tail_hash(self) -> str:
        if not self.path.exists() or not self.path.read_text(encoding="utf-8").strip():
            return "GENESIS"
        last_line = self.path.read_text(encoding="utf-8").strip().splitlines()[-1]
        try:
            return json.loads(last_line)["event_hash"]
        except (KeyError, json.JSONDecodeError) as exc:
            raise ValidationError("audit JSONL illisible") from exc

    def append(self, component: str, action: str, decision: str, details: dict[str, Any] | None = None) -> AuditEvent:
        safe_details = redact(details or {})
        payload = {
            "event_id": str(uuid4()), "timestamp": utc_now(), "run_id": self.run_id,
            "tenant_id": self.tenant_id, "component": component, "action": action,
            "decision": decision, "details": safe_details, "previous_hash": self._previous_hash,
        }
        event_hash = content_hash(payload)
        payload["event_hash"] = event_hash
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(canonical_json(payload) + "\n")
        self._previous_hash = event_hash
        return AuditEvent(**payload)

    @staticmethod
    def verify(path: Path) -> tuple[bool, str]:
        previous = "GENESIS"
        if not path.exists():
            return False, "journal absent"
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            try:
                event = json.loads(line)
                actual_hash = event.pop("event_hash")
            except (json.JSONDecodeError, KeyError):
                return False, f"ligne {line_no} invalide"
            if event.get("previous_hash") != previous:
                return False, f"rupture de chaîne ligne {line_no}"
            # [CORRIGÉ 19/10/2026 — trouvé via smokinggun_scan le 18/10,
            # corrigé le 19/10] canonical_json(event) était recalculé
            # jusqu'à 3 fois par ligne (une fois implicitement dans
            # content_hash, deux fois pour les deux contrôles `in`) --
            # sérialisé une seule fois ici et réutilisé ; content_hash()
            # accepte déjà une chaîne directement sans re-sérialiser.
            serialized = canonical_json(event)
            if content_hash(serialized) != actual_hash:
                return False, f"hash invalide ligne {line_no}"
            if "TOP_SECRET_" in serialized or "sk-" in serialized:
                return False, f"secret non redacté ligne {line_no}"
            previous = actual_hash
        return True, "chaîne valide"

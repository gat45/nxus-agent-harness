"""Grants courts, liés au manifeste et consommables une seule fois."""
from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from typing import Any
import json

from .models import ApprovalGrant, PolicyDenied, ValidationError, content_hash, parse_utc, utc_now


class ApprovalService:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._grants: dict[str, ApprovalGrant] = {}
        if self.path.exists():
            self._load()

    def _load(self) -> None:
        try:
            values = json.loads(self.path.read_text(encoding="utf-8"))
            self._grants = {item["grant_id"]: ApprovalGrant(**item) for item in values}
        except (OSError, json.JSONDecodeError, TypeError, KeyError) as exc:
            raise ValidationError("store d’approbations invalide") from exc

    def _save(self) -> None:
        serialized = [grant.to_dict() for grant in self._grants.values()]
        self.path.write_text(json.dumps(serialized, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def issue(self, *, actor_id: str, run_id: str, manifest_hash: str, tool_id: str,
              arguments: dict[str, Any], ttl_seconds: int = 300) -> ApprovalGrant:
        if ttl_seconds < 1 or ttl_seconds > 3600:
            raise ValidationError("TTL d’approbation hors limite")
        expires = parse_utc(utc_now()) + timedelta(seconds=ttl_seconds)
        grant = ApprovalGrant.create(
            actor_id=actor_id, run_id=run_id, manifest_hash=manifest_hash,
            tool_id=tool_id, arguments=arguments, expires_at=expires.isoformat(),
        )
        self._grants[grant.grant_id] = grant
        self._save()
        return grant

    def validate_and_consume(self, *, grant_id: str, actor_id: str, run_id: str,
                             manifest_hash: str, tool_id: str, arguments: dict[str, Any]) -> ApprovalGrant:
        grant = self._grants.get(grant_id)
        if grant is None:
            raise PolicyDenied("approbation inconnue")
        if grant.consumed:
            raise PolicyDenied("approbation déjà consommée")
        if parse_utc(grant.expires_at) <= parse_utc(utc_now()):
            raise PolicyDenied("approbation expirée")
        expected = (actor_id, run_id, manifest_hash, tool_id, content_hash(arguments))
        received = (grant.actor_id, grant.run_id, grant.manifest_hash, grant.tool_id, grant.arguments_hash)
        if received != expected:
            raise PolicyDenied("approbation non liée à l’action exacte")
        consumed = replace(grant, consumed=True)
        self._grants[grant_id] = consumed
        self._save()
        return consumed

    def revoke_all(self) -> int:
        changed = 0
        for key, grant in list(self._grants.items()):
            if not grant.consumed:
                self._grants[key] = replace(grant, consumed=True)
                changed += 1
        self._save()
        return changed

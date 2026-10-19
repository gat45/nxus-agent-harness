"""Grants courts, liés au manifeste et consommables une seule fois."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from typing import Any, Iterator
import json
import os
import time

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

    @contextmanager
    def _exclusive_lock(self, *, timeout_seconds: float = 10.0) -> Iterator[None]:
        """[AJOUTÉ 19/10/2026 — faille réelle trouvée ET REPRODUITE (rapport
        d'audit externe + test à deux process séparés lancés en parallèle) :
        deux process qui chargent chacun leur propre copie en mémoire du
        même fichier d'approbations peuvent tous les deux valider le même
        grant à usage unique AVANT que l'un ou l'autre n'écrive sa
        consommation sur disque — "usage unique" n'était vrai qu'au sein
        d'un seul process. Verrou de fichier portable (pas de dépendance
        externe) : création exclusive atomique d'un fichier `.lock` sibling
        via O_CREAT|O_EXCL, qui réussit sur EXACTEMENT un process à la fois
        sur Windows et POSIX ; les autres retentent avec un court backoff
        jusqu'au timeout."""
        lock_path = self.path.with_suffix(self.path.suffix + ".lock")
        deadline = time.monotonic() + timeout_seconds
        fd = None
        while fd is None:
            try:
                fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_RDWR)
            except FileExistsError:
                if time.monotonic() >= deadline:
                    raise PolicyDenied("verrou d'approbation indisponible (contention)")
                time.sleep(0.02)
        try:
            yield
        finally:
            os.close(fd)
            lock_path.unlink(missing_ok=True)

    def issue(self, *, actor_id: str, run_id: str, manifest_hash: str, tool_id: str,
              arguments: dict[str, Any], ttl_seconds: int = 300) -> ApprovalGrant:
        if ttl_seconds < 1 or ttl_seconds > 3600:
            raise ValidationError("TTL d’approbation hors limite")
        expires = parse_utc(utc_now()) + timedelta(seconds=ttl_seconds)
        grant = ApprovalGrant.create(
            actor_id=actor_id, run_id=run_id, manifest_hash=manifest_hash,
            tool_id=tool_id, arguments=arguments, expires_at=expires.isoformat(),
        )
        # [AJOUTÉ 19/10/2026 — faille réelle trouvée par un agent puis
        # REPRODUITE avec deux vrais process séparés qui appellent
        # resume_run()+approve_and_run() sur le MÊME run (REC-05) : issue()
        # n'avait NI verrou NI relecture fraîche -- deux ApprovalService
        # distincts (un par resume_run()) partent chacun de l'état DISQUE
        # AU MOMENT DE LEUR CONSTRUCTION (vide, avant tout appel à
        # approve()), ajoutent leur propre grant en mémoire, puis _save()
        # écrase le fichier avec SEULEMENT ce que CE process a en mémoire —
        # le grant du premier process disparaît du disque, écrasé par le
        # second. Reproduit : exit_code="approbation inconnue" sur le
        # process dont le grant a été perdu. Même verrou + relecture
        # fraîche que validate_and_consume(), appliqué ici au moment
        # d'AJOUTER un grant plutôt que de le consommer.
        with self._exclusive_lock():
            if self.path.exists():
                self._load()
            self._grants[grant.grant_id] = grant
            self._save()
        return grant

    def validate_and_consume(self, *, grant_id: str, actor_id: str, run_id: str,
                             manifest_hash: str, tool_id: str, arguments: dict[str, Any]) -> ApprovalGrant:
        with self._exclusive_lock():
            # Relecture OBLIGATOIRE sous verrou : self._grants peut être une
            # copie périmée chargée avant qu'un autre process n'écrive sa
            # propre consommation -- sans ce rechargement, le verrou protège
            # l'écriture mais pas la décision "consumed ou pas", qui resterait
            # basée sur un état obsolète.
            if self.path.exists():
                self._load()
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
        # [AJOUTÉ 19/10/2026 — même famille de bug que issue()/
        # validate_and_consume() (ce même jour) : revoke_all() (appelé par
        # le kill switch, PolicyEngine.abort()) mutait self._grants, une
        # copie en mémoire potentiellement périmée, puis _save() écrasait
        # le fichier avec SEULEMENT cette copie -- un grant émis par un
        # AUTRE process entre la construction de cette instance et cet
        # appel aurait disparu du disque sans jamais être révoqué.
        with self._exclusive_lock():
            if self.path.exists():
                self._load()
            changed = 0
            for key, grant in list(self._grants.items()):
                if not grant.consumed:
                    self._grants[key] = replace(grant, consumed=True)
                    changed += 1
            self._save()
            return changed

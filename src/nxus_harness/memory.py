"""Mémoire persistante inter-run, isolée par tenant, append-only.

Différence avec evidence.py : evidence.jsonl est PAR RUN (provenance d'une
exécution donnée, repart de zéro à chaque run). memory.py est PAR TENANT et
survit aux runs : HarnessEngine.verify_and_complete() y enregistre un résumé
de chaque run terminé (objectif, état final, outils exécutés), et LlmPlanner
peut relire les derniers résumés d'un tenant pour informer sa proposition de
plan sur le run suivant — une vraie boucle de mémoire, pas juste un journal
mort.

Ce store est écrit UNIQUEMENT par le harness lui-même (jamais directement
depuis une sortie de modèle ou un contenu de fixture) : contrairement à
retrieve_fixture (données externes, toujours "untrusted": true), une entrée
de mémoire reflète un fait vérifié par le harness (l'état final d'un run
passé, déjà validé par verify_and_complete()). Elle reste néanmoins un
CONTEXTE pour le planificateur, jamais une autorisation : relire la mémoire
n'accorde aucun droit et ne bypass aucun contrôle de policy.py.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
import json
import re

from .models import utc_now

_SAFE_TENANT = re.compile(r"^[A-Za-z0-9_.-]+$")


@dataclass(frozen=True)
class MemoryEntry:
    run_id: str
    tenant_id: str
    task_id: str
    objective: str
    final_state: str
    tool_ids: list[str]
    recorded_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class MemoryStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def _path_for(self, tenant_id: str) -> Path:
        if not _SAFE_TENANT.match(tenant_id):
            raise ValueError("tenant_id invalide pour la mémoire")
        return self.root / f"{tenant_id}.jsonl"

    def record_run(self, *, run_id: str, tenant_id: str, task_id: str, objective: str,
                   final_state: str, tool_ids: list[str]) -> None:
        entry = MemoryEntry(run_id, tenant_id, task_id, objective, final_state, tool_ids, utc_now())
        with self._path_for(tenant_id).open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry.to_dict(), ensure_ascii=False, sort_keys=True) + "\n")

    def recall(self, tenant_id: str, *, limit: int = 10) -> list[MemoryEntry]:
        path = self._path_for(tenant_id)
        if not path.is_file():
            return []
        lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line]
        entries = [MemoryEntry(**json.loads(line)) for line in lines[-limit:]]
        return entries

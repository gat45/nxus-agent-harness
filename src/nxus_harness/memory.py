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
from datetime import timedelta
from pathlib import Path
from typing import Any
import json

from .models import SAFE_IDENTIFIER_PATTERN, parse_utc, utc_now

_SAFE_TENANT = SAFE_IDENTIFIER_PATTERN  # [MIS A JOUR 19/10/2026] centralisé dans models.py, voir ce fichier pour la raison


@dataclass(frozen=True)
class MemoryEntry:
    run_id: str
    tenant_id: str
    task_id: str
    objective: str
    final_state: str
    tool_ids: list[str]
    recorded_at: str
    # [AJOUTÉ 19/10/2026 — axe 5 du cahier des charges (mémoire), conception
    # revue par agent : le changement le moins cher qui a une vraie valeur
    # n'est pas de scinder en 5 mémoires (épisodique/sémantique/procédurale/
    # préférences/travail) -- il n'existe qu'un seul producteur
    # (verify_and_complete()) et un seul consommateur (_memory_context())
    # aujourd'hui, une taxonomie sans second consommateur serait
    # spéculative. Le vrai manque concret déjà rencontré cette session (voir
    # llm_planner.py, 18/10/2026) : un run vieux de plusieurs semaines reste
    # mélangé aux runs récents sans aucune notion de péremption -- seul
    # `limit` (un COMPTE, pas une durée) les faisait sortir de la fenêtre.
    # Champs ADDITIFS avec défauts : les lignes .jsonl déjà écrites restent
    # lisibles sans migration (dataclass + **kwargs tolère des clés
    # manquantes si elles ont un défaut).
    expires_at: str | None = None
    confidence: float = 1.0

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
                   final_state: str, tool_ids: list[str], ttl_days: int | None = None) -> None:
        expires_at = (parse_utc(utc_now()) + timedelta(days=ttl_days)).isoformat() if ttl_days is not None else None
        entry = MemoryEntry(run_id, tenant_id, task_id, objective, final_state, tool_ids, utc_now(), expires_at)
        with self._path_for(tenant_id).open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry.to_dict(), ensure_ascii=False, sort_keys=True) + "\n")

    def recall(self, tenant_id: str, *, limit: int = 10) -> list[MemoryEntry]:
        path = self._path_for(tenant_id)
        if not path.is_file():
            return []
        lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line]
        entries = [MemoryEntry(**json.loads(line)) for line in lines]
        # [AJOUTÉ 19/10/2026] Filtré par péremption AVANT d'appliquer `limit`,
        # sinon un vieux run expiré pourrait quand même occuper une place
        # dans la fenêtre récente si peu de runs plus récents existent.
        now = parse_utc(utc_now())

        def _not_expired(entry: MemoryEntry) -> bool:
            if entry.expires_at is None:
                return True
            # [AJOUTE 20/10/2026 -- bug reel trouve par un agent puis
            # verifie en vrai : un seul expires_at corrompu/illisible
            # (edition manuelle, corruption disque) faisait lever
            # parse_utc() une ValueError NON RATTRAPEE, qui remontait hors
            # de recall() -- donc hors de LlmPlanner._memory_context() --
            # et plantait la planification de la mission ENTIERE a cause
            # d'UNE SEULE vieille ligne corrompue parmi des entrees par
            # ailleurs valides. Echec OUVERT (traitee comme non expiree)
            # plutot que ferme : la peremption est une aide de fenetrage,
            # pas un controle de securite -- une entree illisible reste
            # visible plutot que de faire disparaitre TOUTE la memoire du
            # tenant.
            try:
                return parse_utc(entry.expires_at) > now
            except ValueError:
                return True

        entries = [entry for entry in entries if _not_expired(entry)]
        return entries[-limit:]

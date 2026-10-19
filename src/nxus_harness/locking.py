"""Verrou de fichier portable partagé par approvals.py, engine.py et audit.py.

[AJOUTE 20/10/2026 -- faille reelle trouvee ET REPRODUITE par un agent :
les TROIS fichiers ci-dessus dupliquaient INDEPENDAMMENT le même motif de
verrou (création atomique O_CREAT|O_EXCL d'un fichier `.lock` sibling,
backoff court jusqu'à un timeout) sans AUCUNE détection de verrou périmé.
Un process qui tient le verrou et meurt anormalement (crash, OOM kill,
`kill -9`, coupure d'alimentation) avant son `finally: unlink` laisse le
`.lock` sur disque POUR TOUJOURS -- reproduit en vrai (fichier `.lock`
créé manuellement pour simuler ce crash, `issue()` ET `revoke_all()`
bloquent 10s puis lèvent PolicyDenied, le verrou reste présent après).
Le pire : `revoke_all()` (approvals.py) est le coupe-circuit de sécurité
(`PolicyEngine.kill_switch`/`abort()`) -- exactement le contrôle censé
fonctionner quand quelque chose a déjà mal tourné est celui qui se bloque
silencieusement pile quand un crash a eu lieu assez tôt pour laisser le
verrou en place.

Centralisé ici (même leçon que SAFE_IDENTIFIER_PATTERN/DEFAULT_DESIRED_DRAFT/
is_drive_absolute_path dans models.py : trois copies qui pourraient un jour
diverger) : la détection de péremption se base sur l'âge du fichier
(mtime), pas sur la vivacité du PID -- plus simple, sans dépendance
externe, cross-platform, et largement suffisant puisque `stale_after_seconds`
est fixé bien au-delà de toute contention légitime (verrou tenu quelques
millisecondes en pratique)."""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator
import os
import time


@contextmanager
def exclusive_file_lock(lock_path: Path, *, timeout_seconds: float = 10.0,
                        stale_after_seconds: float = 60.0,
                        on_timeout: type[Exception] = TimeoutError,
                        timeout_message: str = "verrou indisponible (contention)") -> Iterator[None]:
    deadline = time.monotonic() + timeout_seconds
    fd = None
    while fd is None:
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_RDWR)
        except FileExistsError:
            if _is_stale(lock_path, stale_after_seconds):
                # Reprise d'un verrou périmé : un autre process a pu tenter
                # la même reprise en même temps, le prochain os.open()
                # retrentera simplement la boucle si on perd la course.
                try:
                    lock_path.unlink()
                except OSError:
                    pass
                continue
            if time.monotonic() >= deadline:
                raise on_timeout(timeout_message)
            time.sleep(0.02)
    try:
        yield
    finally:
        os.close(fd)
        lock_path.unlink(missing_ok=True)


def _is_stale(lock_path: Path, stale_after_seconds: float) -> bool:
    try:
        age = time.time() - lock_path.stat().st_mtime
    except OSError:
        return False  # supprimé entre l'échec de l'open et ce stat() : plus périmé, juste disparu
    return age > stale_after_seconds

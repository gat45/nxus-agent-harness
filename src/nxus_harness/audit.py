"""Journal JSONL append-only avec chaînage et redaction minimale."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator
import json
import os
import re
import time
from uuid import uuid4

from .models import ValidationError, canonical_json, content_hash, utc_now

# Les motifs masquent les secrets de démonstration et les formes courantes.
_SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|token|secret|password)\s*([:=])\s*([^\s,;]+)"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._-]+", re.I),
    re.compile(r"\bTOP_SECRET_[A-Za-z0-9_-]+\b"),
    # [AJOUTÉ 19/10/2026 — conçu par un agent après relecture : les motifs
    # précédents ne couvraient que des formes génériques (clé=valeur, sk-,
    # Bearer). execute_python/fetch_url sont les SEULS points où du contenu
    # externe arbitraire entre dans `details` -- un print() de variable
    # d'environnement ou un cat de fichier de clé réelle a une forme
    # précise que ces motifs génériques ne reconnaissent pas. Ajoutés
    # seulement pour des formes plausibles via CES outils précis (pas un
    # scanner générique "toutes les clés cloud possibles" -- sur-ingénierie
    # pour un harnais mono-opérateur local).
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),  # clé d'accès AWS
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b"),  # token GitHub (personnel/OAuth/user/server)
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),  # en-tête de clé privée (ex. cat accidentel d'un fichier .pem)
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

    @contextmanager
    def _exclusive_lock(self, *, timeout_seconds: float = 10.0) -> Iterator[None]:
        """[AJOUTE 20/10/2026 -- faille reelle trouvee ET REPRODUITE (deux
        instances AuditLog reelles pointant sur le meme fichier, 50 append()
        chacune depuis deux threads) : self._previous_hash est mis en cache
        en memoire au __init__ et apres chaque append(), sans jamais relire
        le disque -- deux ecrivains concurrents (meme scenario qu'un run
        repris en double, deja corrige pour approvals.py/engine.py) lisent
        chacun le meme previous_hash perime et ecrivent des maillons en
        collision. Resultat observe : aucune exception au moment de
        l'ecriture (echec SILENCIEUX), mais AuditLog.verify() detecte la
        chaine corrompue a partir de la ligne 2 -- au moment ou c'est
        decouvert, les evenements legitimes sont deja indiscernables d'une
        vraie alteration. Meme verrou portable O_CREAT|O_EXCL que
        approvals.py, mais ICI la relecture du tail depuis le disque se fait
        SOUS le verrou (pas seulement au __init__) pour que deux instances
        ne partagent jamais un previous_hash perime."""
        lock_path = self.path.with_suffix(self.path.suffix + ".lock")
        deadline = time.monotonic() + timeout_seconds
        fd = None
        while fd is None:
            try:
                fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_RDWR)
            except FileExistsError:
                if time.monotonic() >= deadline:
                    raise ValidationError("verrou d'audit indisponible (contention)")
                time.sleep(0.02)
        try:
            yield
        finally:
            os.close(fd)
            lock_path.unlink(missing_ok=True)

    def _tail_sidecar_path(self) -> Path:
        return self.path.with_suffix(self.path.suffix + ".tail")

    def append(self, component: str, action: str, decision: str, details: dict[str, Any] | None = None) -> AuditEvent:
        safe_details = redact(details or {})
        with self._exclusive_lock():
            previous_hash = self._tail_hash()
            payload = {
                "event_id": str(uuid4()), "timestamp": utc_now(), "run_id": self.run_id,
                "tenant_id": self.tenant_id, "component": component, "action": action,
                "decision": decision, "details": safe_details, "previous_hash": previous_hash,
            }
            event_hash = content_hash(payload)
            payload["event_hash"] = event_hash
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(canonical_json(payload) + "\n")
            self._previous_hash = event_hash
            # [AJOUTE 20/10/2026 -- faille reelle trouvee ET REPRODUITE : la
            # chaine de hachage ne lie chaque ligne qu'a la PRECEDENTE ;
            # rien n'ancre la longueur attendue du fichier ailleurs, donc
            # supprimer les N dernieres lignes (truncature) laisse
            # AuditLog.verify() rapporter "chaîne valide" -- confirme par un
            # test reel (3 events ecrits, derniere ligne supprimee par
            # ecriture de fichier brute, verify() toujours (True, ...)).
            # Sidecar hors-bande (chemin different, ecrit SOUS le meme
            # verrou qu'append() donc jamais perime) : le dernier event_hash
            # connu-bon. verify() le compare au vrai dernier maillon trouve
            # dans le fichier ; une troncature change ce dernier maillon
            # (ou le fait disparaitre) sans toucher le sidecar, donc devient
            # detectable. Protege contre une troncature APRES qu'un append()
            # ait eu lieu avec le correctif en place ; n'ancre pas
            # retroactivement un fichier deja tronque avant ce correctif.
            self._tail_sidecar_path().write_text(event_hash, encoding="utf-8")
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
        sidecar_path = path.with_suffix(path.suffix + ".tail")
        if sidecar_path.exists():
            expected_tail = sidecar_path.read_text(encoding="utf-8").strip()
            if expected_tail and expected_tail != previous:
                return False, "troncature détectée (dernier hash connu absent du journal)"
        return True, "chaîne valide"

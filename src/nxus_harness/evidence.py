"""Store local de provenance : evidence → source et claims atomiques."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable
import json

from .models import Claim, Evidence, ValidationError, flatten_for_markdown


def _read_jsonl(path: Path) -> list[dict]:
    """[AJOUTE 20/10/2026 -- bug reel trouve par un agent puis verifie en
    vrai : evidence_ids()/_trusted_evidence_ids()/validate_claims()/
    render_citations() faisaient chacun json.loads(line) sans AUCUN
    try/except -- une seule ligne corrompue (ecriture tronquee par un
    crash, disque plein, ecrivain concurrent) dans evidence.jsonl OU
    claims.jsonl plantait les QUATRE methodes avec un JSONDecodeError non
    rattrape. validate_claims() est appelee depuis verify_and_complete()
    (engine.py) : une seule ligne corrompue pouvait donc faire echouer un
    run par ailleurs reussi, juste avant la ligne d'arrivee. Meme classe
    de bug et meme remede (echec OUVERT, ligne ignoree plutot que tout
    faire planter) que le correctif de memory.py.recall() (74e701d) --
    centralise ici pour que les quatre methodes partagent EXACTEMENT la
    meme tolerance plutot que de la dupliquer quatre fois."""
    if not path.exists():
        return []
    entries = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries


class EvidenceStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.evidence_path = self.root / "evidence.jsonl"
        self.claims_path = self.root / "claims.jsonl"

    def add_evidence(self, evidence: Evidence) -> None:
        with self.evidence_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(evidence.to_dict(), ensure_ascii=False, sort_keys=True) + "\n")

    def add_claim(self, claim: Claim) -> None:
        with self.claims_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(claim.to_dict(), ensure_ascii=False, sort_keys=True) + "\n")

    def evidence_ids(self) -> set[str]:
        return {entry["evidence_id"] for entry in _read_jsonl(self.evidence_path)}

    def _trusted_evidence_ids(self) -> set[str]:
        return {entry["evidence_id"] for entry in _read_jsonl(self.evidence_path) if not entry.get("untrusted", False)}

    def validate_claims(self) -> list[str]:
        known = self.evidence_ids()
        # [AJOUTE 20/10/2026 -- faille reelle trouvee ET REPRODUITE : ce
        # contole ne verifiait QUE la presence d'un evidence_id existant,
        # jamais sa fiabilite -- une claim critique pouvait etre satisfaite
        # par une preuve explicitement marquee untrusted (fixture locale,
        # contenu fetch_url externe), ce qui revient exactement a ne
        # demander AUCUNE corroboration reelle. Desormais, au moins UNE
        # preuve FIABLE (untrusted=False) est exigee pour chaque claim
        # critique -- la simple presence d'evidence_ids ne suffit plus.
        trusted = self._trusted_evidence_ids()
        errors: list[str] = []
        for item in _read_jsonl(self.claims_path):
            evidence_ids = set(item.get("evidence_ids", []))
            missing = evidence_ids - known
            if item.get("critical") and (missing or not evidence_ids):
                errors.append(f"claim critique non supporté: {item.get('claim_id')}")
            elif item.get("critical") and not (evidence_ids & trusted):
                errors.append(f"claim critique supporté uniquement par des preuves non fiables: {item.get('claim_id')}")
        return errors

    def require_valid_claims(self) -> None:
        errors = self.validate_claims()
        if errors:
            raise ValidationError("; ".join(errors))

    def render_citations(self) -> str:
        entries = _read_jsonl(self.evidence_path)
        # [AJOUTE 20/10/2026 -- meme classe de faille deja corrigee pour
        # PLAN.md/report.md (voir engine.py._render_report, 20/10/2026) :
        # title/url/locator proviennent de Evidence.create(), lui-meme
        # alimente par retrieve_fixture/fetch_url (contenu marque
        # "untrusted" dans tools.py) -- flatten par precaution avant
        # interpolation dans report.md, qui inclut ce rendu tel quel.
        return "\n".join(
            f"- [{flatten_for_markdown(entry['title'])}]({flatten_for_markdown(entry['url'])}) — "
            f"{flatten_for_markdown(entry['locator'])} ({entry['collected_at']})"
            for entry in entries
        )

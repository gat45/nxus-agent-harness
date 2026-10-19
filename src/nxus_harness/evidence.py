"""Store local de provenance : evidence → source et claims atomiques."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable
import json

from .models import Claim, Evidence, ValidationError


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
        if not self.evidence_path.exists():
            return set()
        return {json.loads(line)["evidence_id"] for line in self.evidence_path.read_text(encoding="utf-8").splitlines() if line}

    def _trusted_evidence_ids(self) -> set[str]:
        if not self.evidence_path.exists():
            return set()
        return {json.loads(line)["evidence_id"] for line in self.evidence_path.read_text(encoding="utf-8").splitlines()
                if line and not json.loads(line).get("untrusted", False)}

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
        if not self.claims_path.exists():
            return errors
        for line in self.claims_path.read_text(encoding="utf-8").splitlines():
            if not line:
                continue
            item = json.loads(line)
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
        if not self.evidence_path.exists():
            return ""
        entries = [json.loads(line) for line in self.evidence_path.read_text(encoding="utf-8").splitlines() if line]
        return "\n".join(f"- [{entry['title']}]({entry['url']}) — {entry['locator']} ({entry['collected_at']})" for entry in entries)

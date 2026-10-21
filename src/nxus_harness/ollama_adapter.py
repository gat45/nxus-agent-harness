"""Adaptateur Ollama opt-in.

Il ne lance aucune requête au démarrage et ne transmet aucun tool_call au gateway.
Le caller doit valider toute sortie structurée avant usage.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from http.client import IncompleteRead
from urllib.parse import urlparse
from urllib.request import Request, urlopen
import json
import time

from .models import ValidationError


# [AJOUTE 21/10/2026 -- bug reel trouve par un agent puis verifie en vrai
# (serveur local jetable egouttant 1 octet a la fois) : le meme bug deja
# corrige cote llama_cpp_adapter.py (timeout= passe a urlopen() n'est un
# plafond que PAR OPERATION socket, pas sur la requete entiere -- il se
# reinitialise a chaque recv() reussi) n'avait jamais ete reporte ici.
# Un pair qui egoutte des octets tient la connexion ouverte indefiniment
# pendant que response.read() accumule tout en memoire sans aucune limite
# de taille ni de temps total. Meme plafond que le voisin llama.cpp.
_MAX_RESPONSE_BYTES = 8 * 1024 * 1024


def _read_capped(response: Any, *, max_bytes: int = _MAX_RESPONSE_BYTES, deadline_seconds: float) -> bytes:
    deadline = time.monotonic() + deadline_seconds
    chunks: list[bytes] = []
    total = 0
    while True:
        if time.monotonic() > deadline:
            raise ValidationError("réponse Ollama trop lente (délai total dépassé)")
        chunk = response.read(65536)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise ValidationError("réponse Ollama trop volumineuse")
        chunks.append(chunk)
    return b"".join(chunks)


@dataclass(frozen=True)
class OllamaProfile:
    base_url: str = "http://127.0.0.1:11434"
    model: str = ""
    timeout_seconds: int = 20
    enabled: bool = False

    def validate(self) -> None:
        parsed = urlparse(self.base_url)
        if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise ValidationError("le MVP n’autorise Ollama que sur loopback HTTP")
        if self.timeout_seconds < 1 or self.timeout_seconds > 120:
            raise ValidationError("timeout Ollama hors limite")
        if self.enabled and not self.model:
            raise ValidationError("un modèle Ollama épinglé est requis")


class OllamaAdapter:
    """Client restreint pour une réponse JSON, sans exécution d’outils."""

    def __init__(self, profile: OllamaProfile) -> None:
        profile.validate()
        self.profile = profile

    def structured_chat(self, messages: list[dict[str, str]], schema: dict[str, Any]) -> dict[str, Any]:
        if not self.profile.enabled:
            raise ValidationError("adaptateur Ollama désactivé")
        payload = json.dumps({"model": self.profile.model, "messages": messages, "stream": False, "format": schema}).encode("utf-8")
        request = Request(self.profile.base_url.rstrip("/") + "/api/chat", data=payload,
                          headers={"Content-Type": "application/json"}, method="POST")
        # [AJOUTE 21/10/2026 -- bug reel trouve par un agent puis verifie en
        # vrai : ni la lecture (response.read()/_read_capped) ni le
        # json.loads() de l'enveloppe EXTERNE n'etaient proteges, alors que
        # le parse du contenu INTERNE (ci-dessous) l'est deja -- une
        # reponse HTTP tronquee avec un Content-Length mensonger leve un
        # http.client.IncompleteRead brut (qui n'herite ni d'OSError ni de
        # ValueError) qui echappe a tout appelant filtrant sur ces types,
        # et un corps non-JSON leve un JSONDecodeError brut au lieu du
        # ValidationError propre que le reste de cette methode utilise
        # deja pour toute sortie invalide.
        try:
            with urlopen(request, timeout=self.profile.timeout_seconds) as response:  # nosec B310: loopback validated
                raw_bytes = _read_capped(response, deadline_seconds=self.profile.timeout_seconds)
            raw = json.loads(raw_bytes.decode("utf-8"))
        except (IncompleteRead, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValidationError("réponse Ollama invalide (enveloppe JSON illisible)") from exc
        content = raw.get("message", {}).get("content")
        if not isinstance(content, str):
            raise ValidationError("réponse Ollama sans contenu")
        try:
            result = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ValidationError("sortie structurée Ollama invalide") from exc
        if not isinstance(result, dict):
            raise ValidationError("sortie Ollama non objet")
        # Validation d’interface minimale ; la validation métier reste dans le harness.
        required = schema.get("required", [])
        if any(key not in result for key in required):
            raise ValidationError("sortie Ollama incomplète")
        return result

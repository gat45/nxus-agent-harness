"""Adaptateur Ollama opt-in.

Il ne lance aucune requête au démarrage et ne transmet aucun tool_call au gateway.
Le caller doit valider toute sortie structurée avant usage.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse
from urllib.request import Request, urlopen
import json

from .models import ValidationError


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
        with urlopen(request, timeout=self.profile.timeout_seconds) as response:  # nosec B310: loopback validated
            raw = json.loads(response.read().decode("utf-8"))
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

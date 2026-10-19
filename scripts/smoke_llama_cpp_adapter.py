"""Test d'intégration manuel (pas unittest) : parle à un vrai llama-server.

Usage : lancer llama-server (port 8080 par défaut) avec un modèle chargé, puis :
    PYTHONPATH=src python3 scripts/smoke_llama_cpp_adapter.py [model_id]
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from nxus_harness.llama_cpp_adapter import LlamaCppAdapter, LlamaCppProfile

model_id = sys.argv[1] if len(sys.argv) > 1 else "q38_9b_s3_gutop.gguf"
profile = LlamaCppProfile(model=model_id, enabled=True)
adapter = LlamaCppAdapter(profile)

status = adapter.model_status()
print("model_status :", status)
assert status["models"], "aucun modele expose par le serveur"

result = adapter.structured_chat(
    messages=[
        {"role": "system", "content": "Reponds uniquement en JSON valide: {\"answer\": \"...\"}"},
        {"role": "user", "content": "Mets le mot OK dans le champ answer."},
    ],
    schema={"required": ["answer"]},
)
print("OK, reponse structuree recue :", result)
assert "answer" in result
print("SMOKE TEST PASSED")

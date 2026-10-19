#!/usr/bin/env python3
"""Affiche le statut KV/contexte des modèles exposés par un llama-server local.

Lecture seule, loopback uniquement (même contrainte que llama_cpp_adapter).

Usage :
    PYTHONPATH=src python3 scripts/llama_cpp_kv_status.py [base_url]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from nxus_harness.llama_cpp_adapter import LlamaCppAdapter, LlamaCppProfile

base_url = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8080"
adapter = LlamaCppAdapter(LlamaCppProfile(base_url=base_url))
print(json.dumps(adapter.model_status(), indent=2, ensure_ascii=False))

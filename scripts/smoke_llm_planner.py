"""Test d'intégration manuel : un vrai llama-server PROPOSE le plan, le
harness le valide et l'exécute via le MÊME pipeline que run_demo().

Usage : lancer llama-server (port 8080) avec un modèle chargé, puis :
    PYTHONPATH=src python3 scripts/smoke_llm_planner.py [model_id]
"""
from __future__ import annotations

import shutil
import sys
import tempfile
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from nxus_harness.engine import HarnessEngine
from nxus_harness.llama_cpp_adapter import LlamaCppAdapter, LlamaCppProfile
from nxus_harness.llm_planner import LlmPlanner
from nxus_harness.models import RiskLevel, RunState, TaskContract, TaskProfile

model_id = sys.argv[1] if len(sys.argv) > 1 else "q38_9b_s3_gutop.gguf"

root = Path(tempfile.mkdtemp(prefix="nxus-smoke-"))
(root / "fixtures").mkdir()
shutil.copy(Path(__file__).resolve().parents[1] / "fixtures" / "corpus.md", root / "fixtures" / "corpus.md")

engine = HarnessEngine(root)
contract = TaskContract(
    task_id="smoke-llm-planner", tenant_id="smoke-tenant", actor_id="operator-smoke",
    objective="Créer un brouillon local et réversible de note de version.",
    acceptance_criteria=["Le brouillon existe dans le workspace du run.", "Le contrôle déclaré draft_exists réussit."],
    profile=TaskProfile.CODE_CHANGE, max_risk=RiskLevel.R1,
    allowed_paths=["drafts/release-note.md"], allowed_tools=["write_workspace_draft", "run_declared_check"],
    desired_draft="# Note de version\n\nBrouillon propose par un modele local, valide par le harness.\n",
)

adapter = LlamaCppAdapter(LlamaCppProfile(model=model_id, enabled=True, timeout_seconds=90))
planner = LlmPlanner(adapter, memory=engine.memory)

print("Run 1 : appel du modele pour proposer le plan...")
context = engine.run_with_llm(contract, planner)
print("Etat final run 1 :", context.state)
assert context.state == RunState.COMPLETED, f"run non complete : {context.state}"
assert (context.workspace / "drafts/release-note.md").exists()

print("\nRun 2 (meme tenant) : le modele doit voir le run 1 dans son contexte memoire...")
contract2 = replace(contract, task_id="smoke-llm-planner-2", allowed_paths=["drafts/release-note-2.md"],
                     desired_draft="# Note de version 2\n\nDeuxieme brouillon, informe par la memoire du run 1.\n")
context2 = engine.run_with_llm(contract2, planner)
print("Etat final run 2 :", context2.state)
assert context2.state == RunState.COMPLETED, f"run 2 non complete : {context2.state}"
recalled = engine.memory.recall(contract.tenant_id)
print(f"Memoire du tenant apres les 2 runs : {len(recalled)} entree(s)")
assert len(recalled) == 2
print("SMOKE TEST PASSED (plans reellement proposes par le LLM, 2e run informe par la memoire du 1er, valides et executes par le harness)")

shutil.rmtree(root, ignore_errors=True)

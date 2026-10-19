"""Test d'integration manuel : un vrai llama-server propose du code Python
et une recuperation d'URL, un humain approuve (simule, --yes), et les deux
s'executent reellement (R2, profil AGENTIC_EXECUTION).

Usage : lancer llama-server (port 8080) avec un modele charge, puis :
    PYTHONPATH=src python3 scripts/smoke_agentic_execution.py [model_id]
"""
from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from nxus_harness.engine import HarnessEngine
from nxus_harness.llama_cpp_adapter import LlamaCppAdapter, LlamaCppProfile
from nxus_harness.llm_planner import LlmPlanner
from nxus_harness.models import RiskLevel, RunState, TaskContract, TaskProfile

model_id = sys.argv[1] if len(sys.argv) > 1 else "q38_9b_s3_gutop.gguf"

root = Path(tempfile.mkdtemp(prefix="nxus-agentic-"))
(root / "fixtures").mkdir()
shutil.copy(Path(__file__).resolve().parents[1] / "fixtures" / "corpus.md", root / "fixtures" / "corpus.md")

engine = HarnessEngine(root)
contract = TaskContract(
    task_id="smoke-agentic", tenant_id="smoke-tenant", actor_id="operator-smoke",
    objective="Calculer 17*23 avec un script Python et ecrire le resultat dans resultat.txt, "
              "puis recuperer le contenu de https://example.com/.",
    acceptance_criteria=["resultat.txt contient 391", "le contenu de example.com est recupere"],
    profile=TaskProfile.AGENTIC_EXECUTION, max_risk=RiskLevel.R2,
    allowed_paths=["resultat.txt"], allowed_tools=["execute_python", "fetch_url"],
    allowed_urls=["https://example.com/"],
)

adapter = LlamaCppAdapter(LlamaCppProfile(model=model_id, enabled=True, timeout_seconds=120))
planner = LlmPlanner(adapter)

print("Appel du modele pour proposer le plan (code + URL)...")
context = engine.submit(contract, planner=planner)
print((context.run_dir / "PLAN.md").read_text(encoding="utf-8"))
print("Etat apres soumission :", context.state)
assert context.state == RunState.AWAITING_APPROVAL

print("\n[simulation d'approbation humaine : --yes]")
resumed = engine.resume_run(contract.tenant_id, context.run_id)
completed = engine.approve_and_run(resumed, actor_id=contract.actor_id)
print("Etat final :", completed.state)
for entry in completed.results or []:
    print(f"- {entry['tool_id']}: {entry['result']}")

assert completed.state == RunState.COMPLETED, f"run non complete : {completed.state}"
resultat = (completed.workspace / "resultat.txt")
print("\nresultat.txt existe :", resultat.is_file())
if resultat.is_file():
    print("contenu :", resultat.read_text(encoding="utf-8"))
print("SMOKE TEST PASSED (code et requete internet reellement proposes, approuves, executes)")

shutil.rmtree(root, ignore_errors=True)

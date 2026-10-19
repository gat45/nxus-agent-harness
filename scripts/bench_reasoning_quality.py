"""Compare raisonnement ON vs OFF sur la QUALITE du plan (pas juste la
vitesse) : N essais de la tache agentique reelle (code + fetch_url),
mesure l'etat final (COMPLETED vs FAILED/erreur) et le temps, pour chaque
mode. Le serveur doit deja tourner avec le mode voulu ; relancer ce script
une fois par mode (il n'inverse pas --reasoning lui-meme).

Usage :
    PYTHONPATH=src python3 scripts/bench_reasoning_quality.py <label> [n_essais]
"""
from __future__ import annotations

import shutil
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from nxus_harness.engine import HarnessEngine
from nxus_harness.llama_cpp_adapter import LlamaCppAdapter, LlamaCppProfile
from nxus_harness.llm_planner import LlmPlanner
from nxus_harness.models import RiskLevel, RunState, TaskContract, TaskProfile, ValidationError, PolicyDenied

label = sys.argv[1] if len(sys.argv) > 1 else "essai"
n = int(sys.argv[2]) if len(sys.argv) > 2 else 3

results = []
for i in range(n):
    root = Path(tempfile.mkdtemp(prefix="nxus-bench-"))
    (root / "fixtures").mkdir()
    shutil.copy(Path(__file__).resolve().parents[1] / "fixtures" / "corpus.md", root / "fixtures" / "corpus.md")
    engine = HarnessEngine(root)
    contract = TaskContract(
        task_id=f"bench-{i}", tenant_id="bench-tenant", actor_id="operator-bench",
        objective="Calculer 17*23 avec un script Python et ecrire le resultat dans resultat.txt, "
                  "puis recuperer le contenu de https://example.com/.",
        acceptance_criteria=["resultat.txt contient 391", "le contenu de example.com est recupere"],
        profile=TaskProfile.AGENTIC_EXECUTION, max_risk=RiskLevel.R2,
        allowed_paths=["resultat.txt"], allowed_tools=["execute_python", "fetch_url"],
        allowed_urls=["https://example.com/"],
    )
    adapter = LlamaCppAdapter(LlamaCppProfile(model="q38_9b_s3_gutop.gguf", enabled=True, timeout_seconds=120))
    planner = LlmPlanner(adapter)

    start = time.monotonic()
    try:
        context = engine.submit(contract, planner=planner)
        resumed = engine.resume_run(contract.tenant_id, context.run_id)
        completed = engine.approve_and_run(resumed, actor_id=contract.actor_id)
        elapsed = time.monotonic() - start
        resultat = completed.workspace / "resultat.txt"
        content_ok = resultat.is_file() and resultat.read_text(encoding="utf-8").strip() == "391"
        results.append({"state": completed.state.value, "elapsed_s": round(elapsed, 1), "resultat_correct": content_ok})
    except (ValidationError, PolicyDenied) as exc:
        elapsed = time.monotonic() - start
        results.append({"state": f"ERREUR: {exc}", "elapsed_s": round(elapsed, 1), "resultat_correct": False})
    finally:
        shutil.rmtree(root, ignore_errors=True)
    print(f"[{label}] essai {i+1}/{n} : {results[-1]}")

ok = sum(1 for r in results if r["state"] == "COMPLETED" and r["resultat_correct"])
avg_time = sum(r["elapsed_s"] for r in results) / len(results)
print(f"\n=== {label} : {ok}/{n} reussis (COMPLETED + resultat correct), temps moyen {avg_time:.1f}s ===")

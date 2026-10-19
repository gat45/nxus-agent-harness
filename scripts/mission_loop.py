"""Pilote de mission : envoie un objectif au modele local, le laisse PROPOSER
un plan (LlmPlanner), l'approuve automatiquement (ce script tient le role de
l'operateur -- la vraie barriere de securite reste PolicyEngine : allowlist
exacte de chemins/URLs, SSRF, timeout, declared_check -- pas une relecture
humaine a chaque etape pour cette boucle autonome), execute, et affiche le
resultat. La memoire inter-run (memory.py) fait que la mission suivante VOIT
le resultat de la precedente dans le prompt du modele -- c'est elle qui
donne a la boucle sa continuite, pas ce script.

Usage :
    PYTHONPATH=src python3 scripts/mission_loop.py "objectif de la mission" \
        [--allowed-paths chemin1 chemin2] [--allowed-urls url1 url2] \
        [--model q38_9b_s3_gutop.gguf] [--root ./mission-workspace]

Ou en mode liste (un objectif par ligne depuis stdin) :
    echo -e "mission 1\nmission 2" | PYTHONPATH=src python3 scripts/mission_loop.py --stdin
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from nxus_harness.engine import HarnessEngine
from nxus_harness.llama_cpp_adapter import LlamaCppAdapter, LlamaCppProfile
from nxus_harness.llm_planner import LlmPlanner
from nxus_harness.models import PolicyDenied, RiskLevel, TaskContract, TaskProfile, ValidationError


def run_mission(engine: HarnessEngine, planner: LlmPlanner, objective: str, *,
                tenant_id: str, allowed_paths: list[str], allowed_urls: list[str],
                mission_index: int) -> None:
    contract = TaskContract(
        task_id=f"mission-{mission_index}", tenant_id=tenant_id, actor_id="mission-loop",
        objective=objective, acceptance_criteria=["l'objectif de la mission est atteint"],
        profile=TaskProfile.AGENTIC_EXECUTION, max_risk=RiskLevel.R2,
        allowed_paths=allowed_paths, allowed_urls=allowed_urls,
        allowed_tools=["write_workspace_draft", "run_declared_check", "execute_python", "fetch_url"],
        budget_seconds=90,
    )
    print(f"\n{'='*70}\nMISSION {mission_index} : {objective}\n{'='*70}")
    try:
        context = engine.submit(contract, planner=planner)
    except (ValidationError, PolicyDenied) as exc:
        print(f"[REFUSE AVANT APPROBATION] {exc}")
        return
    except Exception as exc:
        # [AJOUTE 20/10/2026 -- bug reel trouve par un agent puis verifie :
        # engine.submit() peut lever d'autres exceptions (ex. TimeoutError
        # si llama-server est lent/inaccessible) APRES avoir correctement
        # marque le run ABORTED sur disque. Seul (ValidationError,
        # PolicyDenied) etait rattrape ici, donc cette exception remontait
        # hors de run_mission(), hors de la boucle `for` de main() --stdin,
        # et arretait TOUT le lot : les missions suivantes n'etaient jamais
        # executees. Verifie par repro reelle (planner factice levant
        # TimeoutError sur la mission 1, missions 2 et 3 jamais executees).
        print(f"[ECHEC INATTENDU AVANT APPROBATION] {type(exc).__name__}: {exc}")
        return

    print(f"\n--- Plan propose par le modele (run {context.run_id}) ---")
    print((context.run_dir / "PLAN.md").read_text(encoding="utf-8"))

    try:
        resumed = engine.resume_run(tenant_id, context.run_id)
        completed = engine.approve_and_run(resumed, actor_id="mission-loop")
    except (ValidationError, PolicyDenied) as exc:
        print(f"[REFUSE A L'EXECUTION] {exc}")
        return
    except Exception as exc:
        print(f"[ECHEC INATTENDU A L'EXECUTION] {type(exc).__name__}: {exc}")
        return

    print(f"\n--- Resultat : {completed.state.value} ---")
    for entry in completed.results or []:
        result = entry["result"]
        summary = {k: v for k, v in result.items() if k not in ("stdout", "stderr", "content")}
        print(f"  {entry['tool_id']}: {summary}")
        if result.get("stdout"):
            print(f"    stdout: {result['stdout'][:300]}")
        if result.get("content"):
            print(f"    content (tronque): {result['content'][:300]}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("objective", nargs="?", help="objectif de la mission (ou utiliser --stdin)")
    parser.add_argument("--stdin", action="store_true", help="lire une mission par ligne depuis stdin")
    parser.add_argument("--model", default="q38_9b_s3_gutop.gguf")
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    parser.add_argument("--root", default="./mission-workspace", type=Path)
    parser.add_argument("--tenant", default="mission-loop-tenant")
    parser.add_argument("--allowed-paths", nargs="*", default=["output.txt", "resultat.txt", "notes.md"])
    parser.add_argument("--allowed-urls", nargs="*", default=["https://example.com/", "https://html.duckduckgo.com/html/"])
    args = parser.parse_args()

    args.root.mkdir(parents=True, exist_ok=True)
    engine = HarnessEngine(args.root)
    adapter = LlamaCppAdapter(LlamaCppProfile(model=args.model, base_url=args.base_url, enabled=True, timeout_seconds=120))
    # memory=engine.memory : la mission N+1 voit le resultat de la mission N
    # dans le prompt du modele -- c'est ce qui fait de ceci une boucle, pas
    # une serie d'appels independants.
    planner = LlmPlanner(adapter, memory=engine.memory)

    missions = [line.strip() for line in sys.stdin if line.strip()] if args.stdin else [args.objective]
    if not missions or not missions[0]:
        parser.error("fournir un objectif ou --stdin")

    for i, objective in enumerate(missions, start=1):
        run_mission(engine, planner, objective, tenant_id=args.tenant,
                    allowed_paths=args.allowed_paths, allowed_urls=args.allowed_urls,
                    mission_index=i)

    print(f"\n{'='*70}\nMemoire du tenant ({args.tenant}) apres {len(missions)} mission(s) :")
    for entry in engine.memory.recall(args.tenant, limit=20):
        print(f"  [{entry.final_state}] {entry.objective}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

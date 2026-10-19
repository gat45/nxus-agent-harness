#!/usr/bin/env python3
"""Frontend minimal pour inspecter les runs, et (depuis le 18/10/2026) pour
en SOUMETTRE un depuis la page /live.

Aucune dépendance externe (stdlib http.server uniquement, conforme au MVP :
"aucun package externe n'est requis").

[MIS A JOUR 18/10/2026 — demandé : donner des ordres depuis la page web]
Ce frontend n'est plus purement lecture seule : POST /mission soumet un
objectif au MEME pipeline que scripts/mission_loop.py (LlmPlanner ->
engine.submit() -> ReflectionReview -> approve_and_run() ->
PolicyEngine.authorize() par opération). Ce n'est donc PAS un contournement
du policy engine : la route ajoute un point d'ENTRÉE, elle ne retire aucune
barrière — mêmes allowed_tools (R2 max : write_workspace_draft,
run_declared_check, execute_python, fetch_url via AGENTIC_EXECUTION),
mêmes allowed_paths/allowed_urls fixes côté serveur (jamais pris depuis la
requête HTTP), même SSRF/timeout/declared_check qu'en CLI. Lié en loopback
uniquement par défaut — exposer --host au-delà du loopback donnerait à
quiconque peut atteindre ce port la capacité d'exécuter du code local ;
ça reste vrai de la même façon pour mission_loop.py en CLI, mais ici
l'avertissement est plus visible car void d'authentification HTTP.

Usage :
    PYTHONPATH=src python3 scripts/view_runs.py [--port 8787] [--root .] [--model ...]
"""
from __future__ import annotations

import argparse
import html
import json
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from nxus_harness.audit import AuditLog
from nxus_harness.engine import HarnessEngine
from nxus_harness.llama_cpp_adapter import LlamaCppAdapter, LlamaCppProfile
from nxus_harness.llm_planner import LlmPlanner
from nxus_harness.models import PolicyDenied, RiskLevel, TaskContract, TaskProfile, ValidationError

_SAFE_SEGMENT = re.compile(r"^[A-Za-z0-9_.-]+$")


def _safe_segment(value: str) -> str | None:
    """Rejette tout ce qui n'est pas un segment de nom de fichier simple —
    aucun `/`, `..`, ni séparateur — avant de l'utiliser dans un chemin."""
    return value if _SAFE_SEGMENT.match(value) else None


class RunsHandler(BaseHTTPRequestHandler):
    runs_root: Path  # injecté par main()
    # [AJOUTÉ 18/10/2026] état mission partagé, injecté par main() — un seul
    # engine/planner pour tout le process, comme mission_loop.py en CLI, pour
    # que la mémoire inter-run (engine.memory) voie les missions lancées
    # depuis la page web aussi bien que celles lancées en CLI.
    engine: HarnessEngine
    planner: LlmPlanner
    mission_tenant: str
    mission_allowed_paths: list[str]
    mission_allowed_urls: list[str]
    mission_token: str | None = None  # None = pas d'authentification (loopback local uniquement)
    _mission_lock = threading.Lock()  # une mission a la fois : execute_python est synchrone
    _mission_counter = 0

    def _send_html(self, status: int, body: str) -> None:
        payload = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002 - signature imposée par BaseHTTPRequestHandler
        pass  # Journal HTTP par défaut coupé : évite de polluer stdout à chaque requête du viewer.

    def do_GET(self) -> None:  # noqa: N802 - nom imposé par BaseHTTPRequestHandler
        path = self.path.split("?", 1)[0]
        if path == "/":
            self._render_index()
            return
        if path == "/live":
            self._render_live()
            return
        parts = [segment for segment in path.strip("/").split("/") if segment]
        if len(parts) == 3 and parts[0] == "run":
            tenant, run_id = _safe_segment(parts[1]), _safe_segment(parts[2])
            if tenant and run_id:
                self._render_run(tenant, run_id)
                return
        self._send_html(404, "<h1>404</h1>")

    def do_POST(self) -> None:  # noqa: N802 - nom imposé par BaseHTTPRequestHandler
        if self.path.split("?", 1)[0] != "/mission":
            self._send_html(404, "<h1>404</h1>")
            return
        # [AJOUTÉ 19/10/2026 — signalé P1 conditionnel par un audit externe]
        # "Le visualiseur n'implémente pas d'authentification visible" --
        # exact. mission_token (optionnel, None par défaut = comportement
        # inchangé en loopback local) : si configuré, le POST doit fournir
        # le même jeton via l'en-tête X-Mission-Token, sinon refus 401
        # avant même de lire le corps de la requête.
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode("utf-8") if length else ""
        fields = urllib.parse.parse_qs(body)
        if self.mission_token is not None:
            # Accepté via en-tête (clients API/CLI) OU champ de formulaire caché
            # (le formulaire HTML de /live ne peut pas poser d'en-tête sans JS).
            provided = self.headers.get("X-Mission-Token") or (fields.get("token") or [""])[0]
            if provided != self.mission_token:
                self._send_html(401, "<h1>401 — jeton manquant ou invalide</h1>")
                return
        objective = (fields.get("objective") or [""])[0].strip()
        if not objective:
            self._send_html(400, "<h1>400 — objectif vide</h1>")
            return
        # [AJOUTÉ 18/10/2026] La mission tourne en arrière-plan (un thread,
        # verrouillé : une seule à la fois) pour que la réponse HTTP revienne
        # tout de suite — /live affiche ensuite sa progression en se
        # rafraîchissant seul, exactement comme pour une mission CLI.
        threading.Thread(target=self._run_mission_background, args=(objective,), daemon=True).start()
        self.send_response(303)
        self.send_header("Location", "/live")
        self.end_headers()

    def _run_mission_background(self, objective: str) -> None:
        with self._mission_lock:
            RunsHandler._mission_counter += 1
            index = RunsHandler._mission_counter
            try:
                context = self.engine.submit(
                    TaskContract(
                        task_id=f"web-mission-{index}", tenant_id=self.mission_tenant,
                        actor_id="live-page", objective=objective,
                        acceptance_criteria=["l'objectif de la mission est atteint"],
                        profile=TaskProfile.AGENTIC_EXECUTION, max_risk=RiskLevel.R2,
                        allowed_paths=self.mission_allowed_paths, allowed_urls=self.mission_allowed_urls,
                        allowed_tools=["write_workspace_draft", "run_declared_check", "execute_python", "fetch_url"],
                        budget_seconds=90,
                    ),
                    planner=self.planner,
                )
                resumed = self.engine.resume_run(self.mission_tenant, context.run_id)
                self.engine.approve_and_run(resumed, actor_id="live-page")
            except Exception:
                # [MIS A JOUR 18/10/2026 — bug réel reproduit : un
                # TimeoutError (llama-server lent/indisponible) n'était PAS
                # capturé ici (seuls ValidationError/PolicyDenied l'étaient),
                # tuant ce thread en silence et laissant /live affiché figé
                # sur un état qui ne bougerait plus jamais. engine.submit()
                # marque maintenant le run ABORTED avant de relayer N'IMPORTE
                # QUELLE exception (voir engine.py) ; ce except large est de
                # la défense en profondeur pour que ce thread ne meure
                # jamais visiblement sans que l'état du run ait déjà été
                # mis à jour en amont. Le détail est déjà visible dans
                # state.json / audit.jsonl du run, lu par /live.
                pass

    def _render_live(self) -> None:
        # [AJOUTÉ 18/10/2026] Page qui se rafraîchit seule (meta refresh, pas
        # de JS nécessaire) et montre le run le plus récemment modifié,
        # TOUS tenants confondus — utile pendant que scripts/mission_loop.py
        # tourne : on voit l'état avancer (DISCOVERY -> ... -> EXECUTING ->
        # COMPLETED/FAILED) et le plan dès qu'il existe, sans attendre la fin
        # du run comme le ferait /run/<tenant>/<run_id> seul.
        latest_dir, latest_mtime = None, -1.0
        if self.runs_root.is_dir():
            for tenant_dir in self.runs_root.iterdir():
                if not tenant_dir.is_dir():
                    continue
                for run_dir in tenant_dir.iterdir():
                    if not run_dir.is_dir():
                        continue
                    mtime = run_dir.stat().st_mtime
                    if mtime > latest_mtime:
                        latest_mtime, latest_dir = mtime, run_dir

        if latest_dir is None:
            self._send_html(200, '<meta http-equiv="refresh" content="2"><h1>En attente d\'un run...</h1>')
            return

        tenant, run_id = latest_dir.parent.name, latest_dir.name
        state_path = latest_dir / "state.json"
        try:
            state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.is_file() else {}
        except json.JSONDecodeError:
            state = {}
        current_state = state.get("state", "?")

        plan_path = latest_dir / "PLAN.md"
        plan_html = html.escape(plan_path.read_text(encoding="utf-8")) if plan_path.is_file() else "(pas encore de plan)"

        audit_path = latest_dir / "audit.jsonl"
        recent_actions = []
        if audit_path.is_file():
            lines = audit_path.read_text(encoding="utf-8").splitlines()
            for line in lines[-12:]:
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                recent_actions.append(
                    f"<li>{html.escape(event.get('timestamp', ''))} — "
                    f"<b>{html.escape(event.get('component', ''))}</b>/{html.escape(event.get('action', ''))} "
                    f"[{html.escape(event.get('decision', ''))}]</li>"
                )

        # [AJOUTÉ 18/10/2026 — demandé : tokens/s] Mesure du SERVEUR
        # llama-server lui-même (timings.predicted_per_second), pas une
        # estimation côté client — journalisée une fois par appel dans
        # model_timings.json (llm_planner.py), jamais recalculée ici.
        timings_path = latest_dir / "model_timings.json"
        tokens_tile = ""
        if timings_path.is_file():
            try:
                timings = json.loads(timings_path.read_text(encoding="utf-8"))
                tps = timings.get("predicted_per_second")
                if tps is not None:
                    tokens_tile = (
                        '<div style="display:inline-block;padding:12px 20px;border:1px solid #444;'
                        'border-radius:8px;margin:8px 0;">'
                        '<div style="font-size:0.75rem;color:#888;">Débit de génération</div>'
                        f'<div style="font-size:2rem;font-weight:600;">{tps:.1f} <span style="font-size:1rem;color:#888;">tok/s</span></div>'
                        f'<div style="font-size:0.75rem;color:#888;">{html.escape(timings.get("model", ""))}'
                        f' · {timings.get("predicted_n", "?")} tokens générés</div>'
                        "</div>"
                    )
            except (json.JSONDecodeError, TypeError):
                pass

        # [AJOUTÉ 18/10/2026 — demandé : évolution des todo] checklist des
        # opérations du plan ; "done" vient de progress.json (engine.py),
        # écrit après CHAQUE opération exécutée, pas seulement en fin de run.
        progress_path = latest_dir / "progress.json"
        todo_html = "(pas encore de plan approuvé)"
        if progress_path.is_file():
            try:
                items = json.loads(progress_path.read_text(encoding="utf-8"))
                todo_html = "<ul style=\"list-style:none;padding-left:0;\">" + "".join(
                    f'<li>{"✓" if item["done"] else "○"} '
                    f'<span style="{"color:#6b6" if item["done"] else "color:#aaa"}">'
                    f'{"terminé" if item["done"] else "en attente"}</span> — '
                    f'<code>{html.escape(item["tool_id"])}</code></li>'
                    for item in items
                ) + "</ul>"
            except (json.JSONDecodeError, TypeError, KeyError):
                pass

        token_field_html = (f'<input type="hidden" name="token" value="{html.escape(self.mission_token)}">'
                           if self.mission_token else "")

        done_states = {"COMPLETED", "FAILED", "ABORTED", "BLOCKED", "REJECTED", "EXPIRED",
                      "COMPLETED_WITH_LIMITS", "COMPLETED_WITH_RESERVATIONS"}
        refresh = "" if current_state in done_states else '<meta http-equiv="refresh" content="1.5">'

        body = f"""
{refresh}
<style>body {{ background:#111; color:#eee; font-family:sans-serif; }} a {{ color:#8ab4f8; }} code {{ color:#9cdcfe; }}</style>
<h1>En direct</h1>
<p><a href="/">&laquo; tous les runs</a></p>
<form method="POST" action="/mission" style="margin:12px 0;display:flex;gap:8px;">
  {token_field_html}
  <input name="objective" placeholder="Donner un ordre au modele local..." required
         style="flex:1;padding:8px;background:#222;color:#eee;border:1px solid #444;border-radius:4px;">
  <button type="submit" style="padding:8px 16px;background:#2d5;color:#111;border:none;border-radius:4px;font-weight:600;">Lancer</button>
</form>
<h2>{html.escape(tenant)} / {html.escape(run_id)}</h2>
<p>État actuel : <b>{html.escape(current_state)}</b></p>
{tokens_tile}
<h3>Progression (todo)</h3>
{todo_html}
<h3>Plan</h3>
<pre>{plan_html}</pre>
<h3>Dernières actions (audit)</h3>
<ul>{''.join(recent_actions) or '<li>(aucune encore)</li>'}</ul>
"""
        self._send_html(200, body)

    def _render_index(self) -> None:
        rows = []
        if self.runs_root.is_dir():
            for tenant_dir in sorted(self.runs_root.iterdir()):
                if not tenant_dir.is_dir():
                    continue
                for run_dir in sorted(tenant_dir.iterdir()):
                    if not run_dir.is_dir():
                        continue
                    href = f"/run/{html.escape(tenant_dir.name)}/{html.escape(run_dir.name)}"
                    rows.append(f"<li><a href=\"{href}\">{html.escape(tenant_dir.name)} / {html.escape(run_dir.name)}</a></li>")
        body = f"<h1>Runs (lecture seule)</h1><p><a href=\"/live\">Voir en direct &raquo;</a></p><ul>{''.join(rows) or '<li>Aucun run</li>'}</ul>"
        self._send_html(200, body)

    def _render_run(self, tenant: str, run_id: str) -> None:
        run_dir = (self.runs_root / tenant / run_id).resolve()
        if self.runs_root.resolve() not in run_dir.parents or not run_dir.is_dir():
            self._send_html(404, "<h1>404</h1>")
            return

        def read(name: str) -> str:
            target = run_dir / name
            return target.read_text(encoding="utf-8") if target.is_file() else "(absent)"

        audit_path = run_dir / "audit.jsonl"
        chain_ok, chain_detail = AuditLog.verify(audit_path) if audit_path.is_file() else (False, "audit.jsonl absent")
        verification_raw = read("verification.json")
        try:
            verification = json.loads(verification_raw)
            verification_html = "".join(
                f"<tr><td>{html.escape(v.get('check_id', ''))}</td>"
                f"<td>{html.escape(str(v.get('status', '')))}</td>"
                f"<td>{html.escape(v.get('details', ''))}</td></tr>" for v in verification
            )
            verification_block = f"<table border=1><tr><th>check</th><th>status</th><th>details</th></tr>{verification_html}</table>"
        except json.JSONDecodeError:
            verification_block = f"<pre>{html.escape(verification_raw)}</pre>"

        body = f"""
<h1>Run {html.escape(tenant)} / {html.escape(run_id)}</h1>
<p><a href="/">&laquo; retour</a></p>
<h2>Chaine d'audit</h2>
<p>{'OK' if chain_ok else 'INVALIDE'} — {html.escape(chain_detail)}</p>
<h2>Verification</h2>
{verification_block}
<h2>Plan (PLAN.md)</h2>
<pre>{html.escape(read('PLAN.md'))}</pre>
<h2>Rapport (report.md)</h2>
<pre>{html.escape(read('report.md'))}</pre>
"""
        self._send_html(200, body)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--host", default="127.0.0.1",
                        help="Loopback par defaut. [CORRIGE 19/10/2026 -- ce "
                             "commentaire mentait depuis l'ajout de POST /mission (18/10) : ce "
                             "frontend n'est PLUS lecture seule, POST /mission soumet de vraies "
                             "missions au modele local. Elargir --host SANS --mission-token "
                             "expose cette ecriture a quiconque atteint ce port ; refuse au demarrage.")
    parser.add_argument("--mission-token", default=None,
                        help="[AJOUTE 19/10/2026 -- signale par un audit externe : aucune "
                             "authentification n'existait sur POST /mission] Jeton partage "
                             "requis pour soumettre une mission (en-tete X-Mission-Token ou champ "
                             "cache du formulaire). Obligatoire si --host sort du loopback.")
    parser.add_argument("--root", default=".")
    parser.add_argument("--model", default="q38_9b_s3_gutop.gguf", help="modele servi par llama-server pour les missions lancées depuis /live")
    parser.add_argument("--llm-base-url", default="http://127.0.0.1:8080")
    parser.add_argument("--tenant", default="live-page-tenant")
    parser.add_argument("--allowed-paths", nargs="*", default=["output.txt", "resultat.txt", "notes.md"])
    parser.add_argument("--allowed-urls", nargs="*", default=["https://example.com/", "https://html.duckduckgo.com/html/"])
    args = parser.parse_args()

    if args.host not in ("127.0.0.1", "localhost", "::1") and not args.mission_token:
        parser.error("--host hors loopback exige --mission-token (POST /mission exécute de vraies missions, "
                     "voir docs/threat-model.md) -- refuse de démarrer sans authentification.")

    RunsHandler.mission_token = args.mission_token
    RunsHandler.runs_root = (Path(args.root) / "runs").resolve()
    # [AJOUTÉ 18/10/2026] même engine que mission_loop.py, partagé par tout
    # le process HTTP : la mémoire inter-run (engine.memory) accumule aussi
    # bien les missions lancées depuis /live que celles lancées en CLI.
    RunsHandler.engine = HarnessEngine(Path(args.root))
    adapter = LlamaCppAdapter(LlamaCppProfile(model=args.model, base_url=args.llm_base_url, enabled=True, timeout_seconds=120))
    RunsHandler.planner = LlmPlanner(adapter, memory=RunsHandler.engine.memory)
    RunsHandler.mission_tenant = args.tenant
    RunsHandler.mission_allowed_paths = args.allowed_paths
    RunsHandler.mission_allowed_urls = args.allowed_urls
    server = HTTPServer((args.host, args.port), RunsHandler)
    print(f"Visualiseur de runs sur http://{args.host}:{args.port}/ (POST /mission pour piloter le modele local depuis /live)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

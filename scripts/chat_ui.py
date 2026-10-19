#!/usr/bin/env python3
"""Mini chatbot web, totalement separe du harnais : parle directement a
llama-server (/v1/chat/completions), sans passer par LlmPlanner, PolicyEngine
ou quoi que ce soit du gateway. Pas de validation de securite ici parce
qu'il n'y a rien a securiser : ce script n'execute aucun outil, ne touche
aucun fichier du harnais, ne peut rien approuver. C'est juste une fenetre de
discussion avec le modele, pour tester/discuter, en complement du
visualiseur de runs (view_runs.py) qui lui reste lecture-seule sur le
harnais.

Usage :
    PYTHONPATH=src python3 scripts/chat_ui.py --model q38_9b_s3_gutop.gguf [--port 8788]
"""
from __future__ import annotations

import argparse
import html
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.request import Request, urlopen

PAGE = """<!doctype html>
<html lang="fr"><head><meta charset="utf-8">
<title>Chat local (llama.cpp)</title>
<style>
body {{ font-family: sans-serif; max-width: 760px; margin: 2rem auto; padding: 0 1rem; background: #111; color: #eee; }}
#log {{ border: 1px solid #333; border-radius: 8px; padding: 1rem; min-height: 300px; margin-bottom: 1rem; white-space: pre-wrap; }}
.msg-user {{ color: #8ab4f8; }}
.msg-assistant {{ color: #81c995; }}
.msg-error {{ color: #f28b82; }}
form {{ display: flex; gap: 0.5rem; }}
input[type=text] {{ flex: 1; padding: 0.6rem; border-radius: 6px; border: 1px solid #333; background: #1a1a1a; color: #eee; }}
button {{ padding: 0.6rem 1.2rem; border-radius: 6px; border: none; background: #4285f4; color: white; cursor: pointer; }}
button:disabled {{ opacity: 0.5; cursor: wait; }}
#hint {{ color: #888; font-size: 0.85rem; margin-bottom: 1rem; }}
</style></head>
<body>
<h1>Chat local</h1>
<p id="hint">Modele : {model} &middot; serveur : {base_url} &middot; discussion directe, hors du harnais (aucune policy, aucun outil).</p>
<div id="log"></div>
<form id="form">
  <input type="text" id="input" placeholder="Ecris un message..." autocomplete="off" autofocus>
  <button type="submit" id="send">Envoyer</button>
</form>
<script>
const log = document.getElementById('log');
const form = document.getElementById('form');
const input = document.getElementById('input');
const send = document.getElementById('send');
let history = [];

function append(role, text) {{
  const div = document.createElement('div');
  div.className = 'msg-' + role;
  div.textContent = (role === 'user' ? '> ' : role === 'error' ? '[erreur] ' : '') + text;
  log.appendChild(div);
  log.scrollTop = log.scrollHeight;
}}

form.addEventListener('submit', async (e) => {{
  e.preventDefault();
  const text = input.value.trim();
  if (!text) return;
  append('user', text);
  history.push({{role: 'user', content: text}});
  input.value = '';
  send.disabled = true;
  try {{
    const resp = await fetch('/api/chat', {{
      method: 'POST', headers: {{'Content-Type': 'application/json'}},
      body: JSON.stringify({{messages: history}}),
    }});
    const data = await resp.json();
    if (data.error) {{
      append('error', data.error);
    }} else {{
      append('assistant', data.content);
      history.push({{role: 'assistant', content: data.content}});
    }}
  }} catch (err) {{
    append('error', String(err));
  }} finally {{
    send.disabled = false;
    input.focus();
  }}
}});
</script>
</body></html>
"""


class ChatHandler(BaseHTTPRequestHandler):
    base_url: str
    model: str
    timeout_seconds: int = 90

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        pass

    def do_GET(self) -> None:  # noqa: N802
        if self.path != "/":
            self.send_response(404)
            self.end_headers()
            return
        body = PAGE.format(model=html.escape(self.model), base_url=html.escape(self.base_url)).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/api/chat":
            self.send_response(404)
            self.end_headers()
            return
        length = int(self.headers.get("Content-Length", 0))
        try:
            incoming = json.loads(self.rfile.read(length).decode("utf-8"))
            messages = incoming["messages"]
            payload = json.dumps({"model": self.model, "messages": messages, "stream": False}).encode("utf-8")
            request = Request(self.base_url.rstrip("/") + "/v1/chat/completions", data=payload,
                              headers={"Content-Type": "application/json"}, method="POST")
            with urlopen(request, timeout=self.timeout_seconds) as response:  # nosec B310: loopback, --host local
                raw = json.loads(response.read().decode("utf-8"))
            content = raw["choices"][0]["message"]["content"]
            result = {"content": content}
        except Exception as exc:
            result = {"error": str(exc)}
        payload_out = json.dumps(result).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload_out)))
        self.end_headers()
        self.wfile.write(payload_out)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True, help="id du modele tel qu'expose par /v1/models")
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    parser.add_argument("--port", type=int, default=8788)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()

    ChatHandler.base_url = args.base_url
    ChatHandler.model = args.model
    server = HTTPServer((args.host, args.port), ChatHandler)
    print(f"Chat local sur http://{args.host}:{args.port}/ (modele: {args.model} via {args.base_url})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

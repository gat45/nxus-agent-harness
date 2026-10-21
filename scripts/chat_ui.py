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
    PYTHONPATH=src python3 scripts/chat_ui.py --base-url http://127.0.0.1:8080 [--model q38_9b_s3_gutop.gguf] [--port 8788]

--model est maintenant optionnel : l'interface interroge /v1/models du
serveur connecte et propose un menu pour choisir/changer de modele a
chaque message, sans relancer ce script. --model ne sert plus que de
valeur de repli si /v1/models est injoignable ou vide.
"""
from __future__ import annotations

import argparse
import html
import json
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any
from urllib.request import Request, urlopen

# [AJOUTE 21/10/2026 -- meme classe de bug deja corrigee dans
# llama_cpp_adapter.py/ollama_adapter.py (commit eef1713), jamais reportee
# ici : do_POST lisait la reponse de llama-server avec response.read() brut
# -- aucun plafond de taille, et timeout= sur urlopen() n'est qu'un delai
# PAR OPERATION socket (il se reinitialise a chaque recv() reussi), pas un
# plafond sur la requete entiere. Un serveur loopback buggy/compromis qui
# renvoie un corps enorme (ou l'egoutte lentement) pouvait etre lu en
# entier en memoire sans aucune limite.
_MAX_RESPONSE_BYTES = 8 * 1024 * 1024


def _read_capped(response: Any, *, max_bytes: int = _MAX_RESPONSE_BYTES, deadline_seconds: float) -> bytes:
    deadline = time.monotonic() + deadline_seconds
    chunks: list[bytes] = []
    total = 0
    while True:
        if time.monotonic() > deadline:
            raise ValueError("reponse llama.cpp trop lente (delai total depasse)")
        chunk = response.read(65536)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise ValueError("reponse llama.cpp trop volumineuse")
        chunks.append(chunk)
    return b"".join(chunks)


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
#model-picker {{ display: flex; gap: 0.5rem; align-items: center; margin-bottom: 1rem; }}
#model-picker label {{ color: #aaa; font-size: 0.85rem; }}
#model-select, #model-custom {{ padding: 0.4rem; border-radius: 6px; border: 1px solid #333; background: #1a1a1a; color: #eee; }}
#model-custom {{ display: none; flex: 1; }}
</style></head>
<body>
<h1>Chat local</h1>
<p id="hint">Serveur : {base_url} &middot; discussion directe, hors du harnais (aucune policy, aucun outil).</p>
<div id="model-picker">
  <label for="model-select">Modele :</label>
  <select id="model-select"><option value="">(chargement...)</option></select>
  <input type="text" id="model-custom" placeholder="id du modele" autocomplete="off">
</div>
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
const modelSelect = document.getElementById('model-select');
const modelCustom = document.getElementById('model-custom');
const DEFAULT_MODEL = {default_model_json};
let history = [];

function append(role, text) {{
  const div = document.createElement('div');
  div.className = 'msg-' + role;
  div.textContent = (role === 'user' ? '> ' : role === 'error' ? '[erreur] ' : '') + text;
  log.appendChild(div);
  log.scrollTop = log.scrollHeight;
}}

function applyModelsList(models) {{
  modelSelect.innerHTML = '';
  if (!models.length) {{
    // Aucun modele expose par /v1/models (ou serveur injoignable) : repli
    // sur une saisie libre, pre-remplie avec le modele par defaut passe en
    // ligne de commande.
    modelSelect.style.display = 'none';
    modelCustom.style.display = 'inline-block';
    modelCustom.value = DEFAULT_MODEL;
    return;
  }}
  for (const id of models) {{
    const opt = document.createElement('option');
    opt.value = id;
    opt.textContent = id;
    if (id === DEFAULT_MODEL) opt.selected = true;
    modelSelect.appendChild(opt);
  }}
  const customOpt = document.createElement('option');
  customOpt.value = '__custom__';
  customOpt.textContent = 'Autre (saisir)...';
  modelSelect.appendChild(customOpt);
  modelSelect.addEventListener('change', () => {{
    modelCustom.style.display = modelSelect.value === '__custom__' ? 'inline-block' : 'none';
  }});
}}

function getSelectedModel() {{
  if (modelSelect.style.display !== 'none' && modelSelect.value && modelSelect.value !== '__custom__') {{
    return modelSelect.value;
  }}
  return modelCustom.value.trim() || DEFAULT_MODEL;
}}

fetch('/api/models').then(r => r.json()).then(data => applyModelsList(data.models || []))
  .catch(() => applyModelsList([]));

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
      body: JSON.stringify({{messages: history, model: getSelectedModel()}}),
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
    # [AJOUTE 20/10/2026 -- bug reel trouve par un agent puis verifie en
    # vrai (meme classe que view_runs.py, corrige le 19/10/2026) : HTTPServer
    # ici est single-threaded, et rfile.read(length) bloque sans timeout
    # jusqu'a recevoir `length` octets. Un client qui annonce un
    # Content-Length enorme et retient le corps gele ce serveur pour TOUT
    # LE MONDE (y compris l'operateur qui l'a lance) -- reproduit en vrai
    # par un agent (socket brut, Content-Length: 999999999, GET / concurrent
    # qui timeout). StreamRequestHandler.setup() applique cette valeur via
    # connection.settimeout() avant chaque requete.
    timeout = 10

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        pass

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/":
            body = PAGE.format(default_model_json=json.dumps(self.model), base_url=html.escape(self.base_url)).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path == "/api/models":
            self._handle_models()
            return
        self.send_response(404)
        self.end_headers()

    def _handle_models(self) -> None:
        # [AJOUTE 21/10/2026 -- demande : laisser l'interface elle-meme
        # choisir le modele plutot que de l'imposer en ligne de commande au
        # demarrage. Interroge /v1/models du serveur llama.cpp connecte
        # (route standard, compatible OpenAI) ; best-effort pur, une panne
        # ici ne doit jamais faire planter la page -- le front-end se
        # replie alors sur une saisie libre pre-remplie avec --model.
        try:
            request = Request(self.base_url.rstrip("/") + "/v1/models", method="GET")
            with urlopen(request, timeout=self.timeout_seconds) as response:  # nosec B310: loopback, --host local
                raw_bytes = _read_capped(response, deadline_seconds=self.timeout_seconds)
            raw = json.loads(raw_bytes.decode("utf-8"))
            ids = [str(item["id"]) for item in raw.get("data", []) if isinstance(item, dict) and item.get("id")]
            result: dict[str, Any] = {"models": ids, "default": self.model}
        except Exception as exc:
            result = {"models": [], "default": self.model, "error": str(exc)}
        payload_out = json.dumps(result).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload_out)))
        self.end_headers()
        self.wfile.write(payload_out)

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/api/chat":
            self.send_response(404)
            self.end_headers()
            return
        # [AJOUTE 20/10/2026 -- voir le commentaire sur `timeout` ci-dessus]
        # Un seul message de chat ne depasse jamais quelques Ko ; rejette le
        # corps AVANT de le lire si le Content-Length declare depasse ce
        # plafond large mais fini.
        MAX_CHAT_BODY_BYTES = 65536
        # [AJOUTE 21/10/2026 -- bug reel trouve par un agent puis verifie en
        # vrai : int() accepte une valeur NEGATIVE (ex. "-1") sans lever --
        # le garde `length > MAX_CHAT_BODY_BYTES` ne la rejette pas, et
        # self.rfile.read(length) avec une taille negative signifie "lire
        # jusqu'a EOF" (semantique io/socket standard) : exactement le
        # danger non borne que ce plafond existe pour empecher. Un en-tete
        # non numerique (ex. "abc") levait aussi un ValueError brut, non
        # rattrape. Rejette maintenant toute valeur hors de [0, plafond].
        try:
            length = int(self.headers.get("Content-Length", 0))
        except ValueError:
            self.send_response(400)
            self.end_headers()
            return
        if length < 0 or length > MAX_CHAT_BODY_BYTES:
            self.send_response(413)
            self.end_headers()
            return
        try:
            incoming = json.loads(self.rfile.read(length).decode("utf-8"))
            messages = incoming["messages"]
            # [AJOUTE 21/10/2026 -- demande : laisser l'interface choisir le
            # modele. Le front-end envoie le modele selectionne (liste
            # /api/models ou saisie libre) ; on ne retombe sur --model (la
            # valeur de demarrage) que si le client n'en a pas fourni un
            # valide -- jamais de confiance aveugle dans une chaine vide ou
            # d'un type inattendu venant du navigateur.
            requested_model = incoming.get("model")
            model_to_use = requested_model.strip() if isinstance(requested_model, str) and requested_model.strip() else self.model
            payload = json.dumps({"model": model_to_use, "messages": messages, "stream": False}).encode("utf-8")
            request = Request(self.base_url.rstrip("/") + "/v1/chat/completions", data=payload,
                              headers={"Content-Type": "application/json"}, method="POST")
            with urlopen(request, timeout=self.timeout_seconds) as response:  # nosec B310: loopback, --host local
                raw_bytes = _read_capped(response, deadline_seconds=self.timeout_seconds)
            raw = json.loads(raw_bytes.decode("utf-8"))
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
    parser.add_argument("--model", default="", help="id du modele par defaut (repli si /v1/models est injoignable/vide) ; "
                                                     "sinon choisissable dans l'interface")
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

"""Adaptateur llama.cpp (llama-server) opt-in, pour utiliser des modèles GGUF locaux.

Même contrat que ollama_adapter.py : loopback HTTP uniquement, désactivé par
défaut, aucune requête au démarrage, aucun tool_call transmis au gateway. Le
caller doit valider toute sortie structurée avant usage — ce module ne décide
rien, il ne fait que parler au serveur et renvoyer un dict déjà vérifié pour
la forme (clés requises présentes), jamais pour le fond.

llama-server expose une API compatible OpenAI (/v1/chat/completions). La
sortie structurée est obtenue via "response_format": {"type": "json_object"},
supporté par llama.cpp depuis la version avec décodage contraint par grammaire
JSON ; comme pour Ollama, seule la présence des clés requises du schéma est
vérifiée ici, pas sa conformité complète (la validation métier reste dans le
harness, jamais dans l'adaptateur).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse
from urllib.request import Request, urlopen
import json
import time

from .models import ValidationError


# [AJOUTE 20/10/2026 -- bug reel trouve par un agent puis verifie en vrai
# (serveur HTTP local jetable renvoyant un corps de plusieurs Mio, lu en
# entier sans aucun garde) : `timeout_seconds` passe a urlopen() est un
# timeout PAR OPERATION socket, pas un plafond sur la requete entiere --
# il se reinitialise a chaque recv() reussi. Un pair qui egoutte des octets
# un par un peut tenir la connexion ouverte indefiniment pendant que
# response.read() accumule tout en memoire, sans aucune limite de taille ni
# de temps total. Meme classe de bug que celle corrigee dans view_runs.py
# (Content-Length non plafonne), cote inverse de la frontiere de confiance :
# ici c'est le harness qui consomme une reponse sans garde. Une reponse
# JSON de plan legitime est petite (quelques Ko) ; ce plafond est large par
# securite mais reste fini.
_MAX_RESPONSE_BYTES = 8 * 1024 * 1024


def _read_capped(response: Any, *, max_bytes: int = _MAX_RESPONSE_BYTES, deadline_seconds: float) -> bytes:
    deadline = time.monotonic() + deadline_seconds
    chunks: list[bytes] = []
    total = 0
    while True:
        if time.monotonic() > deadline:
            raise ValidationError("réponse llama.cpp trop lente (délai total dépassé)")
        chunk = response.read(65536)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise ValidationError("réponse llama.cpp trop volumineuse")
        chunks.append(chunk)
    return b"".join(chunks)


def _strip_markdown_code_fence(content: str) -> str:
    """Retire un bloc markdown ```json ... ``` ou ``` ... ``` autour du JSON.

    Vérifié sur un vrai llama-server (modèle Qwen3.8 9B) : malgré
    "response_format": {"type": "json_object"}, ce build ne contraint pas
    strictement le texte produit — le modèle a répondu
    "```json\\n{...}\\n```" au lieu du JSON brut attendu. json.loads() sur
    la chaîne telle quelle échouait alors systématiquement (JSONDecodeError
    dès le premier caractère). Ne modifie pas une chaîne qui est déjà du
    JSON brut.
    """
    # [CORRIGE 20/10/2026 -- bug reel trouve par un agent puis verifie en
    # vrai : exigeait que la fermeture ``` soit le TOUT DERNIER token de la
    # chaine entiere (rstrip().endswith("```")) -- un modele qui ajoute du
    # texte APRES le bloc ferme (commentaire, note, exemple de formatage
    # contenant lui-meme des backticks) faisait echouer ce test, donc RIEN
    # n'etait retire, et json.loads() sur la chaine encore fermee par ```
    # echouait -- alors que le JSON etait parfaitement valide et extractible.
    # Chercher la fermeture ``` par position (premiere ou derniere) est
    # ambigu dans les deux sens : des backticks triples peuvent apparaitre
    # a la fois DANS une valeur de chaine JSON (avant la vraie fermeture)
    # ET dans de la prose APRES elle. Le parseur JSON lui-meme sait
    # exactement ou s'arrete une valeur JSON valide (raw_decode ignore tout
    # ce qui suit) -- plus robuste que toute heuristique sur la position
    # des ```, et marche identiquement pour les deux cas.
    stripped = content.strip()
    without_leading_fence = stripped.split("\n", 1)[1] if stripped.startswith("```") and "\n" in stripped else stripped
    try:
        _, end = json.JSONDecoder().raw_decode(without_leading_fence)
        return without_leading_fence[:end]
    except json.JSONDecodeError:
        return without_leading_fence


@dataclass(frozen=True)
class LlamaCppProfile:
    base_url: str = "http://127.0.0.1:8080"
    model: str = ""
    timeout_seconds: int = 20
    enabled: bool = False
    # [AJOUTÉ 18/10/2026 — trouvé en lisant la fiche du modèle, demandé
    # explicitement] Réglages recommandés par la fiche HuggingFace
    # d'Ornith-1.5-9B-MTP pour un usage général (section sampling) :
    # temp=1.0, top_k=20, top_p=0.95, min_p=0, presence_penalty=1.5. Les
    # défauts serveur observés (GET /props : temp=0.8, top_k=40, min_p=0.05,
    # presence_penalty=0.0) ne les appliquaient JAMAIS -- absence totale de
    # pénalité de présence, cohérente avec le comportement "recopie un
    # texte déjà vu" observé en vrai (mission 1 qui recopiait le brouillon
    # par défaut, mission 2 qui recopiait la mission précédente). Champs
    # explicites plutôt qu'un dict libre : valeurs par défaut documentées
    # ici, jamais devinées par l'appelant.
    temperature: float = 1.0
    top_k: int = 20
    top_p: float = 0.95
    min_p: float = 0.0
    presence_penalty: float = 1.5

    # [AJOUTÉ 18/10/2026 — cause racine confirmée en vrai] La fiche du
    # modèle donne DEUX profils différents, "tâches générales" et "code
    # précis" (temp 1.0 vs 0.6, presence_penalty 1.5 vs 0.0) -- on
    # n'appliquait QUE le profil général, y compris pour execute_python.
    # Testé en vrai sur la même fonction SSRF qui avait produit du code
    # cassé/incohérent toute la session (voir missions précédentes) :
    # avec le profil général, résultat faux ou cassé à chaque essai ;
    # avec le vrai profil code, le code généré a passé un test réel
    # (localhost -> False, 1.1.1.1 -> True) du premier coup. Le modèle
    # n'était pas la cause principale -- le réglage de sampling l'était.
    def sampling_params(self, *, code_task: bool) -> dict[str, float | int]:
        if not code_task:
            return {"temperature": self.temperature, "top_k": self.top_k, "top_p": self.top_p,
                   "min_p": self.min_p, "presence_penalty": self.presence_penalty}
        return {"temperature": 0.6, "top_k": self.top_k, "top_p": self.top_p,
               "min_p": self.min_p, "presence_penalty": 0.0, "repeat_penalty": 1.0}

    def validate(self) -> None:
        parsed = urlparse(self.base_url)
        if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise ValidationError("le MVP n’autorise llama.cpp que sur loopback HTTP")
        if self.timeout_seconds < 1 or self.timeout_seconds > 120:
            raise ValidationError("timeout llama.cpp hors limite")
        if self.enabled and not self.model:
            raise ValidationError("un modèle GGUF/alias llama.cpp épinglé est requis")


class LlamaCppAdapter:
    """Client restreint pour une réponse JSON, sans exécution d’outils.

    `model` doit correspondre à l’identifiant exposé par llama-server sur
    /v1/models (le nom du fichier .gguf, ou l’Alias -a s’il est défini — voir
    _model_ref() dans llama_ui.py pour ce même piège côté lanceur de modèle).
    """

    def __init__(self, profile: LlamaCppProfile) -> None:
        profile.validate()
        self.profile = profile
        self.last_timings: dict[str, Any] | None = None

    def _get_json(self, path: str) -> dict[str, Any]:
        request = Request(self.profile.base_url.rstrip("/") + path, method="GET")
        with urlopen(request, timeout=self.profile.timeout_seconds) as response:  # nosec B310: loopback validated
            raw_bytes = _read_capped(response, deadline_seconds=self.profile.timeout_seconds)
            return json.loads(raw_bytes.decode("utf-8"))

    def model_status(self) -> dict[str, Any]:
        """Lecture seule : contexte réel et métadonnées par modèle exposé par
        le serveur, pour visibilité opérationnelle sur la gestion KV. N'exige
        PAS que le profil soit "enabled" — contrairement à structured_chat(),
        ceci ne fait parler aucun modèle, ne consomme aucun token, et ne
        retourne rien que l'opérateur ne puisse déjà lire via curl ; seule la
        contrainte loopback de validate() s'applique.

        GET /v1/models seul ne reporte QUE n_ctx_train (contexte natif max du
        modèle), jamais le --ctx-size réellement configuré au lancement du
        serveur (vérifié : n_ctx y est toujours null). Ce dernier n'existe
        que dans GET /props ("default_generation_settings.n_ctx" --
        [CORRIGE 20/10/2026 -- bug de doc trouve par un agent puis verifie
        contre les types TypeScript reels de la webui llama.cpp : n_ctx est
        un FRERE de "params" dans default_generation_settings, jamais
        imbrique sous "default_generation_settings.params.n_ctx" comme
        l'affirmait cette docstring avant correction -- "params" ne
        contient que les reglages d'echantillonnage (temp, top_p...),
        jamais n_ctx. Le CODE ci-dessous lisait deja le bon chemin ; seule
        la docstring etait fausse -- un piege pour un futur mainteneur qui
        l'aurait "corrigee" en suivant la doc plutot que le vrai serveur,
        regression que rien n'aurait detectee sans test dedie (voir
        test_t77)], propre au serveur entier (pas par modèle en mode
        routeur multi-modèles) — on le fusionne donc comme n_ctx_configured
        au niveau serveur plutôt que de prétendre qu'il est par-modèle.
        """
        models_raw = self._get_json("/v1/models")
        models = models_raw.get("data") or models_raw.get("models") or []
        status = []
        for model in models:
            meta = model.get("meta") or {}
            status.append({
                "id": model.get("id") or model.get("name"),
                "n_ctx_train": meta.get("n_ctx_train"),
                "n_params": meta.get("n_params"),
                "size_bytes": meta.get("size"),
            })
        n_ctx_configured = None
        total_slots = None
        try:
            props = self._get_json("/props")
            n_ctx_configured = (props.get("default_generation_settings") or {}).get("n_ctx")
            total_slots = props.get("total_slots")
        except Exception:
            pass  # /props absent sur certains builds : dégradation propre, n_ctx_train reste disponible.
        return {"base_url": self.profile.base_url, "n_ctx_configured": n_ctx_configured,
                "total_slots": total_slots, "models": status}

    def structured_chat(self, messages: list[dict[str, str]], schema: dict[str, Any],
                        json_schema: dict[str, Any] | None = None, *, code_task: bool = False,
                        temperature_override: float | None = None) -> dict[str, Any]:
        """`json_schema` (optionnel) : un vrai JSON Schema (type/properties/
        required/enum...), pas le `schema` léger ci-dessus (qui ne sert qu'à
        vérifier après coup la présence des clés requises). Quand fourni,
        llama-server le compile en grammaire GBNF et CONTRAINT la génération
        token par token — vérifié en conditions réelles (llama-server, Qwen3.8
        9B) : avec seulement "response_format": {"type": "json_object"},
        le modèle enveloppait parfois sa réponse dans un bloc markdown
        ```json ... ``` malgré l'instruction système ; avec "json_schema", la
        sortie est du JSON brut à chaque essai, sans fence à retirer. Sans
        `json_schema`, on retombe sur "json_object" (comportement d'origine,
        compatible avec un `schema` léger uniquement)."""
        if not self.profile.enabled:
            raise ValidationError("adaptateur llama.cpp désactivé")
        response_format: dict[str, Any] = (
            {"type": "json_schema", "json_schema": {"name": "structured_output", "schema": json_schema, "strict": True}}
            if json_schema is not None else {"type": "json_object"}
        )
        payload = json.dumps({
            "model": self.profile.model,
            "messages": messages,
            "stream": False,
            "response_format": response_format,
            # [MIS A JOUR 18/10/2026 — cause racine confirmée en vrai] La
            # fiche du modèle donne un profil "code précis" DIFFÉRENT du
            # profil général (temp 0.6 + presence_penalty 0.0 au lieu de
            # 1.0/1.5) -- on envoyait le profil général pour TOUT, y compris
            # execute_python. Vérifié par un test réel exécutant le code
            # produit : profil général -> code cassé/incohérent à chaque
            # essai toute la session ; profil code -> code correct du
            # premier coup (fonction testée, résultat juste). `code_task`
            # est choisi par l'appelant (voir llm_planner.py), jamais deviné
            # ici depuis le contenu des messages.
            # [AJOUTÉ 19/10/2026] temperature_override : pour une persona
            # distincte (ex. skeptical_review.py, température basse,
            # méfiante) sans créer un 3e profil figé dans la dataclass --
            # seule la température change, le reste du profil (top_k etc.)
            # reste celui déjà validé.
            **{**self.profile.sampling_params(code_task=code_task),
               **({"temperature": temperature_override} if temperature_override is not None else {})},
        }).encode("utf-8")
        request = Request(self.profile.base_url.rstrip("/") + "/v1/chat/completions", data=payload,
                          headers={"Content-Type": "application/json"}, method="POST")
        with urlopen(request, timeout=self.profile.timeout_seconds) as response:  # nosec B310: loopback validated
            raw_bytes = _read_capped(response, deadline_seconds=self.profile.timeout_seconds)
            raw = json.loads(raw_bytes.decode("utf-8"))
        # [AJOUTÉ 18/10/2026 — demandé : afficher les tokens/s] llama-server
        # renvoie ses propres mesures de débit dans "timings" à chaque
        # réponse (predicted_per_second = tokens/s de génération réels,
        # mesurés serveur-side — pas une estimation côté client). Exposé en
        # attribut pour que l'appelant (LlmPlanner) puisse le journaliser
        # sans changer la signature de retour de cette méthode.
        self.last_timings: dict[str, Any] | None = raw.get("timings")
        choices = raw.get("choices") or []
        content = choices[0].get("message", {}).get("content") if choices else None
        if not isinstance(content, str):
            raise ValidationError("réponse llama.cpp sans contenu")
        try:
            result = json.loads(_strip_markdown_code_fence(content))
        except json.JSONDecodeError as exc:
            raise ValidationError("sortie structurée llama.cpp invalide") from exc
        if not isinstance(result, dict):
            raise ValidationError("sortie llama.cpp non objet")
        # Validation d’interface minimale ; la validation métier reste dans le harness.
        required = schema.get("required", [])
        if any(key not in result for key in required):
            raise ValidationError("sortie llama.cpp incomplète")
        return result

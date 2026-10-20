"""Avis consultatif séparé, inspiré du rôle "tech lead" d'un autre harnais
comparé le 2026-10-19 (github.com/fabstech-lab/agents-open-code) : une
persona distincte, explicitement méfiante, à température basse, pour les
défauts que le CODE ne peut pas vérifier mécaniquement (texte généré
incohérent, secret en dur hors fixture connue, code mort évident).

Ceci ne remplace RIEN du pipeline déterministe existant (ReflectionReview,
PolicyEngine, run_declared_check/stdout_matches_file) -- c'est exactement
le piège qu'on a identifié chez l'autre harnais : leur "tech lead" est un
LLM qui se contente d'écrire VALIDÉ/À REFAIRE, sans aucune preuve
structurelle que son verdict est fondé. Ici, l'avis produit est marqué
NON CONTRAIGNANT et n'a aucun pouvoir sur RunState -- jamais consulté par
verify_and_complete(), jamais capable de transformer un COMPLETED en
FAILED ou l'inverse. Il est écrit dans un fichier séparé pour un humain,
pas pour le moteur.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .audit import redact
from .llama_cpp_adapter import LlamaCppAdapter


def skeptical_review(adapter: LlamaCppAdapter, *, objective: str, plan_text: str,
                     workspace: Path, results: list[dict[str, Any]]) -> str:
    """Interroge le MÊME modèle local, mais avec une persona et une
    température différentes de LlmPlanner (0.1, méfiant) -- jamais pour
    proposer des opérations, seulement pour relire ce qui a déjà été fait.
    Retourne le texte de l'avis (jamais analysé programmatiquement : un
    humain le lit, le moteur ne le lit jamais).

    [AJOUTE 20/10/2026 -- faille reelle trouvee ET REPRODUITE par un agent :
    cette fonction lisait le contenu BRUT de chaque fichier du workspace
    (jusqu'a 2000 caracteres) et l'envoyait tel quel au endpoint llama.cpp
    local, puis l'ecrivait TEL QUEL dans skeptical_review.txt -- sans
    AUCUNE redaction, contrairement a audit.jsonl qui redacte deja les
    memes motifs (_SECRET_PATTERNS, voir audit.py). engine.py's secret_scan
    detecte deja "TOP_SECRET_" dans le workspace et le fait echouer dans
    verification.json, mais ce FAIL est consultatif seul -- rien n'empeche
    ce fichier d'etre quand meme lu et recopie ici. Si un execute_python
    approuve ECRIT un secret dans le workspace (plutot que de l'afficher
    seulement en stdout, deja plafonne/capture ailleurs), ce chemin en
    produisait une DEUXIEME copie non redigee, persistee sur disque, en
    dehors de toute garantie de redaction documentee
    (docs/threat-model.md : "redaction avant append audit" -- scope
    audit.jsonl uniquement). redact() est reutilise ici tel quel, meme
    motifs que audit.py, pour que cette garantie s'applique aussi a cet
    artefact."""
    workspace_files = "\n".join(
        f"--- {path.relative_to(workspace).as_posix()} ---\n"
        f"{redact(path.read_text(encoding='utf-8', errors='replace')[:2000])}"
        for path in sorted(workspace.rglob("*")) if path.is_file()
    ) or "(workspace vide)"
    results_summary = "\n".join(
        f"- {entry['tool_id']}: {({k: v for k, v in entry['result'].items() if k not in ('stdout', 'stderr', 'content')})}"
        for entry in results
    ) or "(aucune opération exécutée)"

    messages = [
        {"role": "system", "content": (
            "Tu es un relecteur TECHNIQUE MÉFIANT. Ne pars JAMAIS du principe que c'est bon. "
            "Tu ne corriges rien, tu ne decides rien : ton avis est NON CONTRAIGNANT, lu par un humain "
            "uniquement, il ne peut ni valider ni invalider ce run. "
            "Cherche specifiquement : incoherences entre ce qui est annonce et ce qui est reellement ecrit/calcule ; "
            "secrets ou identifiants ecrits en dur (hors fixtures de test connues) ; "
            "code mort ou qui ne sert a rien ; messages d'erreur vides ou peu clairs pour un humain. "
            "Reponds en texte libre, quelques lignes : ce que tu as trouve, ou rien si tu n'as rien trouve de suspect. "
            "Ne repete pas les resultats, dis seulement ce qui te semble louche."
        )},
        {"role": "user", "content": (
            f"Objectif de la mission : {objective}\n\n"
            f"Plan execute :\n{plan_text}\n\n"
            f"Resultats des operations :\n{results_summary}\n\n"
            f"Fichiers presents dans le workspace apres execution :\n{workspace_files}"
        )},
    ]
    try:
        raw = adapter.structured_chat(messages, {"required": ["avis"]},
                                      json_schema={"type": "object", "properties": {"avis": {"type": "string"}},
                                                  "required": ["avis"], "additionalProperties": False},
                                      temperature_override=0.1)
        return raw.get("avis", "")
    except Exception as exc:  # avis consultatif seul : une panne ici ne doit jamais faire echouer le run
        return f"(avis sceptique indisponible : {exc})"

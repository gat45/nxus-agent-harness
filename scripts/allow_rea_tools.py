#!/usr/bin/env python3
"""A LANCER PAR L'UTILISATEUR, jamais par Claude lui-meme (auto-modification
de permissions refusee par le classificateur, a raison). Ajoute une regle
generique "mcp__rea__*" a ~/.claude/settings.json pour autoriser tous les
outils REA en une fois, au lieu d'en debloquer un par un.

Usage :
    py scripts/allow_rea_tools.py            # applique le changement
    py scripts/allow_rea_tools.py --dry-run  # affiche sans modifier
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

SETTINGS_PATH = Path.home() / ".claude" / "settings.json"
RULE = "mcp__rea__*"


def main() -> int:
    dry_run = "--dry-run" in sys.argv
    if not SETTINGS_PATH.is_file():
        print(f"Introuvable : {SETTINGS_PATH}")
        return 1
    data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    permissions = data.setdefault("permissions", {})
    allow = permissions.setdefault("allow", [])
    if RULE in allow:
        print(f"Deja present : {RULE}")
        return 0
    # Retire les regles mcp__rea__<outil> individuelles devenues redondantes
    # (le motif generique les couvre toutes), sans toucher au reste.
    allow[:] = [rule for rule in allow if not (rule.startswith("mcp__rea__") and rule != RULE)]
    allow.append(RULE)
    rendered = json.dumps(data, ensure_ascii=False, indent=2)
    if dry_run:
        print("--- apercu (rien ecrit) ---")
        print(rendered)
        return 0
    SETTINGS_PATH.write_text(rendered + "\n", encoding="utf-8")
    print(f"Ajoute '{RULE}' a {SETTINGS_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

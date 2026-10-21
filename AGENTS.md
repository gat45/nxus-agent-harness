# AGENTS.md — nxus-agent-harness

Ce fichier documente comment travailler sur ce dépôt avec des agents Claude
Code : les deux rôles dédiés disponibles dans `.claude/agents/`, l'état de
la campagne d'audit en cours, et la méthode qui a produit ses correctifs.

## Les deux agents du projet

- **`nxus-bug-hunter`** (`.claude/agents/nxus-bug-hunter.md`) — investigation
  uniquement, jamais d'écriture de code ni de test. On le délègue sur un
  périmètre précis (un fichier, un sous-système, une classe de bug déjà
  trouvée ailleurs à vérifier par mimétisme) ; il revient avec un rapport
  factuel : bugs confirmés et reproduits avec les vraies classes (fichier,
  ligne, séquence d'appel, résultat observé), séparés de ce qui a été
  envisagé puis écarté. La leçon VER-09 (ne jamais rapporter un bug
  seulement théorique, toujours le reproduire en vrai) est câblée dans sa
  définition.
- **`nxus-reasoning-analyst`** (`.claude/agents/nxus-reasoning-analyst.md`) —
  diagnostic de la qualité de raisonnement/proposition du LLM local
  (`LlmPlanner`, grammaire/schéma, profils de sampling, `bench_reasoning_quality.py`).
  Analyse uniquement ; il propose des pistes d'amélioration concrètes
  (fichier:ligne + comment vérifier l'amélioration), jamais de modification
  directe.

Dans les deux cas : l'agent investigue, le mainteneur (la session Claude
Code qui l'a délégué) lit le rapport, implémente le correctif lui-même,
écrit un test de régression, **vérifie que ce test échoue sans le
correctif** (retrait temporaire, test relancé, correctif restauré), relance
la suite complète, puis commit avec `Co-Authored-By: Claude Sonnet 5
<noreply@anthropic.com>` et push. Ce cycle de vérification n'est jamais
sauté — c'est ce qui distingue un correctif confirmé d'une supposition.

## Projet

Harnais de gouvernance agentique local-first : un LLM local (llama.cpp ou
Ollama, loopback uniquement, opt-in) **propose** des plans d'opérations ;
le harnais (machine d'état, policy engine, registre d'outils fermé,
approbations exactes à usage unique, audit chaîné) **autorise et exécute**,
jamais le modèle directement. Voir `README.md` et
`architecture-blueprint.md` pour la vue produit complète ; `docs/threat-model.md`
pour le modèle de menace et ses limites explicitement acceptées (pas de
sandbox OS pour `execute_python`, surface `cmd.exe` résiduelle sur Windows
pour `rea_inspect`/`smokinggun_scan`).

Tests : `PYTHONPATH=src py -m pytest tests/test_harness.py -q`.

## Registre d'outils étendu (2026-10-21)

Sur demande, le registre a été élargi à quatre nouveaux outils, tous sous
le MÊME modèle d'approbation que les outils existants (R1/R2, approbation
exacte obligatoire, `PolicyEngine.authorize()` fail-closed, audit chaîné)
— le modèle de confiance n'a pas changé, seul le registre a grandi :

- `capture_screen` (R1) — capture l'écran de l'opérateur via PowerShell/
  .NET (zéro dépendance ajoutée), chemin de sortie sous la même allowlist
  que `write_workspace_draft`.
- `read_external_file` (R1) — lecture hors workspace, allowlist EXACTE
  dédiée (`allowed_read_paths`, contrat ET manifeste), même principe que
  `allowed_urls` pour `fetch_url`.
- `mcp_call` (R2) — pont vers UN serveur MCP configuré côté serveur
  uniquement (jamais par le modèle), allowlist exacte des noms d'outils
  MCP (`allowed_mcp_tools`).
- `browser_render_page` (R2) — rendu JS réel via un navigateur Chromium
  headless (msedge/chrome déjà installés, zéro dépendance), partage
  l'allowlist et la garde SSRF de `fetch_url`.

Voir commits `3e58947`, `987fc29`, `5462e3f`, `77de2ad`.

## État de la campagne d'audit (2026-10-21)

22 bugs réels trouvés et corrigés à ce jour, chacun avec un test de
régression vérifié (échoue sans le correctif, confirmé par retrait
temporaire). 152 tests. Classes de bugs dominantes rencontrées plusieurs
fois — `nxus-bug-hunter` les connaît déjà, voir sa définition pour le
détail :

1. Succès réel rapporté comme échec (ou l'inverse) par une étape dérivée
   non-autoritaire qui échoue après coup.
2. Parsing non gardé d'entrée réseau non fiable (JSON, en-tête
   `Content-Length` — y compris une valeur **négative** qui contourne un
   garde `> max` naïf).
3. Lectures réseau non bornées (un `timeout=` par opération socket ne
   borne jamais la durée totale).
4. Écritures en deux étapes non atomiques dont la désynchronisation casse
   une logique de cohérence qui supposait les deux liées.
5. Un correctif appliqué à un fichier, jamais reporté sur un fichier
   jumeau quasi identique.
6. Un artefact montré à l'humain (PLAN.md, verification.json/report.md,
   task.json) et un artefact réellement utilisé/exécuté (plan.manifest.json,
   audit.jsonl) jamais revalidés l'un contre l'autre au rechargement.
7. Un mécanisme de supervision (timeout, plafond, kill switch) qui n'a
   prise que sur la ressource directement tracée, pas sur ce qu'elle a pu
   faire naître et qui lui survit.
8. Une garantie affichée à l'humain ("aucun réseau/shell") qui ne
   correspond pas aux opérations réellement proposées/exécutées.

`nxus-reasoning-analyst` a aussi trouvé et fait corriger deux trous dans
le pipeline de proposition (`llm_planner.py`) : la grammaire JSON Schema
forçait toujours TOUTES les propriétés d'un outil comme `required`
(ignorait le `required` réel du `ToolRegistry` — inerte aujourd'hui, mais
prêt à mordre au premier outil avec un argument optionnel), et
`ast.parse("")` n'étant pas une `SyntaxError`, un `execute_python` vide
passait la grammaire ET le filtre syntaxique sans jamais déclencher la
relance.

Derniers commits (voir `git log` pour l'historique complet) :
`4533fbe` (grammaire required réel + code vide + garanties PLAN.md/
report.md conditionnelles), `2be1561` (agents + AGENTS.md intégrés au
projet), `f4e5893` (supervision des descendants détachés d'`execute_python`),
`bdb14c5` (intégrité affichée de verification.json/report.md),
`bd8ce8f` / `aee9da4` (intégrité de task.json / plan.manifest.json au
rechargement), `84f54cd` (audit best-effort dans `_transition()`).

Pistes non encore closes (voir aussi la section "limites connues" de
`docs/threat-model.md`) :

- Pas de CI (`.github/workflows` absent).
- La fenêtre de course résiduelle du Job Object (`tools.py`, entre
  `Popen()` et l'assignation au job) et le chemin POSIX du même correctif
  (`os.killpg`) ne sont documentés/raisonnés que théoriquement — jamais
  vérifiés sur une vraie machine POSIX (environnement de dev = Windows).
- `tests/test_harness.py` est un seul fichier monolithique (3700+ lignes).
- Le banc `scripts/bench_reasoning_quality.py` n'a tourné qu'avec n=4
  essais réels (résultats narratifs dans `README.md`/
  `DOCUMENTATION_SESSION_2026-10-18.md`, aucun artefact structuré
  conservé) — la décision "raisonnement ON" qu'il a motivée est
  anecdotique, pas statistiquement établie (n≈20-30 recommandé).
- `nxus-reasoning-analyst` a identifié une piste d'impact probable élevé
  non encore implémentée (nécessite un vrai serveur llama.cpp pour être
  vérifiée) : un profil de sampling "mixte" pour les plans qui combinent
  `execute_python` (profil code) et un autre outil R2 comme `fetch_url`
  dans le même appel `structured_chat()` — voir son rapport pour le détail.

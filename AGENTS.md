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

## État de la campagne d'audit (2026-10-21)

18 bugs réels trouvés et corrigés à ce jour, chacun avec un test de
régression vérifié (échoue sans le correctif, confirmé par retrait
temporaire). Classes de bugs dominantes rencontrées plusieurs fois —
`nxus-bug-hunter` les connaît déjà, voir sa définition pour le détail :

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

Derniers commits (voir `git log` pour l'historique complet) :
`f4e5893` (supervision des descendants détachés d'`execute_python`),
`bdb14c5` (intégrité affichée de verification.json/report.md),
`bd8ce8f` / `aee9da4` (intégrité de task.json / plan.manifest.json au
rechargement), `84f54cd` (audit best-effort dans `_transition()`).

Pistes non encore closes (voir aussi la section "limites connues" de
`docs/threat-model.md`) :

- Pas de CI (`.github/workflows` absent).
- `docs/threat-model.md:28` ("il n'exécute ni shell ni réseau") est
  devenu faux depuis l'ajout de `fetch_url`/`rea_inspect`/`smokinggun_scan`
  — à corriger.
- La fenêtre de course résiduelle du Job Object (`tools.py`, entre
  `Popen()` et l'assignation au job) et le chemin POSIX du même correctif
  (`os.killpg`) ne sont documentés/raisonnés que théoriquement — jamais
  vérifiés sur une vraie machine POSIX (environnement de dev = Windows).
- `tests/test_harness.py` est un seul fichier monolithique (3500+ lignes).

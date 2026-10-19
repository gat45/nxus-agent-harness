# Documentation complète — travaux du 18/10/2026

Ce document récapitule tout ce qui a été fait sur `nxus-agent-harness` dans cette session : l'arborescence réelle du projet, chaque changement avec sa source (littérature, projet public, ou bug trouvé en testant), et comment vérifier chaque point soi-même.

## 1. Arborescence réelle du projet

```
nxus-agent-harness/
├── README.md                          # vue d'ensemble, démarrage rapide, flux CLI
├── architecture-blueprint.md           # spécification de référence (pré-existant)
├── LICENSE                             # MIT
├── Makefile                            # make test / make demo
├── pyproject.toml
├── .gitignore                          # exclut runs/, memory/, build/, dist/, *.spec
│
├── src/nxus_harness/                   # cœur du harnais
│   ├── __init__.py
│   ├── __main__.py                     # point d'entrée `python -m nxus_harness`
│   ├── cli.py                          # commandes : demo, submit, approve, verify-audit, devil-advocate
│   ├── engine.py                       # machine d'états, orchestration plan→approbation→exécution→vérification
│   ├── models.py                       # TaskContract, PlanManifest, RiskLevel, RunState, etc.
│   ├── policy.py                       # PolicyEngine — toutes les décisions d'autorisation, fail-closed
│   ├── tools.py                        # ToolRegistry + ToolGateway — le registre fermé d'outils et leur exécution
│   ├── planner.py                      # SimulatedPlanner (déterministe) + ReflectionReview + DevilAdvocate
│   ├── llm_planner.py                  # LlmPlanner — un modèle local PROPOSE le plan (ajouté cette session)
│   ├── llama_cpp_adapter.py            # adaptateur llama.cpp/GGUF (ajouté cette session)
│   ├── ollama_adapter.py               # adaptateur Ollama (pré-existant, même contrat)
│   ├── memory.py                       # MemoryStore — mémoire persistante inter-run (ajouté cette session)
│   ├── approvals.py                    # ApprovalService — grants exacts, TTL, usage unique (pré-existant)
│   ├── audit.py                        # AuditLog — journal JSONL chaîné par hash, redaction (pré-existant)
│   └── evidence.py                     # EvidenceStore — provenance evidence → claim (pré-existant)
│
├── tests/
│   └── test_harness.py                 # 36 tests (T01 à T25, voir section 4)
│
├── scripts/                            # outils opérationnels et tests d'intégration réels
│   ├── nxus_harness_entry.py           # point d'entrée pour PyInstaller (ajouté)
│   ├── view_runs.py                    # visualiseur web lecture-seule des runs (ajouté)
│   ├── chat_ui.py                      # mini-chat web direct vers llama-server (ajouté)
│   ├── llama_cpp_kv_status.py          # lecture seule du contexte/KV d'un llama-server (ajouté)
│   ├── smoke_llama_cpp_adapter.py      # test réel : adaptateur + vrai llama-server (ajouté)
│   ├── smoke_llm_planner.py            # test réel : modèle propose un plan + mémoire inter-run (ajouté)
│   ├── smoke_agentic_execution.py      # test réel : code + fetch_url bout en bout (ajouté)
│   ├── bench_reasoning_quality.py      # comparaison raisonnement on/off, vitesse ET fiabilité (ajouté)
│   ├── verify-audit-chain, replay-run, validate-contracts   # scripts pré-existants
│
├── fixtures/
│   ├── corpus.md                       # corpus de test (contenu hostile inclus, pour T03)
│   └── task-code-change.json           # contrat de démo par défaut
│
├── config/
│   ├── policy.yaml, runtime-profile.simulated.yaml, tool-registry.yaml
│
├── contracts/                          # schémas JSON (task-contract, plan-manifest, approval-grant, audit-event)
│
├── docs/
│   ├── threat-model.md                 # modèle de menace — mis à jour cette session (section R2)
│   └── runbooks/approval.md, rollback.md, incident-stop.md
│
├── research/                           # 23 analyses sourcées
│   ├── 01 à 22 : analyses pré-existantes (NXUS, Rudy, Superpowers, Ollama, MCP, etc.)
│   ├── 23-litterature-academique-2026.md   # revue arXiv/GitHub (ajouté cette session)
│   └── README.md                       # index
│
├── runs/                               # généré à l'exécution (ignoré par git)
├── memory/                             # généré à l'exécution (ignoré par git)
├── build/, dist/, *.spec               # générés par PyInstaller (ignorés par git)
└── DOCUMENTATION_SESSION_2026-10-18.md # ce fichier
```

**~2900 lignes** de code source+tests+scripts au total (`src/` + `tests/` + `scripts/`).

## 2. Ce qui existait déjà avant cette session

Le projet `nxus-agent-harness` était un MVP de gouvernance R0/R1 : machine d'états, policy engine fail-closed, approbations exactes, audit chaîné, provenance, kill switch, adaptateur Ollama optionnel. Documenté dans `NXUS Agent Harness — MVP local-first.md` et `architecture-blueprint.md`, construit à partir de 22 analyses publiques (NXUS, Rudy, Superpowers, Ollama, Open WebUI, AnythingLLM, MCP, collecteurs Web — dossier `research/`). Ce code n'avait **jamais été extrait** de son zip (`nxus-agent-harness-mvp.zip`) ni commité en git avant cette session.

## 3. Ce qui a été ajouté/corrigé, par ordre chronologique

### 3.1 Extraction et premier bug (commit `10227d0b`)
- Le vrai projet (structure complète : `src/`, `tests/`, `research/`, `architecture-blueprint.md`) était enfermé dans `nxus-agent-harness-mvp.zip`, jamais décompressé — des fichiers en vrac et incohérents traînaient à côté. **Extrait.**
- **Bug trouvé** : `engine.py` comparait un `Path` Windows (séparateur `\`) à des `allowed_paths` écrits en JSON avec `/` → le contrôle `scope` échouait systématiquement sous Windows sur un run par ailleurs conforme. Corrigé avec `.as_posix()`.
- **Ajouté** : `llama_cpp_adapter.py` (adaptateur llama.cpp/GGUF, même contrat que l'adaptateur Ollama pré-existant : loopback uniquement, désactivé par défaut).
- **Ajouté** : `llm_planner.py` — un modèle local PROPOSE le plan au lieu du `SimulatedPlanner` déterministe ; aucune autorité supplémentaire, même pipeline de validation.
- **Ajouté** : `memory.py` — mémoire persistante inter-run par tenant.
- Tests : 13 → 22.

**Source** : aucune externe, bug + architecture trouvés en lisant et testant le code existant.

### 3.2 Grammaire GBNF, OWASP, revue de littérature (commit `039d3a32`)
- **Trouvé en testant** : avec `response_format: json_object` seul, le modèle enveloppait parfois sa réponse dans un bloc markdown ` ```json ... ``` `, cassant le parsing JSON. Remplacé par un vrai JSON Schema (`response_format: json_schema`), compilé par `llama-server` en grammaire GBNF qui contraint la génération token par token.
- **Source** : doc llama.cpp sur les sorties structurées — [docs.liquid.ai/deployment/on-device/llama-cpp/structured-output](https://docs.liquid.ai/deployment/on-device/llama-cpp/structured-output.md), confirmé par `llama-server --help` (`response_format` accepte `json_schema`).
- **Ajouté** : traçabilité OWASP LLM Top-10 sur chaque décision de `PolicyEngine` (ex. `P-STATE-001` → *LLM06:2025 Excessive Agency*).
- **Source** : idée reprise d'AgentGate (github.com/agentkitai), une gateway d'approbation publique qui fait la même chose — trouvée par recherche web.
- **Revue de littérature complète** dans `research/23-litterature-academique-2026.md` : 5 papiers arXiv évalués (2607.07405 "Reason Less, Verify More" — valide empiriquement l'architecture existante, portes déterministes 29,6%→42,0% de succès ; 2606.28679 "Capability Gates Are Not Authorization" ; 2603.20449 solveur SMT ; 2512.12806 sandboxing transactionnel ; 2601.08012 MCP à capacités étiquetées) + 2 projets publics (AgentGate, Keep), avec pour chacun ce qui a été adopté **et ce qui a été explicitement écarté** et pourquoi.
- Tests : 22 → 24.

### 3.3 Correctif d'ordonnancement (commit `bf55a133`)
- **Trouvé en testant en vrai** : le modèle a une fois proposé `run_declared_check` AVANT `write_workspace_draft` — comme les opérations s'exécutent dans l'ordre de la liste, le contrôle a tourné sur un fichier inexistant, échoué, jamais relancé après l'écriture. Le harnais a refusé le run à raison, mais pour une erreur évitable. Prompt du `LlmPlanner` clarifié : l'ordre de la liste est l'ordre d'exécution réel.

### 3.4 Chat UI (commit `cbf73a56`)
- **Ajouté** à la demande de l'utilisateur : `scripts/chat_ui.py`, un mini-chat web totalement séparé du harnais (parle direct à `llama-server`, ne passe par aucune validation de policy — rien à sécuriser puisqu'il n'exécute aucun outil).

### 3.5 Humain réellement dans la boucle (commit `0bc66a9c`)
- **Bug de conception trouvé** en relisant `engine.py` après une critique directe de l'utilisateur ("c'est un harnais pour avoir des agents... comment un humain va l'utiliser ?") : `run_demo()`/`run_with_llm()` enchaînaient planification + **approbation automatique** + exécution dans le MÊME appel Python. La mécanique d'approbation (grants exacts, TTL, usage unique) était réelle et testée, mais rien ne la déclenchait depuis une vraie lecture humaine — c'était du théâtre de bout en bout.
- **Corrigé** : `HarnessEngine.submit()` (crée+planifie, s'arrête à `AWAITING_APPROVAL`), `resume_run()` (recharge un `RunContext` complet depuis le disque — `task.json`, `state.json`, `plan.manifest.json`), `approve_and_run()`. Commandes CLI `submit`/`approve` séparées. Testé en vrai avec deux process Python distincts (pas juste des tests unitaires).
- **Ajouté** : `PlanManifest.from_dict()`/`PlannedOperation.from_dict()` (symétriques aux `to_dict()` existants), nécessaires pour recharger un plan depuis le disque.
- Tests : 24 → 28.

### 3.6 Exécution de code réelle + accès internet encadré (commit `1a621d31`)
- **À la demande explicite de l'utilisateur** ("le harnais doit pouvoir créer modifier exécuter du code, aller sur internet"), suivant le propre processus documenté du projet (`docs/threat-model.md`, section "Conditions avant un connecteur R2+"), pas en silence.
- **Ajouté** : `TaskProfile.AGENTIC_EXECUTION` (seul profil avec accès aux nouveaux outils), `RiskLevel` R1→R2, `TaskContract.allowed_urls` (allowlist exacte, même logique que `allowed_paths`).
- **Ajouté** : outil `execute_python` (exécute vraiment du code, `subprocess`, cwd fixé au workspace, timeout dérivé de `budget_seconds`, sortie tronquée) et `fetch_url` (requête HTTP réelle, allowlist exacte + garde SSRF contre les hôtes privés/loopback/link-local).
- **Bug SSRF trouvé en documentant la checklist** : `urlopen()` suit les redirections HTTP par défaut — une URL autorisée pouvait rediriger (302) vers un hôte privé (ex. l'IP de métadonnées cloud `169.254.169.254`) et contourner la garde après coup. **Corrigé** avec un opener qui bloque toute redirection ; vérifié contre un vrai serveur local qui redirige vers cette IP.
- Testé de bout en bout en vrai (`scripts/smoke_agentic_execution.py`) : le modèle a proposé du code Python (calcul 17×23) et une URL, un humain a approuvé dans un process séparé, le code a tourné et écrit le bon résultat, la page `example.com` a été réellement récupérée.
- Tests : 28 → 34.

### 3.7 Bug de vérification de contenu (commit `8229a8b5`)
- **Trouvé en comparant la qualité du raisonnement on/off** (4 essais réels de la tâche agentique) : 2 essais sur 4 finissaient `COMPLETED` avec un `resultat.txt` **faux**. Cause : `declared_check` valait `NOT_APPLICABLE` pour `AGENTIC_EXECUTION` (ne s'appliquait qu'à `CODE_CHANGE`) — le contrôle `scope` vérifie l'EMPLACEMENT d'une écriture, jamais son CONTENU.
- **Corrigé** : `declared_check` requis aussi pour `AGENTIC_EXECUTION` ; `run_declared_check` gagne un vérificateur `file_equals:<chemin>:<contenu attendu>` (en plus de `draft_exists`) ; prompt du `LlmPlanner` mis à jour pour que le modèle termine son plan par ce contrôle.
- Tests : 34 → 36.

### 3.8 Décision utilisateur : raisonnement gardé actif (commit `2cee66e5`)
- Mesuré en vrai : `--reasoning off` ≈ 40% plus rapide (2,5-11s) mais nettement moins fiable sur une tâche à plusieurs outils (omissions de `fetch_url`/`run_declared_check`, URL hors allowlist). **Décision : raisonnement laissé activé** — documentée dans le README pour ne pas revenir en arrière par erreur.

### 3.9 Exécutable autonome (commits `7732a8ea`, `2e48bd2c`)
- **Ajouté** : `dist/nxus-harness.exe` via PyInstaller (~9,7 Mo, aucune dépendance externe).
- **Bug de packaging trouvé** : `_project_root()` se basait sur `__file__`, qui pointe vers le dossier d'extraction temporaire de PyInstaller une fois figé — `runs/`/`fixtures/` se seraient retrouvés au mauvais endroit. **Corrigé** (détection `sys.frozen`, retombe sur le dossier courant).
- **Second bug trouvé** (rapporté par l'utilisateur, "l'exe marche pas") : l'exe distribué seul (sans le reste du dépôt) échouait faute de `fixtures/`. **Corrigé** : `_ensure_default_fixtures()` les crée automatiquement avec le même contenu que celles du dépôt, uniquement si absentes.
- Testé en vrai à chaque étape, depuis un dossier complètement vide, sans Python installé à côté.

## 4. Tests (36 au total, `tests/test_harness.py`)

| Plage | Sujet |
|---|---|
| T01, T03 | Parcours complet + audit ; contenu hostile non fiable |
| T05 | Grants : usage unique, liaison exacte, expiration |
| T06, T07, T08 | Refus R4, schéma strict, traversal de chemin |
| T10, T11, T12, T14 | Claim non sourcé, redaction secret, kill switch, isolation tenant |
| T15, T16 | Adaptateurs Ollama/llama.cpp distants refusés |
| T17 | RAG local avec provenance réelle |
| T18 | `LlmPlanner` : complète comme le planificateur simulé, rejette hors-périmètre, rejette réponse malformée |
| T19 | Mémoire inter-run : persiste, isolée par tenant, apparaît dans le prompt |
| T20 | Schéma JSON strict envoyé au modèle |
| T21 | Tag OWASP sur les refus de policy |
| T22 | `submit`/`resume_run`/`approve_and_run` — humain dans la boucle |
| T23 | `execute_python` réel, timeout, `fetch_url` allowlist + garde SSRF |
| T24 | `fetch_url` ne suit pas les redirections vers un hôte privé |
| T25 | `declared_check` détecte un résultat de calcul faux |

Lancer : `PYTHONPATH=src python3 -m unittest discover -s tests -v`

## 5. Comment vérifier chaque point soi-même

```bash
cd nxus-agent-harness

# Suite de tests complète
PYTHONPATH=src python3 -m unittest discover -s tests -v

# Démo simple (planificateur déterministe, tout automatique)
PYTHONPATH=src python3 -m nxus_harness demo

# Flux réel humain-dans-la-boucle (lance llama-server sur :8080 au préalable)
PYTHONPATH=src python3 -m nxus_harness submit --contract fixtures/task-code-change.json --llm <ton-modele.gguf>
PYTHONPATH=src python3 -m nxus_harness approve demo-tenant <run-id> --actor operator-demo

# Exécution de code + internet réels (profil AGENTIC_EXECUTION)
PYTHONPATH=src python3 scripts/smoke_agentic_execution.py <ton-modele.gguf>

# Visualiseur web des runs (lecture seule)
PYTHONPATH=src python3 scripts/view_runs.py --port 8787

# Chat direct avec le modèle (hors harnais)
PYTHONPATH=src python3 scripts/chat_ui.py --model <ton-modele.gguf> --port 8788

# Exe autonome (zéro setup, fixtures auto-créées)
dist/nxus-harness.exe demo
```

## 6. Sources externes citées

- [arXiv 2607.07405 — Reason Less, Verify More](https://arxiv.org/pdf/2607.07405)
- [arXiv 2606.28679 — Capability Gates Are Not Authorization](https://www.emergentmind.com/papers/2606.28679)
- [arXiv 2603.20449 — Solver-Aided Verification of Policy Compliance](https://arxiv.org/abs/2603.20449)
- [arXiv 2512.12806 — Fault-Tolerant Sandboxing for AI Coding Agents](https://arxiv.org/html/2512.12806v1)
- [arXiv 2601.08012 — Towards Verifiably Safe Tool Use for LLM Agents](https://alphaxiv.org/abs/2601.08012)
- [llama.cpp structured output (json_schema/GBNF)](https://docs.liquid.ai/deployment/on-device/llama-cpp/structured-output.md)
- AgentGate (github.com/agentkitai) — gateway d'approbation, tags OWASP LLM Top-10
- Keep (github.com/majorcontext) — gateway de policy YAML (évaluée, non reprise — voir `research/23-litterature-academique-2026.md`)

Détail complet de ce qui a été lu, adopté, et explicitement écarté : `research/23-litterature-academique-2026.md`.

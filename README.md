# NXUS Agent Harness — MVP local-first

Un **harness agentique** qui sépare strictement le modèle (proposition), le plan de contrôle (autorisation), l’exécution bornée et la vérification indépendante. Il a été construit à partir de l’étude des ressources publiques NXUS, Rudy, Superpowers, Deep Research, Ollama, Open WebUI, AnythingLLM, MCP et des briques de collecte Web. Les méthodes sont reprises comme des **références publiques** ; aucun code privé ni prompt système privé n’est utilisé.

> **Positionnement :** ce dépôt est un MVP de gouvernance et de test, désormais R0–R2. Le cœur reste sans shell libre, navigateur, MCP, secret, paiement, e-mail ou déploiement. Le registre d'outils réel comprend aujourd'hui **huit** outils — pas deux : `read_fixture`/`retrieve_fixture`/`run_declared_check` (R0, lecture), `write_workspace_draft` (R1), `execute_python`/`fetch_url` (R2, approbation exacte requise), `request_rea_analysis` (R0, relais asynchrone), `rea_inspect` (R1, sous-commandes lecture seule allowlistées), `smokinggun_scan` (R0, analyse statique) et `jacobian_verify` (R0, calcul mathématique pur). **Correctif de dérive doc/code du 2026-10-19** : ce README n'en mentionnait que deux avant cette mise à jour, alors que les six autres étaient déjà dans `policy.py`/`tools.py` et autorisés en profil `AGENTIC_EXECUTION` — voir `docs/threat-model.md`, section "Connecteurs R2" pour les limites de chacun.

## Ce qui fonctionne maintenant

- **Contrat de tâche** validé (`TaskContract`) : objectif, critères d’acceptation, profil, risque, chemins et outils autorisés.
- **Machine d’états** persistée : `INTAKE → DISCOVERY → DRAFTING_PLAN → REFLECTION_REVIEW → AWAITING_APPROVAL → APPROVED → EXECUTING → VERIFYING → SECURITY_GATE → COMPLETED`.
- **Plan humain `PLAN.md`** et **manifeste machine JSON** liés par hash.
- **Approbations exactes** : liées à l’acteur, au run, au hash de manifeste, à l’outil et aux arguments normalisés ; elles expirent et ne sont consommables qu’une fois.
- **Registre d’outils fermé** : lecture de fixtures, retrieval local, écriture de brouillon dans un workspace isolé et contrôle déclaré. Un faux outil R4 (`send_external_message`) existe seulement pour vérifier le refus.
- **Policy engine fail-closed** : le modèle, un document, un résultat d’outil ou une description MCP ne peuvent pas élargir une permission.
- **Provenance** `evidence → source` et validation des claims critiques.
- **Audit JSONL redacted** et chaîné par hash, avec vérificateur intégré.
- **Kill switch** : révoque les grants non consommés et fait passer le run à `ABORTED`.
- **Adaptateur Ollama optionnel** : désactivé par défaut, loopback HTTP uniquement, aucune exécution directe de `tool_calls`.
- **Adaptateur llama.cpp optionnel** (`llama_cpp_adapter.py`, modèles GGUF via `llama-server`) : même contrat qu’Ollama — désactivé par défaut, loopback HTTP uniquement, aucune exécution directe de `tool_calls`. Testé de bout en bout contre un `llama-server` réel (`scripts/smoke_llama_cpp_adapter.py`).
- **Visibilité KV/contexte** (`scripts/llama_cpp_kv_status.py`) : lecture seule du contexte réellement configuré (`/props`) et des métadonnées par modèle (`/v1/models`) d’un `llama-server` local — aide à diagnostiquer un contexte mal dimensionné sans jamais faire parler le modèle.
- **RAG local réel** : `retrieve_fixture` enregistre maintenant une `Evidence` tracée par ligne trouvée (locator + excerpt), au lieu de renvoyer des correspondances sans provenance.
- **Visualiseur de runs en lecture seule** (`scripts/view_runs.py`) : frontend minimal stdlib (aucune dépendance), sert `PLAN.md`/`report.md`/`verification.json`/l’état de la chaîne d’audit par run. Aucune route d’écriture, d’approbation ou d’exécution — ne peut structurellement pas contourner le policy engine.
- **Raisonnement réel optionnel** (`llm_planner.py`, `LlmPlanner`) : un modèle local (via `llama_cpp_adapter.py`) PROPOSE le plan d’opérations au lieu du `SimulatedPlanner` déterministe. Le modèle n’autorise, n’exécute et ne modifie rien — toute proposition retraverse exactement le même `ReflectionReview` puis `PolicyEngine` qu’un plan simulé. Testé de bout en bout contre un `llama-server` réel (`scripts/smoke_llm_planner.py`) : plan proposé, validé et exécuté avec succès.
- **Mémoire persistante inter-run** (`memory.py`, `MemoryStore`) : contrairement à `evidence.jsonl` (par run), chaque run terminé laisse une entrée par tenant qui survit aux runs suivants. `LlmPlanner` peut relire les N derniers runs d’un tenant pour informer sa proposition — contexte seul, aucun droit accordé. Testé de bout en bout : un 2ᵉ run réel voit effectivement le 1ᵉʳ dans son prompt.
- **Sortie LLM contrainte par grammaire (GBNF)** : `LlmPlanner` envoie désormais un vrai JSON Schema (`response_format: json_schema`, une branche par outil autorisé avec `tool_id` en `const`) au lieu de `json_object` seul. Trouvé en comparant à la doc llama.cpp sur les sorties structurées : avec `json_object` seul, un modèle réel (Qwen3.8 9B) enveloppait parfois sa réponse dans un bloc markdown ` ```json ... ``` ` malgré l’instruction système ; `json_schema` contraint la génération token par token, donc du JSON brut à chaque essai.
- **Traçabilité OWASP LLM Top-10** (`policy.py`) : chaque décision de `PolicyEngine` qui refuse une opération porte désormais le risque OWASP LLM qu’elle mitige (ex. `P-STATE-001` → *LLM06:2025 Excessive Agency*), visible dans `audit.jsonl`. Idée reprise d’une gateway d’approbation publique (AgentGate) qui fait la même chose. Annotation pure, aucune décision changée.
- **Humain réellement dans la boucle** (`HarnessEngine.submit`/`approve_and_run`/`resume_run`, commandes CLI `submit`/`approve`) : jusqu’ici, `run_demo()`/`run_with_llm()` enchaînaient planification + approbation + exécution dans le MÊME appel Python — personne ne lisait jamais vraiment `PLAN.md` avant que l’approbation soit accordée automatiquement. `submit` crée et planifie un run puis S’ARRÊTE à `AWAITING_APPROVAL` ; `approve` (une commande SÉPARÉE, dans un autre process) recharge le run depuis le disque, réaffiche le plan, demande une confirmation explicite, et n’exécute que sur un oui. Testé de bout en bout en deux process distincts, y compris avec `--llm` (le modèle propose, l’humain décide dans un process différent).
- **Exécution de code et accès réseau réels, encadrés (R2)** : profil `AGENTIC_EXECUTION` avec deux nouveaux outils — `execute_python` (code Python réellement exécuté dans le workspace du run, timeout dérivé de `budget_seconds`, sortie plafonnée) et `fetch_url` (requête HTTP réelle, allowlist EXACTE `contract.allowed_urls`/`manifest.allowed_urls`, garde SSRF sur l'hôte de départ ET sur toute redirection — les deux testées en conditions réelles, y compris contre l'IP de métadonnées cloud `169.254.169.254`). Les deux restent R2 (approbation exacte requise, jamais auto-exécutés) ; voir `docs/threat-model.md` pour la checklist "Conditions avant un connecteur R2+" appliquée et ses limites explicites (pas de sandbox OS). Testé de bout en bout contre un `llama-server` réel : le modèle a proposé du code + une URL, approuvés dans un process séparé, exécutés avec le résultat attendu (`scripts/smoke_agentic_execution.py`).

## Raisonnement du modèle local : laissé activé

Mesuré en conditions réelles (`scripts/bench_reasoning_quality.py`, 4 essais de la tâche `AGENTIC_EXECUTION` réelle) : `--reasoning off` rend `llama-server` ~40 % plus rapide (2.5–11s contre plus lent avec le raisonnement), mais le modèle (9B) devient nettement moins fiable sur une tâche à plusieurs outils — il a omis `fetch_url` ou `run_declared_check`, ou proposé une URL hors allowlist, dans plusieurs essais sur 4. **Décision : raisonnement laissé activé** (`--reasoning on`, le défaut). La vitesse n'est pas retenue au prix de la fiabilité sur ce genre de tâche.

## Démarrage rapide

Prérequis : Python 3.11+ ; aucun package externe n’est requis pour le MVP.

```bash
cd nxus-agent-harness
make test
make demo
```

Ou sans `make` :

```bash
PYTHONPATH=src python3 -m nxus_harness demo
PYTHONPATH=src python3 -m nxus_harness devil-advocate "Faut-il élargir le périmètre ?" --assumption "Le runner est suffisamment isolé"
```

**Flux réel avec un humain dans la boucle** (recommandé plutôt que `demo`, qui approuve tout seul) :

```bash
# 1. Soumettre une tâche — s'arrête pour approbation, affiche le plan
PYTHONPATH=src python3 -m nxus_harness submit --contract fixtures/task-code-change.json
# optionnel : --llm <modele-expose-par-llama-server> pour que le plan soit
# réellement proposé par un modèle local au lieu du planificateur simulé

# 2. Dans un AUTRE terminal (ou plus tard) : lire le plan et décider
PYTHONPATH=src python3 -m nxus_harness approve demo-tenant <run-id> --actor operator-demo
```

## Exécutable autonome (.exe Windows)

Pour utiliser le harnais sans installer Python : un `.exe` autonome (PyInstaller, ~10 Mo, aucune dépendance externe au MVP) expose les mêmes commandes (`demo`, `submit`, `approve`, `verify-audit`, `devil-advocate`).

```bash
python3 -m pip install pyinstaller
python3 -m PyInstaller --onefile --name nxus-harness --paths src scripts/nxus_harness_entry.py
```

Produit `dist/nxus-harness.exe`. Testé en conditions réelles depuis un dossier totalement vide, sans checkout Python à côté — fonctionne tel quel (`runs/` et `fixtures/` relatifs au dossier où l'exe est lancé, pas à son emplacement d'installation ; voir le correctif `_project_root()` dans `cli.py`) :

```bash
cp dist/nxus-harness.exe fixtures/*.json fixtures/*.md /un/dossier/vide/
cd /un/dossier/vide
./nxus-harness.exe demo
```

La démonstration crée un dossier sous `runs/demo-tenant/<run-id>/` contenant notamment :

```text
PLAN.md                 # plan relisible par un humain
plan.manifest.json      # périmètre exécutable et hashé
approvals.json          # grants exacts, jamais réutilisables
audit.jsonl             # journal append-only et redacted
evidence.jsonl          # sources/évidences de fixture
verification.json       # résultats pass/fail/not_run
report.md               # comparaison plan, exécution et limites
workspace/              # seul répertoire modifiable par le MVP
```

Pour vérifier un audit :

```bash
PYTHONPATH=src python3 -m nxus_harness verify-audit runs/demo-tenant/<run-id>/audit.jsonl
```

## Règles d’autorité

| Élément | Peut faire | Ne peut pas faire |
|---|---|---|
| Modèle / planificateur | Proposer un plan structuré, une critique et des opérations prévues | Octroyer un droit, appeler un outil directement, modifier la politique |
| Policy engine | Valider état, risque, profil, outil, chemin et manifeste | Produire du contenu métier ou inférer une approbation |
| Approval service | Émettre et consommer un grant précis | Créer une approbation générale ou durable |
| Tool gateway | Valider puis exécuter un outil enregistré | Exécuter shell/réseau/MCP inconnu ou hors manifeste |
| Verifier / security gate | Comparer les preuves et bloquer les manques | Transformer un test absent en succès |

## Profils et portée

| Profil | MVP | Risque maximal | État |
|---|---:|---:|---|
| `QA_READONLY` | corpus local | R0 | actif |
| `DECISION_CHALLENGE` | objections structurées, sans verdict | R0 | actif |
| `RESEARCH_READONLY` | fixtures locales uniquement | R0 | actif |
| `CODE_CHANGE` | brouillon dans workspace éphémère | R1 | actif |
| `SECURITY_REVIEW` | contrôles locaux déclarés | R0 | actif partiel |
| `AGENTIC_EXECUTION` | code Python exécuté, requête HTTP allowlistée | R2 | actif |
| `EXTERNAL_ACTION` | — | R3/R4 | explicitement refusé |

## Tests inclus

La suite `unittest` couvre notamment : parcours complet et audit, contenu hostile non fiable, grants expirés/rejoués/modifiés, refus des effets externes, schéma d’arguments strict, traversal de chemin, claim critique non sourcé, redaction de secret, kill switch, isolation par tenant et adaptateurs Ollama/llama.cpp distants refusés.

Ces contrôles matérialisent les scénarios T01 à T15 du [blueprint d’architecture](architecture-blueprint.md). Ils testent uniquement des fixtures et un environnement local autorisé.

## Architecture et sources de conception

Le [blueprint d’architecture](architecture-blueprint.md) est la spécification de référence : principes d’autorité, niveaux R0–R4, mémoire/provenance, broker MCP, profils d’intégration, matrice d’adoption, 15 scénarios de test et séquencement de mise en œuvre. Les 22 analyses détaillées et sourcées sont indexées dans [research/README.md](research/README.md).

Les décisions importantes sont les suivantes :

1. Les `SKILL.md` et les playbooks sont des **protocoles de travail**, pas des mécanismes de sécurité exécutables.
2. MCP est un **transport/adaptateur**, pas le policy engine ; tout serveur MCP doit passer par un broker et une sandbox dédiés.
3. Ollama est un **moteur de modèle local** facultatif ; ses sorties et tool calls restent non fiables jusqu’à validation par le harness.
4. Open WebUI et AnythingLLM sont des **interfaces ou workspaces possibles**, jamais l’autorité de décision.
5. Firecrawl, Crawlee, Scrapling et Supadata sont des **collecteurs optionnels** lecture seule et doivent être isolés derrière budgets, provenance, egress allowlist et protections SSRF.

## Hors périmètre volontaire

Le MVP propose désormais un accès réseau réel mais strictement allowlisté (`fetch_url`) et une exécution de code réelle mais sans sandbox OS (`execute_python`), tous deux R2, profil `AGENTIC_EXECUTION` uniquement — voir ci-dessus et `docs/threat-model.md`. Il **ne** propose toujours pas de web scraping actif (crawl multi-pages), d’API MCP, d’authentification multi-utilisateur réelle, de coffre de secrets, de sandbox OS matérielle (conteneur/VM, cgroups, egress filtré au niveau réseau), d’intégration Open WebUI/AnythingLLM, ni de déploiement. L’absence de ces fonctions reste un choix de sécurité ; leur ajout doit suivre les étapes 2 à 5 du blueprint et avoir un contrat, une analyse de menace, un adaptateur isolé, des tests de contrat et une approbation adaptée.

Consulter aussi : [modèle de menace](docs/threat-model.md), [runbook d’approbation](docs/runbooks/approval.md), [runbook de rollback](docs/runbooks/rollback.md) et [runbook d’arrêt](docs/runbooks/incident-stop.md).

## Licence

MIT. Les sources méthodologiques tierces conservent leurs licences et conditions respectives ; le dossier `research/` indique les sources utilisées et ne les redistribue pas.

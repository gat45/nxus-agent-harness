# Claude Deep Research Skill — évaluation pour un harness agentique

## Conclusion opérationnelle

Le **Claude Deep Research Skill** n’est pas un moteur de recherche autonome complet ni une preuve de fiabilité de Claude. C’est surtout un **contrat de travail méthodologique et un substrat local d’évidence** pour Claude Code : il décrit un pipeline de recherche, propose des structures JSON/JSONL, fournit des scripts Python de persistance et de validation, et laisse l’orchestration réelle au modèle hôte. Le point le plus important pour un harness est explicitement documenté dans `research_engine.py` : le fichier est un « STATE SCAFFOLD (not a runtime orchestrator) » et « does NOT drive Claude Code — Claude is the orchestrator » ([script public](https://raw.githubusercontent.com/199-biotechnologies/claude-deep-research-skill/main/scripts/research_engine.py)).

Il faut donc **adopter les contrats de provenance, d’évidence, de claims atomiques, les boucles de vérification et l’idée de séparation recherche/synthèse**. Il faut **isoler ou réécrire** l’orchestration, les appels aux fournisseurs, les permissions fichiers/réseau, le contrôle des coûts et la sécurité des contenus web. Il ne faut pas présenter les seuils « 10+ sources » ou « 3+ sources par affirmation » comme une garantie statistique : ils sont des règles de workflow, tandis que la qualité du score de source, la diversité réelle et la solidité sémantique restent imparfaites.

## Ce qui est attesté publiquement

La fiche Nxus décrit un pipeline en huit phases, avec 5 à 10 recherches parallèles et 2 à 3 sous-agents produisant des objets d’évidence structurés. Elle annonce aussi un minimum de 10 sources, au moins 3 sources par affirmation majeure, des validations automatiques, et des sorties Markdown, HTML et PDF ([fiche Nxus](https://nxus.fr/skills/claude-deep-research-skill)). Le dépôt amont est public, sous licence MIT selon son README, et s’installe par clonage dans `~/.claude/skills/deep-research` ([README](https://raw.githubusercontent.com/199-biotechnologies/claude-deep-research-skill/main/README.md)).

Le dépôt contient `SKILL.md`, des références méthodologiques, des schémas, des scripts, des templates et des tests ([arborescence GitHub](https://github.com/199-biotechnologies/claude-deep-research-skill)). Les schémas publics incluent `source.schema.json`, `evidence.schema.json`, `claim.schema.json` et `run_manifest.schema.json` ([répertoire schemas](https://api.github.com/repos/199-biotechnologies/claude-deep-research-skill/contents/schemas?ref=main)). Les scripts publics comprennent notamment `citation_manager.py`, `evidence_store.py`, `extract_claims.py`, `research_engine.py`, `source_evaluator.py`, `validate_report.py`, `verify_citations.py`, `verify_claim_support.py` et `verify_html.py` ([répertoire scripts](https://api.github.com/repos/199-biotechnologies/claude-deep-research-skill/contents/scripts?ref=main)).

La dernière série de commits visible publiquement montre une évolution vers un registre de sources stable, un magasin d’évidence append-only, des claims typés et une vérification déterministe du support des claims. Le commit public du 11 avril 2026 décrit notamment un score de support combinant recouvrement lexical, nombres, années et entités, avec les statuts `supported`, `partial`, `needs_review` et `unsupported` ([historique public des commits](https://api.github.com/repos/199-biotechnologies/claude-deep-research-skill/commits?per_page=10)). Ce sont des indications de maturité du dépôt, pas une validation indépendante de ses performances.

## Rôle réel et mécanismes utiles

### 1. Pipeline de recherche

`SKILL.md` définit les modes `quick`, `standard`, `deep` et `ultradeep`, avec un nombre de phases croissant. Le pipeline conceptuel est : cadrage, planification, récupération, triangulation, affinement du plan, synthèse, critique, raffinement et packaging ([contrat SKILL](https://raw.githubusercontent.com/199-biotechnologies/claude-deep-research-skill/main/SKILL.md)). La méthodologie détaille les phases SCOPE, PLAN, RETRIEVE, TRIANGULATE, OUTLINE REFINEMENT, SYNTHESIZE, CRITIQUE, REFINE et PACKAGE ([méthodologie](https://raw.githubusercontent.com/199-biotechnologies/claude-deep-research-skill/main/reference/methodology.md)).

Le mécanisme le plus utile est la **boucle d’évidence** : récupérer, enregistrer l’évidence, vérifier les claims, puis relancer des recherches ciblées si une lacune critique apparaît. La critique peut revenir à la récupération par des « delta-queries ». Pour un harness, cette boucle est préférable à un simple appel « cherche puis rédige » : elle rend les arrêts, les reprises et les lacunes explicites.

### 2. Persistance et identité des sources

`citation_manager.py` crée un `run_manifest.json` et des fichiers JSONL pour les sources, l’évidence et les claims. L’identité d’une source est dérivée d’un identifiant stable : DOI, arXiv ou URL normalisée, puis un préfixe de SHA-256 de 16 caractères ([gestionnaire de citations](https://raw.githubusercontent.com/199-biotechnologies/claude-deep-research-skill/main/scripts/citation_manager.py)). Les numéros d’affichage sont attribués seulement au moment de l’export, ce qui évite de casser les références quand de nouvelles sources sont ajoutées.

C’est un bon contrat d’artefact pour un harness : chaque exécution doit avoir un identifiant, une question, un mode, une configuration de fournisseurs, des hypothèses, des horodatages et des chemins d’artefacts. Le registre doit conserver l’URL brute, le locator canonique, le titre, l’année, le type et le statut des métadonnées. Les JSONL append-only facilitent la reprise et l’audit, mais ne suffisent pas seuls pour l’immutabilité : le harness doit ajouter permissions, hachage des fichiers, verrouillage concurrent et journal d’événements.

### 3. Évidence et claims atomiques

Le dépôt sépare la source bibliographique de l’extrait d’évidence et du claim. Cette séparation permet de répondre à trois questions différentes : **quelle source**, **quel passage**, **quelle affirmation**. Le commit public d’avril 2026 indique que la vérification des claims classe les claims factuels, de synthèse, de recommandation et de spéculation, et fait échouer en mode strict les claims factuels non supportés ([commit public](https://github.com/199-biotechnologies/claude-deep-research-skill/commit/4662194319dd167749857c82fb669a3b3973201d)).

Pour le harness, il faut reprendre ce modèle avec un lien explicite `claim_id -> evidence_id -> source_id`, un locator précis, un extrait conservé et un statut de vérification. Une citation présente dans le texte ne doit jamais être considérée comme preuve suffisante par elle-même.

### 4. Scoring et validation

Le script `source_evaluator.py` calcule un score pondéré à partir de l’autorité du domaine, de la récence, de l’expertise et d’un indicateur de biais ([évaluateur](https://raw.githubusercontent.com/199-biotechnologies/claude-deep-research-skill/main/scripts/source_evaluator.py)). Il applique des listes codées en dur de domaines réputés, modérés ou faibles. Cette heuristique est utile comme **signal de tri**, mais pas comme jugement de vérité : elle favorise certains domaines, traite les domaines inconnus par défaut comme moyennement suspects, et sa détection du biais repose en partie sur des mots-clés.

`validate_report.py` vérifie la présence de sections, le format des citations, la correspondance bibliographie/citations, les placeholders, la longueur, un nombre minimal recommandé de sources et les liens internes ([validateur](https://raw.githubusercontent.com/199-biotechnologies/claude-deep-research-skill/main/scripts/validate_report.py)). La documentation de qualité annonce aussi une vérification DOI/URL et une boucle de correction jusqu’à trois cycles ([quality gates](https://raw.githubusercontent.com/199-biotechnologies/claude-deep-research-skill/main/reference/quality-gates.md)). Dans le harness, ces contrôles doivent être des **gates bloquants** pour les claims factuels critiques, avec un état explicite `blocked` lorsque le contrôle ne peut pas être exécuté.

## Interfaces et artefacts à reprendre

Le minimum recommandé pour une exécution est :

- `run_manifest.json` : requête, mode, version du harness, hypothèses, limites, fournisseurs, budget, horodatages, politique de sécurité et hachés des artefacts ;
- `sources.jsonl` : une entrée par source canonique, avec URL brute, titre, type, auteur/éditeur, date, statut de récupération et hash de contenu ;
- `evidence.jsonl` : extrait exact, locator, type d’évidence, langue, timestamp, `source_id` et hash ;
- `claims.jsonl` : claim atomique, type, criticité, `evidence_ids`, statut, score, décision et justification ;
- `report.md` : source de vérité lisible, avec liens URL exacts proches des affirmations ;
- un journal d’événements séparé : appels d’outils, domaines consultés, erreurs, retraits de contenu et décisions humaines.

Le script d’état public expose aussi une structure `ResearchState` contenant requête, mode, phase, scope, plan, sources, findings, synthèse, critique, rapport et métadonnées ([research_engine.py](https://raw.githubusercontent.com/199-biotechnologies/claude-deep-research-skill/main/scripts/research_engine.py)). Il faut la considérer comme une inspiration de contrat, non comme une implémentation prête à produire : sa fonction `execute_phase` affiche essentiellement les instructions et retourne un statut `instructions_displayed`; elle ne lance pas la recherche elle-même.

## Limites et risques

**Orchestration non autonome.** Le dépôt ne prouve pas que Claude Code dispose effectivement, dans n’importe quel environnement, de WebSearch, WebFetch, Task, search-cli ou d’agents parallèles. Le `research_engine.py` le dit explicitement : Claude reste l’orchestrateur ([source](https://raw.githubusercontent.com/199-biotechnologies/claude-deep-research-skill/main/scripts/research_engine.py)). Le harness doit donc fournir ses propres adaptateurs, timeouts, retries, quotas, annulation et reprise.

**Dépendances et secrets.** Le cœur revendique Python 3.9+ et la bibliothèque standard, mais `search-cli` est optionnel et nécessite au moins une clé fournisseur ; WeasyPrint est requis pour le PDF ([requirements.txt](https://raw.githubusercontent.com/199-biotechnologies/claude-deep-research-skill/main/requirements.txt)). La configuration des clés ne doit jamais entrer dans le prompt, les artefacts d’évidence ou les rapports. Elle doit passer par un coffre de secrets, avec allowlist de fournisseurs et limites de dépenses.

**Qualité de source incomplète.** Un domaine prestigieux peut publier une erreur, un blog peut contenir une information exacte, et trois pages peuvent se recopier. Le seuil de trois sources ne mesure donc pas l’indépendance. Le harness doit détecter les doublons, les citations secondaires, la dépendance à un même communiqué, les conflits temporels et les contenus non consultables.

**Vérification sémantique fragile.** Le score public de support fondé sur tokens, nombres, années et entités est déterministe et auditable, mais il ne démontre pas la relation logique entre une phrase et sa preuve. Il faut le traiter comme filtre de tri, puis exiger une revue renforcée pour les nombres, causalités, comparaisons, citations réglementaires et décisions à fort impact.

**Contenu web non fiable.** Les pages récupérées peuvent contenir des instructions adversariales, du prompt injection, du code ou des données personnelles. Le contenu doit être traité comme **donnée non fiable**, jamais comme instruction de contrôle. Le fetcher doit isoler HTML, scripts, pièces jointes et redirections, limiter les domaines et conserver une trace de ce qui a été réellement lu.

**Packaging et auto-continuation.** HTML/PDF et continuation de rapports sont des commodités, non des garanties. Le PDF ajoute une dépendance système et peut exécuter des chemins de conversion non maîtrisés. La continuation recursive peut multiplier coûts et appels. Elle doit être plafonnée par profondeur, budget, taille et durée, avec approbation avant publication.

**Maturité.** Le dépôt est structuré et évolue rapidement : le README public annonce 29 commits et une version 2.3.1, tandis que l’historique visible montre des travaux v3.0 sur les contrats d’évidence et le support des claims ([README](https://github.com/199-biotechnologies/claude-deep-research-skill) ; [commits](https://api.github.com/repos/199-biotechnologies/claude-deep-research-skill/commits?per_page=10)). Cela indique une maturité de prototype avancé / outil en consolidation, pas une certification enterprise. Les versions et comportements doivent être épinglés par commit et testés localement avant adoption.

## Ce qu’il faut adopter, rendre optionnel ou isoler

### À adopter

1. **Le modèle claim–evidence–source**, avec identifiants stables, locators, extraits exacts, hachage et provenance.
2. **Le manifest par run** et les artefacts append-only, plus un journal d’événements immuable.
3. **La séparation des phases** : cadrer avant de chercher, trianguler avant de synthétiser, critiquer avant de publier.
4. **Les statuts explicites** `supported`, `partial`, `needs_review`, `unsupported`, `conflicted` et `blocked`.
5. **Les gates bloquants** pour les claims factuels critiques et une politique de publication qui refuse les placeholders ou citations non résolues.
6. **Les modes de profondeur**, avec limites de temps, nombre d’appels, budget et nombre maximal d’agents.

### Optionnel

- recherche multi-fournisseurs via `search-cli` ; utile si les clés et la gouvernance sont disponibles, mais le harness doit avoir un adaptateur de secours ;
- sous-agents parallèles et persona de red team ; à activer seulement avec isolation, budget et fusion déterministe ;
- HTML/PDF, templates visuels et auto-continuation ; à faire après la validité du Markdown et des artefacts ;
- score heuristique de crédibilité ; utile pour prioriser, jamais pour autoriser seul une affirmation.

### À éviter ou isoler

- installer aveuglément le dépôt dans un environnement de production sans pin de commit, revue de code et sandbox ;
- laisser le modèle décider seul qu’une recherche est terminée ;
- compter les sources au lieu de vérifier leur indépendance et leur contenu ;
- confondre la présence d’une URL avec le support d’un claim ;
- exposer des clés API, des données privées ou des prompts système dans les fichiers d’exécution ;
- exécuter code, HTML, PDF ou scripts provenant des sources consultées dans le même périmètre de confiance ;
- annoncer des capacités privées, des benchmarks comparatifs ou une « chasse aux hallucinations » garantie sans preuve expérimentale reproductible.

## Architecture cible du harness

Le harness devrait placer un **contrôleur déterministe** autour du modèle. Le contrôleur reçoit une requête et un budget, crée le manifest, impose un graphe de phases et donne au modèle uniquement les outils nécessaires à la phase courante. Le collecteur réseau fonctionne dans un sandbox sans accès aux secrets bruts et renvoie des documents normalisés, des métadonnées, des hashes et des erreurs.

Après chaque récupération, un writer append-only persiste source et evidence avant toute synthèse. Un extracteur transforme le brouillon en claims atomiques. Un vérificateur calcule le support lexical et les correspondances, mais les claims critiques passent par une seconde vérification indépendante ou humaine. Un policy engine décide si la phase suivante est autorisée. Le rédacteur ne peut citer que des `evidence_id` présents dans le store.

Le contrôleur doit imposer : allowlist de domaines pour les sources sensibles, blocage SSRF et réseaux internes, taille et type de fichier maximum, timeouts, limites de concurrence, détection de boucles et de redirections, redaction de secrets, isolation des pièces jointes, journalisation et reprise idempotente. Les sorties HTML/PDF sont produites dans un job séparé et non privilégié. La publication exige un rapport de validation sans erreur, un registre de claims sans fait critique non supporté et, pour les sujets à risque, une approbation humaine.

## Verdict

Le skill est une **bonne base de méthode et de contrats d’audit**, particulièrement pour la persistance des preuves et la traçabilité. Il ne doit pas être importé comme un agent autonome ni comme un système de sécurité complet. La recommandation est de **réutiliser ses schémas et conventions après revue**, d’implémenter l’orchestration et les contrôles de sécurité dans le harness, puis de tester sur des jeux de requêtes connus : citations contradictoires, pages injectées, sources dupliquées, dates incohérentes, nombres modifiés et absence de fournisseur. L’adoption doit être épinglée sur un commit public vérifié, avec licence MIT respectée et un dossier de dérogations documentant toute divergence.

## Références

- https://nxus.fr/skills/claude-deep-research-skill — fiche Nxus.
- https://github.com/199-biotechnologies/claude-deep-research-skill — dépôt amont public.
- https://raw.githubusercontent.com/199-biotechnologies/claude-deep-research-skill/main/README.md — README public.
- https://raw.githubusercontent.com/199-biotechnologies/claude-deep-research-skill/main/SKILL.md — contrat du skill.
- https://raw.githubusercontent.com/199-biotechnologies/claude-deep-research-skill/main/reference/methodology.md — méthodologie du pipeline.
- https://raw.githubusercontent.com/199-biotechnologies/claude-deep-research-skill/main/reference/quality-gates.md — quality gates.
- https://raw.githubusercontent.com/199-biotechnologies/claude-deep-research-skill/main/requirements.txt — dépendances.
- https://raw.githubusercontent.com/199-biotechnologies/claude-deep-research-skill/main/scripts/research_engine.py — état et pseudo-orchestration.
- https://raw.githubusercontent.com/199-biotechnologies/claude-deep-research-skill/main/scripts/citation_manager.py — identité des sources et manifest.
- https://raw.githubusercontent.com/199-biotechnologies/claude-deep-research-skill/main/scripts/source_evaluator.py — score de crédibilité.
- https://raw.githubusercontent.com/199-biotechnologies/claude-deep-research-skill/main/scripts/validate_report.py — validation structurelle.
- https://api.github.com/repos/199-biotechnologies/claude-deep-research-skill/contents/scripts?ref=main — inventaire des scripts publics.
- https://api.github.com/repos/199-biotechnologies/claude-deep-research-skill/contents/schemas?ref=main — inventaire des schémas publics.
- https://api.github.com/repos/199-biotechnologies/claude-deep-research-skill/commits?per_page=10 — historique public récent.
- https://github.com/199-biotechnologies/claude-deep-research-skill/commit/4662194319dd167749857c82fb669a3b3973201d — commit public sur la vérification du support des claims.

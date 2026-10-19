# Catalogue public des compétences Nxus : évaluation pour un harness agentique

## Conclusion opérationnelle

Le catalogue public [Nxus Skills](https://nxus.fr/skills) est un **annuaire éditorial de compétences agentiques**, pas un runtime, une API, ni une garantie de sécurité. Il référence 28 skills actives, avec un nom lisible, un identifiant de projet, une catégorie, des clients annoncés, une source et une procédure d’installation. Nxus décrit une skill comme un module d’instructions, de workflow et parfois de scripts ou de ressources, chargé dans un agent pour une tâche spécialisée. Cette définition est cohérente avec le standard public Agent Skills : un dossier contient au minimum `SKILL.md` et peut contenir `scripts/`, `references/` et `assets/`, avec chargement progressif (découverte, activation, exécution) ([Nxus, catalogue](https://nxus.fr/skills), [Agent Skills, spécification publique](https://github.com/agentskills/agentskills)).

Pour un harness complet, la valeur principale est méthodologique : **progressive disclosure**, skills versionnées et inspectables, workflows explicites, artefacts vérifiables, tests et revue avant livraison. Il faut adopter ces motifs comme conventions du harness, mais ne pas installer aveuglément les skills. Les skills qui exécutent du code, lancent un navigateur, créent un serveur MCP, manipulent des documents ou analysent tout un dépôt doivent être isolées dans des sandboxes à permissions minimales. Une fiche Nxus est une porte d’entrée et une recommandation éditoriale ; elle n’est pas une preuve d’audit, de compatibilité durable, de licence homogène ou d’absence d’exfiltration.

## Ce que le catalogue atteste réellement

Nxus présente les fiches comme des compétences prêtes à ajouter à Claude, Codex et à d’autres agents. La page de catalogue expose notamment les catégories Dev & Code, Recherche & Analyse, Documents, Data, Design, Marketing et DevOps. Elle explique que chaque fiche indique la source, la compatibilité et, lorsque connue, l’installation ([https://nxus.fr/skills](https://nxus.fr/skills)). Le nombre « 28 skills actives référencées » est une déclaration de la page Nxus, à traiter comme un état éditorial susceptible d’évoluer, non comme une version d’API.

La page ne publie pas de code privé, de prompt système privé ni de fonctionnalité Nxus cachée. Les capacités évaluées ci-dessous viennent des fiches publiques Nxus et des dépôts publics liés. Les labels « Top Pick », les verdicts (« à garder », « point de départ obligé ») sont des avis éditoriaux, non des résultats de benchmark indépendant.

Le standard public décrit une skill comme un paquet portable d’instructions. Le mécanisme de progressive disclosure limite le contexte initial : le harness découvre les noms/descriptions, charge ensuite le `SKILL.md` pertinent, puis les scripts ou références nécessaires ([https://github.com/agentskills/agentskills](https://github.com/agentskills/agentskills)). Le dépôt public Anthropic confirme que les skills sont des dossiers autonomes avec `SKILL.md`, instructions, scripts et ressources, et précise que ses skills sont fournies à des fins de démonstration/éducation, que les comportements peuvent différer selon le produit et qu’il faut les tester avant un usage critique ([https://github.com/anthropics/skills](https://github.com/anthropics/skills)).

## Mécanismes et artefacts utiles

### 1. Superpowers : gouverner le cycle de développement

Nxus décrit [Superpowers](https://nxus.fr/skills/superpowers) comme une méthodologie de développement par skills composables : clarification du besoin, conception, plan, branches isolées, TDD, revue et vérification. Le dépôt public [obra/superpowers](https://github.com/obra/superpowers) détaille une chaîne concrète : brainstorming, worktree, plan d’implémentation, exécution avec sous-agent ou en ligne, RED-GREEN-REFACTOR, revue, puis finalisation de branche. Les artefacts utiles sont un design accepté, un plan avec chemins de fichiers et étapes de vérification, une branche/worktree, les tests, les rapports de revue et la décision de merge/PR/conservation/suppression.

**À adopter :** portes d’approbation explicites avant conception puis implémentation ; plan exécutable ; test avant code ; revue séparée de l’implémentation ; preuve de vérification avant déclaration de succès ; isolation par worktree. **À isoler :** dispatch de sous-agents et actions Git qui écrivent ou fusionnent. Une méthodologie prescriptive n’est pas un contrôle de sécurité : elle dépend de l’obéissance du modèle et doit être doublée de permissions et de contrôles déterministes.

### 2. mcp-builder : concevoir des interfaces d’outils

La fiche [mcp-builder](https://nxus.fr/skills/mcp-builder) référence le dépôt public Anthropic et décrit quatre phases : recherche/planification, implémentation, revue/test avec MCP Inspector, puis évaluations. Elle couvre FastMCP en Python et le SDK MCP Node/TypeScript, avec préférence annoncée pour TypeScript. Le dépôt source et sa fiche Nxus insistent sur la qualité d’un serveur MCP mesurée par les tâches réellement accomplies par le LLM, pas par le simple nombre d’endpoints ([https://github.com/anthropics/skills/tree/main/skills/mcp-builder](https://github.com/anthropics/skills/tree/main/skills/mcp-builder)).

**À adopter :** contrats d’outils typés, descriptions orientées tâche, validation des entrées/sorties, tests via Inspector, évaluations de tâches réelles, timeouts, idempotence quand possible et journaux d’audit. **À isoler :** chaque serveur MCP dans un processus/conteneur avec allowlist de réseau, secrets injectés au besoin, quotas et séparation lecture/écriture. La skill aide à construire l’interface ; elle ne fournit pas par elle-même l’autorisation métier, la gestion des secrets, la sandbox d’exécution ni une preuve de sûreté de l’API exposée.

### 3. Deep Research : pipeline de preuve et de citations

La fiche [claude-deep-research-skill](https://nxus.fr/skills/claude-deep-research-skill) annonce un pipeline en huit phases, recherches parallèles, sous-agents renvoyant des objets de preuve structurés, triangulation, validation de structure/citations/hallucinations, puis sorties Markdown, HTML et PDF. Le dépôt public [199-biotechnologies/claude-deep-research-skill](https://github.com/199-biotechnologies/claude-deep-research-skill) documente les modes Quick/Standard/Deep/UltraDeep, la persistance de `sources.json`, les seuils annoncés de 10+ sources et 3+ sources par affirmation majeure, ainsi que des scripts de validation et de vérification des citations.

**À adopter :** schéma de preuve claim/source, URL exacte, date d’accès, qualité et rôle de la source, séparation recherche/synthèse/critique, validation automatique et sauvegarde progressive. **Optionnel :** HTML/PDF, multi-provider search, sous-agents red-team et continuation pour les sujets longs. **À éviter :** considérer « 10 sources » comme une garantie ; des sources copiées, secondaires ou dépendantes peuvent donner une fausse triangulation. Les clés de recherche et les contenus confidentiels doivent rester dans un périmètre de données contrôlé.

### 4. webapp-testing : observation réelle du navigateur

La fiche [webapp-testing](https://nxus.fr/skills/webapp-testing) décrit des scripts Playwright en Python, un utilitaire `with_server.py`, des clics/attentes/DOM, screenshots et logs de console. Elle préconise « reconnaissance puis action » : inspecter le DOM rendu avant d’utiliser les sélecteurs. Le dépôt lié est le répertoire public Anthropic [webapp-testing](https://github.com/anthropics/skills/tree/main/skills/webapp-testing).

**À adopter :** tests de parcours reproductibles, artefacts screenshot/trace/log, attente explicite, validation du DOM et arrêt sur erreur. **À isoler fortement :** serveur local, navigateur, accès réseau, cookies, téléchargements et toute authentification. Le navigateur est une surface d’exfiltration et d’action externe ; le harness doit utiliser des profils éphémères, domaines allowlistés, comptes de test, secrets absents des prompts/logs et approbation humaine pour les actions irréversibles. Un screenshot ou un test vert n’est pas une preuve de sécurité.

### 5. Skills documentaires et tableurs : artefacts structurés

La fiche [xlsx](https://nxus.fr/skills/xlsx) indique pandas pour l’analyse, openpyxl pour le formatage et les formules, et un recalcul via LibreOffice (`recalc.py`) après création/modification. Elle annonce des contrôles d’erreurs (`#REF!`, `#DIV/0!`, `#VALUE!`, `#N/A`, `#NAME?`) et un code couleur distinguant saisies et formules. Les fiches [pdf](https://nxus.fr/skills/pdf), [docx](https://nxus.fr/skills/docx) et [pptx](https://nxus.fr/skills/pptx) couvrent respectivement extraction/OCR/assemblage, documents Word et présentations.

**À adopter :** fichiers de sortie comme artefacts immuables versionnés, validation de schéma et de rendu, recalcul indépendant, détection d’erreurs, contrôle des macros/liens externes et conservation des journaux de transformation. **À isoler :** LibreOffice et parseurs/OCR dans des conteneurs sans réseau ; les documents non fiables doivent être traités comme entrées adversariales. La présence d’une formule correcte syntaxiquement ne prouve ni sa justesse métier ni l’absence de données sensibles dans le fichier final.

### 6. Understand-Anything : cartographie et contexte de code

Nxus référence [Understand-Anything](https://nxus.fr/skills/understand-anything), mais la fiche pointe désormais vers [Egonex-AI/Understand-Anything](https://github.com/Lum1104/Understand-Anything) alors que GitHub affiche le dépôt sous `Egonex-AI/Understand-Anything`. Cette différence de propriétaire/URL est un signal de maintenance à vérifier avant automatisation.

Le README public décrit un pipeline hybride Tree-sitter + LLM, un graphe dans `.ua/knowledge-graph.json`, des commandes d’analyse, dashboard, chat, diff et onboarding, ainsi qu’une analyse incrémentale et cinq à sept rôles d’agents selon la commande ([https://github.com/Egonex-AI/Understand-Anything](https://github.com/Egonex-AI/Understand-Anything)). Le même README précise que le graphe peut être partagé comme JSON, que `intermediate/` et `diff-overlay.json` sont des données locales à exclure, et qu’un viewer local peut servir le graphe en lecture seule sans LLM ni sortie de données.

**À adopter :** index structurel déterministe, graphe versionné, analyse incrémentale, impact de diff et visualisation read-only. **À isoler :** les analyseurs LLM et les hooks post-commit ; ne jamais exécuter des commandes dérivées de chemins ou contenus non fiables sans validation. La politique de sécurité publique du projet qualifie l’outil de local-only, indique qu’il ne « phone home » pas, et mentionne comme menaces les chemins hostiles, JSON non fiable et endpoint de contenu du dashboard ([https://github.com/Egonex-AI/Understand-Anything/blob/main/SECURITY.md](https://github.com/Egonex-AI/Understand-Anything/blob/main/SECURITY.md)). Ce sont des garde-fous déclarés par le projet, pas une certification indépendante.

## Limites, maturité et dépendances

Le catalogue est utile mais hétérogène. Il mélange des skills Anthropic présentées comme source-available/démonstration, un framework MIT communautaire, un outil de recherche MIT, un outil de cartographie MIT et des skills marketing/design ou bureautiques dont les fiches ne donnent pas toutes le même niveau de détail. Les licences, dépendances, cadence de commits et support varient par dépôt ; ils doivent être enregistrés séparément dans un manifest signé. Le dépôt Anthropic contient notamment une spécification et un template, mais son avertissement demande de tester les implémentations avant les usages critiques ([https://github.com/anthropics/skills](https://github.com/anthropics/skills)).

La compatibilité annoncée par Nxus (« Claude », « Codex » ou les deux) décrit une cible d’installation, pas une compatibilité sémantique garantie. La spécification ouverte est adoptée par plusieurs clients ([https://github.com/agentskills/agentskills](https://github.com/agentskills/agentskills)), mais les hooks, slash commands, plugin marketplaces, chemins de skills, permissions et outils diffèrent selon le harness. Il faut donc un adaptateur par client et des tests de comportement, plutôt qu’un simple copier-coller de dossier.

Les installations `curl | bash`, `git clone` à la branche par défaut, plugins de marketplace et scripts inclus sont des chaînes d’approvisionnement. Le harness doit pinner commit/tag et hash, vérifier la licence, scanner les scripts et dépendances, produire un SBOM, exécuter en sandbox et soumettre les nouvelles versions à une évaluation de régression. Il doit aussi distinguer les instructions de skill des instructions de confiance système : une skill ne peut pas s’auto-accorder accès aux secrets, au réseau, au shell privilégié ou à une fusion Git.

## Garde-fous requis dans le harness

1. **Registre signé des skills :** identifiant, dépôt source, commit, licence, mainteneur, date de revue, compatibilité, permissions demandées, dépendances, hash et statut d’approbation.
2. **Chargement progressif contrôlé :** métadonnées d’abord ; `SKILL.md` ensuite ; scripts/références seulement lorsqu’une tâche les justifie. Les instructions sont des données non fiables jusqu’à validation.
3. **Deny-by-default :** filesystem limité au workspace, réseau par allowlist, secrets jamais injectés par défaut, exécution non root, quotas CPU/mémoire/temps et approbation pour écritures externes.
4. **Contrats d’outils :** schémas JSON, validation stricte, dry-run, idempotence, timeouts, limites de taille, journal d’audit et séparation des outils de lecture et d’écriture.
5. **Preuves et sorties :** chaque résultat doit référencer les fichiers/URLs utilisés, les commandes et les contrôles effectués ; les artefacts doivent être stockés dans un espace de travail traçable et nettoyable.
6. **Évaluation continue :** tests de déclenchement, tests adversariaux de prompt injection et d’exfiltration, golden tasks, tests de non-régression et revue humaine des actions à impact.
7. **Arrêt sûr :** interruption, rollback, expiration des credentials, suppression de worktree/conteneur et reprise depuis l’état journalisé.

## Décision d’intégration

**À adopter en priorité :** le format `SKILL.md` et la progressive disclosure ; le registre de provenance ; les gates Superpowers (spécification, plan, TDD, revue, vérification) ; le contrat MCP avec tests/évals ; le modèle de preuve/citation de Deep Research ; les artefacts de test navigateur et de documents ; l’analyse structurelle incrémentale de code.

**À rendre optionnel :** sous-agents parallèles, HTML/PDF, graphes interactifs, post-commit hooks, fournisseurs de recherche multiples, télémetrie et intégrations marketplace. Leur activation doit dépendre du risque, du coût et de l’environnement, jamais d’un déclenchement implicite.

**À éviter ou isoler :** exécution directe de scripts téléchargés, `curl | bash` non pinné, accès réseau général, navigateur avec session réelle, outils MCP d’écriture sans approbation, documents non fiables ouverts avec des applications privilégiées, hooks persistants, et fusion/production déclenchée par une simple conclusion du modèle.

Le catalogue Nxus est donc un **répertoire de patrons et de composants réutilisables**, avec une bonne couverture pratique et plusieurs dépôts publics substantiels, mais pas un socle de confiance. Le harness doit reprendre les interfaces et les contrôles observables, vérifier chaque upstream indépendamment et conserver une frontière nette entre compétence déclarative, outil effecteur et politique d’autorisation.

## Références

- [Nxus — Annuaire des Skills IA](https://nxus.fr/skills)
- [Nxus — Superpowers](https://nxus.fr/skills/superpowers)
- [Nxus — mcp-builder](https://nxus.fr/skills/mcp-builder)
- [Nxus — Deep Research](https://nxus.fr/skills/claude-deep-research-skill)
- [Nxus — webapp-testing](https://nxus.fr/skills/webapp-testing)
- [Nxus — xlsx](https://nxus.fr/skills/xlsx)
- [Nxus — Understand-Anything](https://nxus.fr/skills/understand-anything)
- [Anthropic — Agent Skills](https://github.com/anthropics/skills)
- [obra — Superpowers](https://github.com/obra/superpowers)
- [199-biotechnologies — claude-deep-research-skill](https://github.com/199-biotechnologies/claude-deep-research-skill)
- [Egonex-AI — Understand-Anything](https://github.com/Egonex-AI/Understand-Anything)
- [Understand-Anything — SECURITY.md](https://github.com/Egonex-AI/Understand-Anything/blob/main/SECURITY.md)
- [Agent Skills — spécification ouverte](https://github.com/agentskills/agentskills)
- [GitHub — About agent skills](https://docs.github.com/en/copilot/concepts/agents/about-agent-skills)

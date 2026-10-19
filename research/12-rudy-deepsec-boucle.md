# Évaluation de la Skill SaaS Factory + Boucle + DeepSec de Rudy

## Conclusion opérationnelle

La ressource étudiée est une **skill Markdown d’orchestration**, pas un scanner, un runtime d’agents ni une preuve de sécurité. Elle impose une séquence utile pour transformer une idée en MVP : cadrage vérifiable, étude de marché, spécification produit et technique, construction par tranches, gate de sécurité défensif, vérification, puis décision go/no-go. Le fichier public recommande explicitement de ne jamais commencer par coder et fixe les étapes « Cadrage → Scout marché → Spec produit → Spec technique → Build incremental → DeepSec gate → Verification → Decision go/no-go → Rapport final » ([SKILL.md](https://github.com/rudy-io/agentic-saas-factory-skills/blob/main/skills/saas-factory-boucle-deepsec/SKILL.md)).

Pour un harness agentique, il faut **adopter le protocole de boucle, les contrats d’artefacts, les contrôles de non-secret, les barrières d’actions irréversibles et la production de preuves**. Il faut traiter le marché et le score d’opportunité comme une aide à la décision, non comme une validation empirique. Le bloc nommé DeepSec doit rester un **gate défensif à compléter par des outils réellement exécutés** : la skill elle-même ne lance ni SAST, ni tests, ni audit de dépendances, ni scanner d’agent.

La source est publiquement nettoyée et générique. L’attribution précise que `boucle-autonome` et `saas-factory` sont adaptées de workflows privés, dont les chemins, secrets, détails serveur, hypothèses projet et données client ont été retirés ; elle indique aussi que le gate est seulement inspiré de l’idée publique de DeepSec, sans code, matchers, données privées ou texte propriétaire ([ATTRIBUTION.md](https://github.com/rudy-io/agentic-saas-factory-skills/blob/main/docs/ATTRIBUTION.md)). Il ne faut donc pas inférer l’existence d’un prompt privé, d’un accès à une infrastructure Rudy/NXUS ou d’une fonctionnalité non présente dans les fichiers publics.

## Rôle réel et périmètre

Le dépôt se décrit comme un ensemble de skills publiques pour une factory SaaS, une boucle autonome et une revue de sécurité défensive. Il est destiné aux outils qui supportent une convention `SKILL.md` tels que Codex ou Claude Code ; l’installation documentée consiste à copier les dossiers dans le répertoire de skills de l’agent ([README du dépôt](https://github.com/rudy-io/agentic-saas-factory-skills)). La skill ne définit pas d’API, de format JSON, d’orchestrateur multi-agent, de sandbox, de gestion de permissions ou de connecteur fournisseur. Les fichiers attendus sont des conventions documentaires : `01-analyse-marche.md`, `02-spec-produit.md`, `03-spec-technique.md`, `04-deepsec-rapport.md` et `05-rapport-final.md`.

Le dépôt est public, sous licence MIT, et son README décrit quatre skills séparées : orchestration complète, boucle autonome, factory SaaS et gate DeepSec ([README](https://github.com/rudy-io/agentic-saas-factory-skills), [LICENSE](https://github.com/rudy-io/agentic-saas-factory-skills/blob/main/LICENSE)). La métadonnée GitHub consultée indique un dépôt public créé le 2 juillet 2026, mis à jour le 13 juillet 2026, avec un seul commit, quatre stars et aucun fork au moment de la consultation ([API GitHub](https://api.github.com/repos/rudy-io/agentic-saas-factory-skills)). Ces signaux décrivent une ressource jeune et peu éprouvée publiquement ; ils ne mesurent pas sa qualité intrinsèque.

## Mécanismes et étapes utiles

### 1. Contrat de boucle et preflight

Avant toute action, l’agent doit écrire l’objectif, un critère de succès vérifiable, la cible, le problème, le livrable, le périmètre, le hors-périmètre, un budget de temps/itérations, les risques irréversibles et les commandes de vérification ([SKILL.md](https://github.com/rudy-io/agentic-saas-factory-skills/blob/main/skills/saas-factory-boucle-deepsec/SKILL.md)). La skill autonome formule le cycle `Discovery → Plan → Exec → Verify → Iterate → Report`, demande de lire les instructions et l’état du projet, puis d’identifier une cause racine et d’arrêter après trois cycles sans progrès ([boucle-autonome/SKILL.md](https://github.com/rudy-io/agentic-saas-factory-skills/blob/main/skills/boucle-autonome/SKILL.md)).

**À adopter dans le harness :** un objet de tâche immuable ou versionné contenant objectif, critères, périmètre, budget, lignes rouges et plan de rollback ; un journal append-only des décisions ; un compteur d’itérations ; une condition de sortie « succès vérifié / blocage explicite ». Le critère ne doit pas rester une phrase libre : le harness doit exiger une commande, un test, une assertion ou une preuve attendue.

### 2. Scout marché et décision économique

La factory demande un fichier d’analyse avant le build, avec cible, alternatives, concurrents, requêtes SEO, volonté de payer, acquisition, risques, wedge, MVP et verdict. Le score sur 30 additionne douleur, urgence, budget, faiblesse de la concurrence, acquisition et faisabilité ; `GO` est proposé à partir de 22, `TEST` entre 16 et 21 et `NO-GO` sous 16, sauf objectif pédagogique ([SKILL.md](https://github.com/rudy-io/agentic-saas-factory-skills/blob/main/skills/saas-factory-boucle-deepsec/SKILL.md)).

**À adopter avec réserve :** le document et le verdict comme artefacts de traçabilité. **Optionnel :** le score numérique et les champs SEO/pricing si le produit est interne ou si les données sont insuffisantes. **À ne pas traiter comme preuve :** les scores générés par le modèle, les concurrents supposés ou la volonté de payer non corroborée par entretiens, données de marché ou expérimentation.

### 3. Spécification produit et technique

La spec produit couvre promesse, persona, cas P0, fonctionnalités P0/P1/P2, écrans, données, workflow, pricing, métriques et limites du MVP. La spec technique couvre stack, schéma, routes, API, auth, rôles, fichiers, noms de variables d’environnement, jobs, tests, migration et rollback ; elle interdit explicitement d’écrire de vraies clés et prescrit seulement les noms de variables ([SKILL.md](https://github.com/rudy-io/agentic-saas-factory-skills/blob/main/skills/saas-factory-boucle-deepsec/SKILL.md)).

**À adopter :** génération séparée des specs et validation humaine ou policy-engine avant passage au build ; contrats d’interface entre les fichiers ; liste d’env vars sans valeurs ; plan de migration et rollback obligatoire pour toute modification de données. Le harness devrait convertir ces specs en tests d’acceptation et en allowlist de fichiers/commandes, plutôt que laisser l’agent interpréter chaque étape sans contrôle.

### 4. Build incrémental et vérification

L’ordre recommandé est d’auditer ou initialiser, poser le modèle de données, faire l’auth, construire le workflow, puis la landing, l’admin, le paiement, l’IA, les analytics et les logs. Chaque tranche doit rendre compte des fichiers modifiés, du risque, de la vérification, du résultat et de la prochaine tranche ([SKILL.md](https://github.com/rudy-io/agentic-saas-factory-skills/blob/main/skills/saas-factory-boucle-deepsec/SKILL.md)). La vérification minimale inclut démarrage, workflow principal, tests, build, console, routes sensibles, liens et relecture du diff.

**À adopter :** petites transactions de travail, diff contrôlé, tests après chaque tranche et arrêt sur échec non expliqué. **À isoler :** toute capacité de déploiement, de modification DNS, de paiement ou d’envoi à des tiers ; elles doivent être des outils séparés avec approbation explicite, idempotence et rollback, pas des commandes librement accessibles au même agent de build.

### 5. DeepSec gate défensif

Le gate couvre secrets, auth/rôles, données personnelles, API, paiement, uploads, IA, frontend et déploiement. Les contrôles mentionnés comprennent absence de `.env` commité et de tokens en dur, autorisation serveur, ownership checks contre l’IDOR, validation stricte, rate limiting, vérification de signature des webhooks, limites MIME/taille des uploads, sanitation HTML, quotas IA, lockfile/audit de dépendances, HTTPS, headers, backups et rollback ([deepsec-security-gate/SKILL.md](https://github.com/rudy-io/agentic-saas-factory-skills/blob/main/skills/deepsec-security-gate/SKILL.md)). Le verdict prévu est `PASS`, `PASS AVEC RESERVES` ou `FAIL`, avec surface, preuves, bloquants, risques et correctifs.

La checklist demande des tests autorisés dans un environnement contrôlé, par exemple vérifier qu’un compte A ne lit pas les données de B, qu’un non-admin ne fait pas d’action admin et que les payloads invalides sont rejetés ([deepsec-security-gate/SKILL.md](https://github.com/rudy-io/agentic-saas-factory-skills/blob/main/skills/deepsec-security-gate/SKILL.md)). Elle reste une liste de contrôle : elle ne fournit pas de scanner ni de garantie de couverture.

## Ce que « DeepSec » signifie ici, et ce qu’il ne signifie pas

L’attribution Rudy renvoie au projet public [Vercel Labs deepsec](https://github.com/vercel-labs/deepsec), à l’annonce Vercel et à `deepsec-skill.dev`. Le dépôt Rudy précise qu’il n’inclut pas le code, les matchers, les données privées ou le texte propriétaire de ces projets ([ATTRIBUTION.md](https://github.com/rudy-io/agentic-saas-factory-skills/blob/main/docs/ATTRIBUTION.md)). Le nom du gate ne doit donc pas être compris comme l’intégration du CLI Vercel.

Le DeepSec Vercel réel est un scanner agentique exécutable : il commence par un scan regex rapide, envoie les candidats à des agents IA, peut revalider les findings, enrichir avec les métadonnées Git et exporter des rapports. Son dépôt documente `scan`, `process`, `process --diff`, `triage`, `revalidate`, `enrich`, `report`, `export`, `metrics` et l’exécution optionnelle en sandbox ([README Vercel deepsec](https://github.com/vercel-labs/deepsec), [SKILL.md Vercel](https://github.com/vercel-labs/deepsec/blob/main/SKILL.md)). Il persiste son état dans `.deepsec/`, reprend une exécution interrompue et propose des limites de coût et de durée (`--max-cost-usd`, `--max-duration`) ([README Vercel deepsec](https://github.com/vercel-labs/deepsec)).

Cette comparaison fournit des interfaces utiles pour un harness, mais **ne justifie pas de prétendre que la skill Rudy les implémente**. Le DeepSec Vercel indique lui-même que ses analyses peuvent coûter des milliers ou dizaines de milliers de dollars sur de grands dépôts et que son taux de faux positifs est approximativement de 10–20 % avant la revalidation ([README Vercel deepsec](https://github.com/vercel-labs/deepsec), [annonce Vercel](https://vercel.com/blog/introducing-deepsec-find-and-fix-vulnerabilities-in-your-code-base)). Son annonce le décrit comme encore tôt dans son développement ([annonce Vercel](https://vercel.com/blog/introducing-deepsec-find-and-fix-vulnerabilities-in-your-code-base)). Ce sont des limites du scanner Vercel, pas des mesures de la skill Rudy.

Le scanner Vercel documente une couverture technique déclarative : détection par fichiers sentinelles ou dépendances, matchers et highlights par technologie ; certaines familles comme Rust, JVM et .NET ont une détection mais des matchers dédiés encore en roadmap ([supported-tech.md](https://github.com/vercel-labs/deepsec/blob/main/docs/supported-tech.md)). Pour le harness, cela implique d’enregistrer la couverture effective de chaque outil et de ne jamais convertir « technologie détectée » en « sécurité démontrée ».

## Garde-fous à intégrer

1. **Autorité et périmètre :** exiger un dépôt/environnement explicitement autorisé, une portée de fichiers et un mode read-only par défaut. La politique du dépôt interdit l’attaque de tiers, le contournement d’accès, la collecte d’identifiants et le scan sans autorisation ([SECURITY.md](https://github.com/rudy-io/agentic-saas-factory-skills/blob/main/SECURITY.md)).
2. **Secrets :** scanner le working tree et l’historique, masquer toute valeur dans les logs, utiliser un coffre ou des variables injectées, et déclencher rotation/révocation si un secret est trouvé. La politique publique prescrit rotation immédiate, retrait, inspection de l’historique et hypothèse de compromission ([SECURITY.md](https://github.com/rudy-io/agentic-saas-factory-skills/blob/main/SECURITY.md)).
3. **Actions à haut impact :** bloquer par défaut suppression sans backup, paiement, emails/SMS, exposition de données personnelles, DNS, infrastructure critique et déploiement sans rollback. Ces stops sont explicitement listés par la skill ([SKILL.md](https://github.com/rudy-io/agentic-saas-factory-skills/blob/main/skills/saas-factory-boucle-deepsec/SKILL.md)).
4. **Sécurité agentique :** isoler le code non fiable, réduire réseau et permissions shell, borner coût/durée/itérations, journaliser les appels outils, et exiger une seconde vérification indépendante pour un PASS. L’inspiration Vercel avertit qu’un scanner agentique se comporte comme un coding agent avec accès shell complet ; le sandbox réduit l’exposition mais ne supprime pas le risque de prompt injection provenant de dépendances ou de code vendored ([README Vercel deepsec](https://github.com/vercel-labs/deepsec)).
5. **Preuves :** un verdict ne peut être `PASS` que si commandes, versions, commit, périmètre, résultats et exceptions sont archivés. Une checklist cochée par le modèle sans sortie de test doit être `non vérifiée`.
6. **Séparation des rôles :** l’agent qui modifie le code ne doit pas être l’unique juge de son propre gate. Utiliser une étape d’audit distincte, et conserver un état `FAIL` tant que les bloquants ne sont pas corrigés.

## Maturité, dépendances et limites

La skill Rudy dépend d’un agent compatible avec `SKILL.md`, d’un workspace projet, de commandes locales et de la capacité de l’agent à lire/écrire les artefacts. Elle ne fixe aucun modèle, fournisseur LLM, système d’identité, sandbox, base de données, CI, outil SAST ou format machine lisible. Elle peut donc être facilement adoptée comme politique, mais sa reproductibilité et sa sécurité opérationnelle dépendent entièrement du harness qui l’exécute.

Les principales limites observables sont l’absence de preuves d’exécution dans le dépôt, l’absence de tests publiés ou de CI documentée dans le README, l’absence de schéma d’artefacts formel et l’ambiguïté du terme « DeepSec » par rapport au scanner Vercel. Les instructions sont prescriptives mais non auto-validantes : elles disent de lancer `npm audit`, `pnpm audit`, des tests et un build selon le projet, sans définir comment vérifier qu’ils ont réellement été lancés ([deepsec-security-gate/SKILL.md](https://github.com/rudy-io/agentic-saas-factory-skills/blob/main/skills/deepsec-security-gate/SKILL.md)).

Les limites métier sont tout aussi importantes. Le score marché est un cadre de priorisation, pas une étude ; un `GO` ne prouve ni demande ni rentabilité. Le gate n’est pas une pentest, ne couvre pas automatiquement la configuration cloud, la chaîne de fournisseurs, la confidentialité juridique, la résilience ou les menaces émergentes. La règle « ne jamais commencer par coder » doit aussi être adaptée aux tickets de correction ou aux tâches purement techniques où une analyse de marché serait hors sujet.

## Décision pour le harness

### À adopter

- Le contrat preflight et le cycle `Discovery → Plan → Exec → Verify → Iterate → Report`.
- Des artefacts versionnés avec schéma machine : contexte, specs, plan, journal d’outils, résultats de tests, rapport DeepSec, décision finale.
- Les contrôles secrets/auth/ownership/validation/rate-limit/webhooks/uploads/IA/dépendances/déploiement comme exigences minimales.
- Les verdicts `PASS`, `PASS AVEC RESERVES`, `FAIL`, avec règle dure : `FAIL` interdit déploiement et exposition.
- Les stops et approbations explicites pour toute action irréversible ou externe.
- Les limites de coût, durée, concurrence et itérations, inspirées des interfaces documentées par Vercel deepsec mais implémentées dans le harness lui-même.

### Optionnel

- Le scout marché, le pricing, les requêtes SEO et le score sur 30 pour les produits externes.
- Le support de paiement, d’uploads ou d’IA lorsqu’ils ne font pas partie du produit.
- L’intégration du CLI Vercel deepsec comme outil spécialisé, après revue de licence, coût, réseau, stockage `.deepsec`, modèle de menace et couverture du langage.
- Une exécution distribuée en sandbox pour les gros dépôts, avec secrets hors worker et egress strict ; ce mode est documenté par Vercel mais n’est pas fourni par Rudy ([README Vercel deepsec](https://github.com/vercel-labs/deepsec)).

### À éviter ou isoler

- Donner au même agent des permissions de build, de déploiement, de paiement, de suppression et de validation finale.
- Confondre le nom « DeepSec » de la skill Rudy avec le scanner Vercel ou une certification.
- Accepter un PASS fondé sur une checklist non accompagnée de preuves.
- Envoyer secrets, données personnelles ou code propriétaire à un fournisseur sans autorisation, minimisation et politique de rétention.
- Laisser le modèle inventer des concurrents, des résultats de tests, des scans ou des validations de marché.
- Exécuter des tests offensifs hors environnement contrôlé ou sans autorisation.

## Références principales

- [Skill complète Rudy](https://github.com/rudy-io/agentic-saas-factory-skills/blob/main/skills/saas-factory-boucle-deepsec/SKILL.md)
- [Boucle autonome Rudy](https://github.com/rudy-io/agentic-saas-factory-skills/blob/main/skills/boucle-autonome/SKILL.md)
- [Gate DeepSec Rudy](https://github.com/rudy-io/agentic-saas-factory-skills/blob/main/skills/deepsec-security-gate/SKILL.md)
- [README Rudy](https://github.com/rudy-io/agentic-saas-factory-skills)
- [Politique de sécurité Rudy](https://github.com/rudy-io/agentic-saas-factory-skills/blob/main/SECURITY.md)
- [Attribution Rudy](https://github.com/rudy-io/agentic-saas-factory-skills/blob/main/docs/ATTRIBUTION.md)
- [Vercel Labs deepsec](https://github.com/vercel-labs/deepsec)
- [Vercel deepsec SKILL.md](https://github.com/vercel-labs/deepsec/blob/main/SKILL.md)
- [Vercel supported tech](https://github.com/vercel-labs/deepsec/blob/main/docs/supported-tech.md)
- [Annonce officielle Vercel](https://vercel.com/blog/introducing-deepsec-find-and-fix-vulnerabilities-in-your-code-base)

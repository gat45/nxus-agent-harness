# Skill SaaS Factory de Rudy : évaluation pour un harness agentique

## Rôle réel et périmètre

Le sujet étudié est d’abord un **document d’instructions Markdown**, pas un framework d’exécution, un agent autonome livré avec un runtime, ni un scanner de sécurité. Le fichier demandé décrit une « factory publique » qui prend une idée de SaaS, micro-SaaS, outil métier ou MVP et la transforme en produit testable ou en décision d’abandon : analyse de marché, wedge, spécification, plan de build, acquisition, pricing et verdict. [Source primaire : `skills/saas-factory/SKILL.md`](https://github.com/rudy-io/agentic-saas-factory-skills/blob/main/skills/saas-factory/SKILL.md)

Le dépôt public se présente plus largement comme un ensemble de skills génériques pour construire de petits SaaS et outils internes : boucle autonome, factory SaaS et gate de sécurité défensif. Il indique que les documents sont destinés à des outils acceptant une convention `SKILL.md`, tels que Codex ou Claude Code, et recommande de copier les dossiers dans le répertoire de skills de l’agent. [README du dépôt](https://github.com/rudy-io/agentic-saas-factory-skills) Le dépôt est public et sous licence MIT ; l’attribution précise que `saas-factory` et `boucle-autonome` sont des versions nettoyées/adaptées de workflows privés, dont les chemins, secrets, identifiants, détails serveur et données clients ont été retirés. [Attribution](https://github.com/rudy-io/agentic-saas-factory-skills/blob/main/docs/ATTRIBUTION.md) Il ne faut donc pas inférer l’existence d’un accès au workflow privé de Rudy ni de prompts privés à partir de ce dépôt.

Le skill SaaS Factory isolé n’est pas l’orchestrateur complet. Le dépôt publie séparément `saas-factory-boucle-deepsec`, qui combine cadrage, étude, spécifications, build incrémental, gate de sécurité, vérification et décision finale. [Skill d’orchestration](https://github.com/rudy-io/agentic-saas-factory-skills/blob/main/skills/saas-factory-boucle-deepsec/SKILL.md) Pour un harness complet, cette distinction est importante : adopter le skill isolé fournit une méthode de découverte et de décision produit ; adopter l’orchestrateur ajoute un protocole opératoire, mais ne remplace toujours pas les contrôles d’exécution du harness.

## Mécanismes et étapes utiles

### 1. Cadrage avant le code

La règle centrale de l’orchestrateur est de ne pas commencer par coder. Il impose successivement cadrage, scout marché, spécification produit, spécification technique, build incrémental, gate DeepSec, vérification et décision go/no-go. Le contrat initial doit expliciter l’objectif, un critère de succès vérifiable, la cible, le problème, le livrable, le périmètre et hors périmètre, le budget temps/itérations, les risques irréversibles et les commandes de vérification. [Orchestrateur](https://github.com/rudy-io/agentic-saas-factory-skills/blob/main/skills/saas-factory-boucle-deepsec/SKILL.md)

C’est un bon contrat d’entrée pour le harness : il rend les tâches observables et empêche qu’une demande vague (« construis un SaaS ») soit traitée comme une autorisation illimitée. Le harness devrait toutefois stocker ce contrat dans un état structuré et validé, plutôt que seulement dans un prompt.

### 2. Analyse de marché et wedge

Le skill demande de répondre à la fréquence et au coût du problème, aux alternatives actuelles, aux concurrents directs et indirects, à la volonté de payer et à la crédibilité du canal d’acquisition. Il propose six scores sur 5, pour un total sur 30 : douleur métier, urgence, budget, faiblesse de la concurrence/angle distinct, acquisition plausible et faisabilité rapide du MVP. Les seuils publiés sont `GO` à 22–30, `TEST` à 16–21 et `NO-GO` sous 16, avec possibilité d’outil interne dans les cas faibles mais utiles en interne. [Skill SaaS Factory](https://github.com/rudy-io/agentic-saas-factory-skills/blob/main/skills/saas-factory/SKILL.md) L’orchestrateur reprend les mêmes seuils et ajoute les alternatives, requêtes SEO, risques, wedge et MVP recommandé. [Orchestrateur](https://github.com/rudy-io/agentic-saas-factory-skills/blob/main/skills/saas-factory-boucle-deepsec/SKILL.md)

Le concept de **wedge** est particulièrement utile : un angle d’entrée étroit, destiné à une cible précise, résolvant un problème fréquent, démontrable et vendable sans expliquer quinze modules. Le skill écarte les dashboards « tout-en-un », le « CRM avec IA » sans douleur précise, les marketplaces sans offre/demande et le simple « comme X mais moins cher ». [Skill SaaS Factory](https://github.com/rudy-io/agentic-saas-factory-skills/blob/main/skills/saas-factory/SKILL.md) Le harness devrait conserver ces critères comme heuristiques de qualité, mais jamais transformer le score en preuve de demande : les scores sont des jugements de l’agent, à compléter par des observations, entretiens, pages concurrentes et expériences réelles autorisées.

### 3. Artefacts produit et technique

Les sorties attendues minimales du skill isolé sont `01-analyse-marche.md`, `02-spec-produit.md`, `03-spec-technique.md`, `04-plan-build.md` et `05-rapport-final.md`. [Skill SaaS Factory](https://github.com/rudy-io/agentic-saas-factory-skills/blob/main/skills/saas-factory/SKILL.md) L’orchestrateur ajoute explicitement `04-deepsec-rapport.md` au cours du gate. [Orchestrateur](https://github.com/rudy-io/agentic-saas-factory-skills/blob/main/skills/saas-factory-boucle-deepsec/SKILL.md)

La spécification produit doit contenir promesse, persona, problème principal, workflow P0, fonctionnalités P0/P1, exclusions MVP, écrans, données, pricing, acquisition et script de démonstration ; la version orchestrée complète avec métriques et limites MVP. La spécification technique couvre stack, modèle de données, routes/pages, API, authentification, rôles, paiement, emails/notifications, IA, analytics, tests et variables d’environnement. Les secrets ne doivent jamais être écrits ; seules les **noms** de variables sont listés, par exemple `DATABASE_URL` ou `AUTH_SECRET`. [Skill SaaS Factory](https://github.com/rudy-io/agentic-saas-factory-skills/blob/main/skills/saas-factory/SKILL.md) [Orchestrateur](https://github.com/rudy-io/agentic-saas-factory-skills/blob/main/skills/saas-factory-boucle-deepsec/SKILL.md)

### 4. Construction incrémentale

L’ordre recommandé commence par une landing claire et le workflow principal, puis la persistance, l’authentification si nécessaire, l’administration minimale, le paiement si le produit est vendable, l’IA seulement si elle accroît réellement la valeur, puis SEO/acquisition, logs/analytics/monitoring et enfin le polish. L’orchestrateur recommande aussi de construire en tranches et, pour chaque tranche, de conserver fichiers modifiés, risque, vérification, résultat et prochaine tranche. [Orchestrateur](https://github.com/rudy-io/agentic-saas-factory-skills/blob/main/skills/saas-factory-boucle-deepsec/SKILL.md)

Cette séquence est directement réutilisable comme machine à états du harness. Elle doit être reliée à une politique de permissions : une étape « paiement », « publication » ou « déploiement » ne doit pas devenir exécutable simplement parce qu’elle apparaît dans le plan.

### 5. Boucle et preuve

Le skill `boucle-autonome` formalise `Discovery -> Plan -> Exec -> Verify -> Iterate -> Report`. Il impose de lire les instructions et l’architecture existantes, de faire un plan court, de modifier le minimum nécessaire, puis de vérifier par tests, build, lint, smoke test, requête HTTP, lecture du diff ou recherche de secrets. Après un échec, il demande d’identifier la cause racine, de corriger une chose à la fois et d’arrêter après trois cycles sans progrès net. [Boucle autonome](https://github.com/rudy-io/agentic-saas-factory-skills/blob/main/skills/boucle-autonome/SKILL.md)

Pour le harness, c’est un modèle de contrôle utile : chaque transition doit produire des preuves adressables (commande, sortie, fichier, URL ou journal), et le rapport final doit distinguer fait, vérification, résultat et risques restants. Une boucle de prompt seule n’est toutefois pas une garantie d’arrêt ; le runtime doit imposer timeout, budget, nombre d’itérations et permissions.

## Garde-fous et sécurité

Le gate `deepsec-security-gate` est explicitement défensif et limité aux propres applications, dépôts ou environnements de test autorisés ; il exclut l’attaque de tiers, le contournement d’accès, la collecte de credentials et le scan sans autorisation. [Gate DeepSec](https://github.com/rudy-io/agentic-saas-factory-skills/blob/main/skills/deepsec-security-gate/SKILL.md) La politique du dépôt répète cette limite et prescrit rotation/révocation immédiate, nettoyage du dépôt et inspection de l’historique si un secret a été commité. [SECURITY.md](https://github.com/rudy-io/agentic-saas-factory-skills/blob/main/SECURITY.md)

Le checklist couvre les secrets et logs, l’authentification et les rôles côté serveur, cookies et sessions, données personnelles, validation et ownership des ressources, IDOR, rate limiting, CORS/CSRF, paiements et webhooks signés, uploads, dépendances, rendu HTML, accessibilité, HTTPS, headers, migrations, backups, rollback, IA et quotas. Pour l’IA, il demande de ne pas envoyer de données sensibles sans raison/consentement ou base légale, de confirmer les actions irréversibles, de limiter coûts et quotas, de prévoir un fallback et de valider les sorties avant insertion critique. [Gate DeepSec](https://github.com/rudy-io/agentic-saas-factory-skills/blob/main/skills/deepsec-security-gate/SKILL.md)

Les arrêts obligatoires de l’orchestrateur et de la boucle sont une base de politique d’approbation humaine : confirmation avant emails/SMS à de vraies personnes, paiement, suppression sans backup, exposition de données personnelles, modification DNS/infrastructure critique, déploiement sans rollback, usage d’un secret introuvable et décision produit majeure ambiguë. [Orchestrateur](https://github.com/rudy-io/agentic-saas-factory-skills/blob/main/skills/saas-factory-boucle-deepsec/SKILL.md) [Boucle autonome](https://github.com/rudy-io/agentic-saas-factory-skills/blob/main/skills/boucle-autonome/SKILL.md) Dans le harness, ces lignes rouges doivent être des contrôles techniques non contournables : approbation externe, dry-run, allowlist d’outils, séparation des identités et journal d’audit.

## Dépendances et maturité

La dépendance directe est un agent capable de charger des fichiers `SKILL.md` et d’exécuter les actions qu’il autorise ; le dépôt ne fournit ni serveur, ni base, ni modèle, ni gestionnaire de secrets, ni pipeline CI/CD. Le README décrit l’installation comme une copie de répertoires dans les dossiers de skills, puis un redémarrage de l’agent. [README](https://github.com/rudy-io/agentic-saas-factory-skills) Le contenu est donc portable, mais la reproductibilité dépend entièrement du runtime, de ses outils et de ses permissions.

Le dépôt est présenté par l’API GitHub comme public, non fork, non archivé, sur `main`, sous MIT, avec 1 commit, 4 étoiles, 0 fork et 0 issue ouverte au moment de la consultation. [Métadonnées publiques du dépôt](https://api.github.com/repos/rudy-io/agentic-saas-factory-skills) Ces indicateurs ne mesurent pas la qualité, mais ils signalent un artefact récent et peu validé publiquement. Il n’existe pas, dans les pages consultées, de suite de tests, benchmark, schéma d’artefact, contrat machine-readable, mécanisme de reprise ou preuve de déploiement. Il faut donc le traiter comme un playbook utile, pas comme un composant de production certifié.

Le dépôt revendique une inspiration générale de DeepSec et précise ne pas inclure de code d’exploitation, de contenu DeepSec privé ou de texte propriétaire. [Attribution](https://github.com/rudy-io/agentic-saas-factory-skills/blob/main/docs/ATTRIBUTION.md) La référence Vercel `deepsec`, distincte du skill de Rudy, est un scanner/harness de sécurité open source qui fonctionne avec des coding agents ; sa documentation indique qu’il peut coûter des milliers voire dizaines de milliers de dollars sur de grands dépôts, conserver son état dans `.deepsec/`, reprendre après interruption et être lancé avec des limites de coût et durée. [Dépôt Vercel DeepSec](https://github.com/vercel-labs/deepsec) L’annonce Vercel précise une chaîne scan, investigation, revalidation, enrichissement et export, ainsi qu’un taux de faux positifs annoncé d’environ 10–20 % et un développement encore précoce. [Annonce Vercel](https://vercel.com/blog/introducing-deepsec-find-and-fix-vulnerabilities-in-your-code-base) Ces éléments concernent Vercel `deepsec`, pas le skill Rudy : le harness ne doit pas prétendre disposer de ce scanner simplement en chargeant `deepsec-security-gate`.

## Ce qu’il faut adopter, rendre optionnel ou isoler

### À adopter

- Le contrat d’objectif et de succès vérifiable avant toute mutation.
- Les artefacts versionnés, nommés et séparés : analyse marché, spécification produit, spécification technique, plan de build, preuves de vérification et rapport final.
- Le wedge étroit, le P0 court et l’ordre build-first-workflow avant dashboard, IA ou polish.
- La boucle Discovery/Plan/Exec/Verify/Iterate/Report, avec preuve par étape et arrêt après absence de progrès.
- Le gate défensif secrets/auth/ownership/paiements/uploads/IA/dépendances/déploiement.
- Les lignes rouges comme politiques runtime : pas de secret en clair, pas d’action irréversible sans approbation, pas de tiers ou production sans autorisation explicite.

### Optionnel, à activer selon le risque

- L’étude SEO et le canal d’acquisition ; nécessaire pour un SaaS public, superflue pour un prototype interne isolé.
- Auth, paiement, emails, uploads, IA, 2FA et monitoring ; chacun doit être activé uniquement si le produit les requiert, mais le contrôle correspondant devient obligatoire dès qu’il est activé.
- Le scanner Vercel `deepsec` ou un outil équivalent dans un environnement sandboxé, avec budget, durée, fournisseur de modèle, conservation des données et sortie contrôlés. Le checklist de Rudy ne l’installe pas et ne l’exécute pas.
- Une étape d’approbation humaine après scoring et avant build coûteux, puis avant publication, paiement, envoi ou déploiement.

### À éviter ou isoler

- Traiter le score /30 comme validation de marché ou lancer un build public sur la seule conclusion de l’agent.
- Confondre la documentation Markdown avec une boucle réellement autonome, des tests ou une preuve de sécurité.
- Permettre à l’agent de demander ou d’imprimer des secrets, de contourner les lignes rouges ou de muter DNS/production avec des credentials larges.
- Ajouter l’IA avant que le workflow P0 fonctionne, ou construire un gros dashboard sans action utilisateur démontrée.
- Mélanger données de recherche, données utilisateurs, credentials et artefacts de code dans le même contexte modèle.
- Utiliser le nom « DeepSec » comme garantie : le gate est une checklist, pas une preuve d’absence de vulnérabilités ; même l’outil Vercel distinct annonce des faux positifs et des coûts significatifs. [Annonce Vercel](https://vercel.com/blog/introducing-deepsec-find-and-fix-vulnerabilities-in-your-code-base)

## Architecture de harness recommandée

Le harness peut encapsuler le playbook dans une machine à états : `INTAKE → MARKET_RESEARCH → PRODUCT_SPEC → TECH_SPEC → BUILD_SLICE → VERIFY → SECURITY_GATE → HUMAN_REVIEW → VERDICT`. Chaque état possède un schéma de sortie, une liste d’outils autorisés, un budget, un timeout, des preuves requises et une politique de retry. Le passage à l’état suivant est conditionnel à la validation du schéma et des preuves, non à une phrase d’agent.

Le contexte doit être compartimenté : dossier de travail et branche dédiés, secrets uniquement via un coffre ou injection éphémère, réseau sortant allowlisté, données de test synthétiques, et sandbox pour le code non fiable. Les actions sensibles doivent passer par des adaptateurs idempotents en dry-run, avec approbation et journal d’audit. Les sorties agent doivent être traitées comme des propositions non fiables, notamment les scores, commandes et conclusions de sécurité.

Enfin, le harness devrait compléter ce dépôt par des contrôles absents du playbook : validation JSON/JSON Schema des artefacts, provenance des sources et fraîcheur, tests reproductibles, scan de secrets indépendant, SAST/SCA, tests d’autorisation, sauvegarde/rollback automatisés, limites de coût modèle et d’appels outils, détection d’injection de prompt dans les dépôts et documents analysés, et revue humaine des décisions `GO`/déploiement. La licence MIT autorise la réutilisation avec conservation de la notice et sans garantie ; elle ne constitue ni SLA ni certification de sécurité. [Licence](https://github.com/rudy-io/agentic-saas-factory-skills/blob/main/LICENSE)

## Verdict

À adopter comme **couche de méthode produit et de contrôle**, pas comme moteur d’exécution. La valeur principale est la discipline : expliciter la douleur, tester un wedge, réduire le P0, produire des artefacts vérifiables, construire par tranches et refuser les actions irréversibles par défaut. Pour un harness complet, le contenu doit être isolé derrière une machine à états, des permissions et des preuves indépendantes. Le skill isolé est approprié pour l’idéation et la spécification ; l’orchestrateur public est approprié comme playbook de bout en bout ; le gate DeepSec est un checklist de release à compléter par des outils et une revue autorisée. Ni le score marché, ni un `PASS` textuel, ni la présence d’un fichier `SKILL.md` ne doivent être considérés comme une garantie de viabilité, de sécurité ou de déploiement.

## Références principales

- https://github.com/rudy-io/agentic-saas-factory-skills/blob/main/skills/saas-factory/SKILL.md
- https://github.com/rudy-io/agentic-saas-factory-skills/blob/main/skills/saas-factory-boucle-deepsec/SKILL.md
- https://github.com/rudy-io/agentic-saas-factory-skills/blob/main/skills/boucle-autonome/SKILL.md
- https://github.com/rudy-io/agentic-saas-factory-skills/blob/main/skills/deepsec-security-gate/SKILL.md
- https://github.com/rudy-io/agentic-saas-factory-skills
- https://api.github.com/repos/rudy-io/agentic-saas-factory-skills
- https://github.com/rudy-io/agentic-saas-factory-skills/blob/main/docs/ATTRIBUTION.md
- https://github.com/rudy-io/agentic-saas-factory-skills/blob/main/SECURITY.md
- https://github.com/vercel-labs/deepsec
- https://vercel.com/blog/introducing-deepsec-find-and-fix-vulnerabilities-in-your-code-base
- https://github.com/rudy-io/agentic-saas-factory-skills/blob/main/LICENSE

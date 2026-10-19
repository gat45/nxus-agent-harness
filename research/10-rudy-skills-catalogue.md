# Étude du dépôt public `rudy-io/agentic-saas-factory-skills`

## Conclusion opérationnelle

Le dépôt est un **catalogue public de quatre fichiers d’instructions Markdown**, et non un runtime, un scanner, un orchestrateur distribué ou une preuve de sécurité. Il propose une discipline de travail pour agents de programmation : cadrer une tâche, analyser l’opportunité d’un SaaS, construire par tranches, vérifier les résultats et appliquer une checklist défensive avant livraison. Le dépôt se décrit lui-même comme destiné à des outils qui reconnaissent une convention `SKILL.md` (Codex, Claude Code ou équivalents) et recommande de copier un dossier de skill dans le répertoire de skills de l’agent : [README du dépôt](https://github.com/rudy-io/agentic-saas-factory-skills).

Pour un harness complet, il faut donc **adopter ses contrats, artefacts, vérifications et arrêts comme une couche de politique et de procédure**, sans les confondre avec des contrôles techniques exécutés automatiquement. Les actions à risque, la gestion des secrets, l’isolation du modèle, les permissions outils, les journaux inviolables et les preuves de test doivent être fournis par le harness lui-même.

## Ce qui est effectivement public

L’API GitHub décrit un dépôt public, non forké, sous branche `main`, sous licence MIT, avec les répertoires `skills/` et `docs/`, ainsi que `README.md`, `SECURITY.md` et `LICENSE` : [métadonnées API GitHub](https://api.github.com/repos/rudy-io/agentic-saas-factory-skills), [contenus racine API](https://api.github.com/repos/rudy-io/agentic-saas-factory-skills/contents). L’API indique aussi un dépôt très petit, sans langage détecté, sans release publiée ni téléchargement, et avec un historique public minimal (un commit au moment de la consultation). Ces signaux limitent la maturité démontrable : il s’agit d’un **playbook initial**, pas d’un produit éprouvé par une suite de tests ou un programme de releases.

Les quatre skills sont :

- `saas-factory-boucle-deepsec` : orchestration complète marché → spécifications → build → gate sécurité → vérification → verdict ;
- `boucle-autonome` : protocole générique `Discovery → Plan → Exec → Verify → Iterate → Report` ;
- `saas-factory` : scoring de marché, wedge, spécification MVP, plan de build, acquisition, pricing et décision ;
- `deepsec-security-gate` : checklist défensive couvrant secrets, auth, données, API, paiement, uploads, IA, dépendances, frontend et déploiement.

Les textes canoniques sont publiés dans [orchestrateur](https://raw.githubusercontent.com/rudy-io/agentic-saas-factory-skills/main/skills/saas-factory-boucle-deepsec/SKILL.md), [boucle autonome](https://raw.githubusercontent.com/rudy-io/agentic-saas-factory-skills/main/skills/boucle-autonome/SKILL.md), [SaaS Factory](https://raw.githubusercontent.com/rudy-io/agentic-saas-factory-skills/main/skills/saas-factory/SKILL.md) et [DeepSec Security Gate](https://raw.githubusercontent.com/rudy-io/agentic-saas-factory-skills/main/skills/deepsec-security-gate/SKILL.md).

L’attribution apporte une limite importante : elle dit que la boucle autonome et SaaS Factory sont adaptées d’un workflow privé, tout en affirmant que les chemins privés, secrets, identifiants, détails serveur, hypothèses de projet et données clients ont été retirés. Elle dit aussi que le skill DeepSec ne contient ni code d’exploitation, ni contenu privé DeepSec, ni texte propriétaire ; il adopte seulement une idée générale de revue défensive : [ATTRIBUTION.md](https://raw.githubusercontent.com/rudy-io/agentic-saas-factory-skills/main/docs/ATTRIBUTION.md). Rien dans cette étude ne permet donc de prétendre accéder au workflow privé, à des prompts système privés ou à des fonctionnalités non publiées.

## Mécanismes et étapes utiles

### 1. Contrat de tâche avant action

L’orchestrateur impose un contrat avant toute action : objectif, critère de succès vérifiable, utilisateur cible, problème, livrable, périmètre, hors périmètre, budget d’itérations, risques irréversibles et commandes de vérification. La boucle autonome reprend une version plus générique avec risque principal, budget et lignes rouges. C’est une bonne primitive de harness : elle transforme une demande vague en **objet exécutable et auditable**.

À adopter : un schéma machine-readable équivalent, validé avant l’octroi d’outils. Le harness doit refuser ou demander clarification si le critère est absent pour une tâche à risque élevé. Pour les tâches à faible risque, il peut proposer un critère, mais doit enregistrer que celui-ci a été inféré.

### 2. Discovery et plan court

La boucle autonome demande de lire les instructions du projet, l’architecture, les fichiers proches, l’état Git, la documentation locale et les erreurs disponibles, puis de reformuler la compréhension et de produire un plan avec vérification et rollback. Cela donne au harness une séquence utile : **contexte local → plan borné → exécution minimale**. Le texte ne fournit toutefois ni format de snapshot, ni contrôle de fraîcheur, ni mécanisme empêchant le modèle de considérer une instruction hostile du dépôt comme une autorité.

À adopter avec une hiérarchie de confiance explicite : politique du harness et instructions utilisateur au-dessus des fichiers inspectés ; contenu du dépôt traité comme données non fiables ; prompt injection détectée et signalée ; commandes proposées séparées des commandes autorisées.

### 3. Factory produit et décision économique

SaaS Factory demande de produire `01-analyse-marche.md`, `02-spec-produit.md`, `03-spec-technique.md`, `04-plan-build.md` et `05-rapport-final.md`. Le marché est noté sur 30 selon douleur, urgence, budget, concurrence/angle, acquisition et faisabilité. Les seuils publics sont `GO` à 22–30, `TEST` à 16–21 et `NO-GO`/outil interne à 0–15. Le skill demande aussi un wedge étroit, les alternatives existantes, l’acquisition plausible, le pricing, les coûts variables de l’IA et les limites du MVP : [SaaS Factory](https://raw.githubusercontent.com/rudy-io/agentic-saas-factory-skills/main/skills/saas-factory/SKILL.md).

À adopter comme **cadre de décision et format de livrables**, pas comme vérité prédictive. Le score est heuristique, sans protocole d’échantillonnage, sources obligatoires, calibration historique ou validation humaine. Le harness devrait exiger les sources et distinguer faits, hypothèses et jugement ; le seuil numérique ne doit jamais déclencher seul une dépense, un lancement public ou une décision irréversible.

### 4. Build incrémental et vérification

L’orchestrateur recommande de construire par tranches : initialisation/audit, modèle de données, auth, workflow principal, landing, admin minimal, puis paiement, IA, analytics et logs. Chaque tranche doit rendre compte des fichiers modifiés, du risque, de la vérification, du résultat et de la prochaine tranche. La boucle autonome demande de corriger une cause racine à la fois et de s’arrêter après trois cycles sans progrès notable : [orchestrateur](https://raw.githubusercontent.com/rudy-io/agentic-saas-factory-skills/main/skills/saas-factory-boucle-deepsec/SKILL.md), [boucle autonome](https://raw.githubusercontent.com/rudy-io/agentic-saas-factory-skills/main/skills/boucle-autonome/SKILL.md).

À adopter : un état de tâche append-only ou versionné, un diff par tranche, une preuve de vérification attachée et un plafond d’itérations/coût. À compléter : isolation des worktrees, sandbox d’exécution, allowlist de commandes, timeouts, quotas réseau et restauration automatique.

### 5. Gate défensif avant livraison

Le gate DeepSec distingue `PASS`, `PASS AVEC RESERVES` et `FAIL`, et demande un rapport avec surface auditée, preuves, bloquants, risques et correctifs. Il couvre notamment : absence de secrets commités, variables d’environnement sans valeurs, auth et rôles vérifiés côté serveur, sessions/cookies, minimisation et protection des données, validation/rate limiting/CORS/CSRF/ownership des API, webhooks de paiement signés et idempotents, uploads bornés et privés, garde-fous IA, quotas/coûts, lockfile et audit des dépendances, sanitation frontend, build, migrations, backup, rollback, HTTPS et headers : [DeepSec Security Gate](https://raw.githubusercontent.com/rudy-io/agentic-saas-factory-skills/main/skills/deepsec-security-gate/SKILL.md).

C’est la partie la plus directement réutilisable pour un harness de livraison. À adopter comme **contrat de contrôle**, avec preuves structurées et une politique qui bloque la promotion en cas de `FAIL`. À ne pas présenter comme un scan complet : la checklist n’exécute pas elle-même les tests, ne prouve pas l’absence de vulnérabilité et ne remplace ni revue humaine ni outils spécialisés.

## Garde-fous et lignes rouges

Les deux skills de boucle demandent confirmation avant d’envoyer des emails/SMS/messages à de vraies personnes, lancer un paiement, supprimer des données sans backup, exposer une application contenant des données personnelles, modifier DNS ou infrastructure critique, déployer sans rollback, utiliser un secret introuvable ou changer une décision produit ouverte. Ils interdisent de demander ou d’écrire un secret en clair. Le dépôt ajoute une politique publique interdisant l’attaque de tiers, le contournement de contrôles, la collecte d’identifiants, le scan sans autorisation et la publication de secrets/données privées : [SECURITY.md](https://raw.githubusercontent.com/rudy-io/agentic-saas-factory-skills/main/SECURITY.md).

Ces garde-fous sont pertinents, mais leur forme est principalement déclarative. Un agent peut ignorer une phrase ou mal classer une commande. Le harness doit donc convertir chaque ligne rouge en **capability gate technique** : approbation explicite, jeton à portée limitée, environnement de test, simulation/dry-run, transaction réversible, backup vérifié, journalisation et possibilité de révocation. L’absence de preuve d’autorisation doit être un refus, non une permission implicite.

Le gate DeepSec recommande aussi de ne pas envoyer de données sensibles au modèle sans raison, de filtrer ou confirmer les actions irréversibles, de journaliser coûts/modèles/erreurs, de valider la sortie IA avant insertion critique et de fournir un fallback. Ce sont de bons invariants de confidentialité et de robustesse, mais il faut les implémenter au niveau du proxy outils/modèles et de la couche données, pas uniquement dans le prompt : [DeepSec Security Gate](https://raw.githubusercontent.com/rudy-io/agentic-saas-factory-skills/main/skills/deepsec-security-gate/SKILL.md).

## Dépendance et distinction avec Vercel `deepsec`

L’attribution de Rudy cite [Vercel Labs `deepsec`](https://github.com/vercel-labs/deepsec) comme inspiration et affirme ne pas copier son code, ses matchers, ses données privées ou son texte propriétaire. Le dépôt Vercel est un outil distinct : scanner regex, investigation par agents, revalidation, enrichissement, export et exécution optionnelle en sandbox ; il ajoute un dossier `.deepsec` au dépôt et documente des plafonds de coût/durée. Son README avertit de le traiter comme un agent de programmation avec accès shell complet et précise que les scans de grands dépôts peuvent coûter des milliers voire dizaines de milliers de dollars : [README Vercel deepsec](https://github.com/vercel-labs/deepsec).

L’annonce officielle Vercel décrit le flux `Scan → Investigate → Revalidate → Enrich → Export`, estime un taux de faux positifs d’environ 10–20 % dans son expérience et qualifie le projet de développement encore précoce : [annonce Vercel](https://vercel.com/blog/introducing-deepsec-find-and-fix-vulnerabilities-in-your-code-base). Ces éléments sont importants pour le harness : si `deepsec` est adopté comme outil optionnel, il faut isoler son exécution, plafonner coût/durée, protéger les clés, traiter les sorties comme des findings à confirmer et ne jamais transformer un `PASS` en preuve d’absence de vulnérabilité.

Le site `deepsec-skill.dev` distingue explicitement le scanner Vercel, son propre wrapper et son standard opératoire ; il recommande autorisation explicite, threat sketch, preuves défensives et incertitude honnête (`needs-authorized-validation`) : [standard DeepSec public](https://www.deepsec-skill.dev/). Ce standard n’est pas une dépendance du dépôt Rudy ; il constitue seulement une référence publique supplémentaire utile pour enrichir le protocole, avec attribution séparée.

## Limites, maturité et risques d’usage

1. **Instructions, pas exécution.** Les fichiers Markdown ne sont ni un moteur de policy, ni un orchestrateur, ni une suite de tests. Les noms de fichiers et les étapes n’existent que si le harness ou l’agent les matérialise.
2. **Preuves insuffisamment normalisées.** Les rapports demandés sont lisibles par humain, mais aucun schéma de finding, niveau de confiance, provenance, hash d’artefact ou journal append-only n’est imposé.
3. **Sécurité non exhaustive.** La checklist couvre de nombreuses erreurs fréquentes, mais elle ne traite pas complètement supply chain, provenance/signature des artefacts, prompt injection dans les données, fuite via télémétrie, multi-tenancy complexe, disponibilité, gestion des identités du harness ou compromission du modèle.
4. **Scoring business subjectif.** Les seuils `GO/TEST/NO-GO` ne sont pas validés empiriquement dans le dépôt. Ils doivent rester des signaux de discussion.
5. **Peu de maturité observable.** L’API publique indique petite taille, absence de tags/releases et historique public très court au moment de la consultation : [API du dépôt](https://api.github.com/repos/rudy-io/agentic-saas-factory-skills). Il faut le traiter comme un playbook versionné par le harness, avec revue et tests internes.
6. **Risque de surconfiance.** Le mot « gate » peut suggérer une garantie. Il faut afficher la couverture réelle, les contrôles non exécutés et les risques résiduels.
7. **Risque de contexte hostile.** La phase Discovery lit du code et des documents potentiellement contrôlés par un tiers. Sans isolation et hiérarchie d’instructions, un dépôt malveillant peut influencer l’agent.

## Décision pour le harness

### À adopter

- Contrat de tâche obligatoire avec objectif, succès mesurable, périmètre, budget, risques et vérifications.
- Cycle `Discovery → Plan → Exec → Verify → Iterate → Report`, avec état versionné et preuves.
- Construction incrémentale, diff limité, cause racine et arrêt après absence de progrès.
- Artefacts standardisés de marché, produit, technique, build, sécurité et rapport final.
- Gate de sécurité défensif couvrant secrets, auth/roles, ownership, données, paiements, uploads, IA, dépendances, déploiement et rollback.
- Lignes rouges traduites en approbations et restrictions d’outils exécutables.
- Verdicts explicites `PASS`, `PASS AVEC RESERVES`, `FAIL` et `GO/TEST/PIVOT/NO-GO`, toujours accompagnés de preuves et d’incertitudes.

### Optionnel ou à adapter

- Scoring marché sur 30 et seuils numériques, à utiliser comme heuristique documentée.
- `deepsec` de Vercel pour une revue séparée, uniquement sur code autorisé et dans une sandbox à coût/durée plafonnés.
- 2FA, paiement, emails, analytics, IA et acquisition, selon le produit et son niveau de risque.
- Enrichissement Git, rapports Markdown et conventions exactes de noms de fichiers ; le harness peut imposer JSON + Markdown.

### À éviter ou isoler

- Copier les skills et supposer que l’agent respectera les contrôles sans enforcement.
- Exécuter une commande shell proposée par le dépôt ou le modèle sans allowlist, sandbox, timeout et journal.
- Envoyer automatiquement emails, paiements, suppressions, déploiements, DNS ou secrets.
- Déclarer une application sûre parce qu’une checklist est remplie ou qu’un scanner n’a rien trouvé.
- Mélanger la checklist Rudy avec le scanner Vercel ou le standard `deepsec-skill.dev` comme s’il s’agissait d’un même produit.
- Charger des instructions privées, prompts système privés ou fonctionnalités non attestées : seules les sources publiques citées ici fondent cette étude.

## Architecture minimale recommandée

Le harness devrait implémenter un **policy engine** qui reçoit le contrat de tâche et calcule les capabilities autorisées ; un **workspace isolé** pour le dépôt et les tests ; un **tool broker** qui contrôle shell, réseau, fichiers, secrets et déploiement ; un **evidence store** append-only liant chaque affirmation à une commande, URL, diff ou artefact ; un **approval service** pour les lignes rouges ; un **security gate runner** qui exécute les contrôles et marque les contrôles non exécutés ; et un **release controller** qui interdit la promotion si le verdict ou les preuves requises manquent.

Cette architecture est la traduction technique des principes publics du catalogue. Elle ne prétend pas être fournie par Rudy. Le dépôt fournit les procédures et formats conceptuels ; le harness doit fournir l’enforcement, l’isolation, la mesure et la responsabilité opérationnelle.

## Références

- [Dépôt GitHub](https://github.com/rudy-io/agentic-saas-factory-skills)
- [README brut](https://raw.githubusercontent.com/rudy-io/agentic-saas-factory-skills/main/README.md)
- [API métadonnées](https://api.github.com/repos/rudy-io/agentic-saas-factory-skills)
- [Orchestrateur](https://raw.githubusercontent.com/rudy-io/agentic-saas-factory-skills/main/skills/saas-factory-boucle-deepsec/SKILL.md)
- [Boucle autonome](https://raw.githubusercontent.com/rudy-io/agentic-saas-factory-skills/main/skills/boucle-autonome/SKILL.md)
- [SaaS Factory](https://raw.githubusercontent.com/rudy-io/agentic-saas-factory-skills/main/skills/saas-factory/SKILL.md)
- [DeepSec Security Gate](https://raw.githubusercontent.com/rudy-io/agentic-saas-factory-skills/main/skills/deepsec-security-gate/SKILL.md)
- [SECURITY.md](https://raw.githubusercontent.com/rudy-io/agentic-saas-factory-skills/main/SECURITY.md)
- [ATTRIBUTION.md](https://raw.githubusercontent.com/rudy-io/agentic-saas-factory-skills/main/docs/ATTRIBUTION.md)
- [Vercel Labs deepsec](https://github.com/vercel-labs/deepsec)
- [Annonce officielle Vercel](https://vercel.com/blog/introducing-deepsec-find-and-fix-vulnerabilities-in-your-code-base)
- [DeepSec public standard](https://www.deepsec-skill.dev/)

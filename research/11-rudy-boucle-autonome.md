# Skill « Boucle autonome » de Rudy : évaluation pour un harness agentique

## Verdict opérationnel

Le skill `boucle-autonome` est un **protocole de pilotage en Markdown**, pas un moteur d’agents. Il donne à un agent de coding une discipline de travail vérifiable : cadrer, inspecter, planifier, exécuter par petites étapes, vérifier avec des preuves, itérer puis rendre compte. Le dépôt le décrit explicitement comme un protocole pour les tâches dont l’objectif et le critère de succès peuvent être vérifiés, et recommande l’arrêt devant les actions irréversibles, les secrets, les paiements, les messages à des tiers, les suppressions sans sauvegarde et les ambiguïtés produit majeures [1].

Pour un harness complet, il faut donc **adopter la structure et les artefacts**, mais les transformer en contrôles exécutables. Le texte seul ne fournit ni sandbox, ni gestion de permissions, ni machine d’état persistante, ni stratégie de retry, ni preuve cryptographiquement liée à l’exécution. Les actions à impact externe doivent rester isolées derrière une politique de capacités et une approbation humaine explicite.

## Ce que le skill est réellement

Le dépôt public présente quatre skills génériques destinés aux outils qui supportent une convention `SKILL.md`, notamment Codex et Claude Code. `boucle-autonome` est le composant consacré à la boucle fermée pour les tâches vérifiables ; il est distinct de la factory SaaS et du gate de sécurité DeepSec [2]. L’attribution précise que ce skill est adapté d’un protocole privé de boucle autonome et que les chemins, secrets, détails serveur, hypothèses projet et données clients ont été retirés [3]. Il ne faut donc pas lui attribuer des fonctionnalités privées ou supposer qu’il révèle le protocole interne complet de Rudy.

La boucle proposée est : **Discovery → Plan → Exec → Verify → Iterate → Report** [1]. Son rôle réel est de rendre explicites les points de décision d’un agent déjà capable d’utiliser un terminal, des fichiers et des outils de test. Elle ne définit pas l’implémentation de ces outils et ne garantit pas qu’une vérification soit honnête, complète ou indépendante.

## Mécanismes et étapes utiles

### 1. Preflight : contrat de tâche

Avant toute action, le skill demande de consigner : objectif, critère de succès vérifiable, périmètre, hors périmètre, risque principal, budget temps/itérations, vérification prévue et lignes rouges [1]. C’est la partie la plus directement réutilisable dans un harness : elle convertit une demande vague en contrat testable et crée un point d’arrêt avant l’accès aux outils.

Le critère doit être observable : build qui passe, endpoint HTTP qui répond, fichier qui s’ouvre ou formulaire qui crée effectivement un enregistrement [1]. Dans le harness, ce contrat doit être un objet structuré et versionné, pas seulement du texte libre. Il devrait contenir une condition d’acceptation, une liste de commandes autorisées, un budget de durée/coût, les ressources touchées et le niveau d’approbation requis.

### 2. Discovery : réduire les suppositions

La phase Discovery impose de lire les instructions du projet, l’architecture, les fichiers proches, l’état Git, la documentation locale et les logs disponibles, puis de reformuler la compréhension en trois lignes maximum [1]. Cette contrainte est utile contre le démarrage prématuré et le refactoring hors sujet.

À implémenter comme précondition de l’exécution : inventaire des fichiers et instructions effectivement lus, commit ou snapshot de départ, statut de l’arbre de travail, et détection des instructions contradictoires. Le résumé court est un artefact de traçabilité ; il ne doit pas remplacer les données brutes de découverte.

### 3. Plan : exécution bornée

Le plan demandé est court et contient des étapes, une vérification et un rollback [1]. Cette forme est adaptée à un orchestrateur : elle permet de comparer l’intention avant action avec les commandes réellement exécutées. Elle est insuffisante si le plan ne précise pas les permissions, les fichiers mutables, les effets réseau et les critères d’arrêt.

### 4. Exec : changement minimal et réversible

Les règles d’exécution sont : modifier le minimum nécessaire, respecter le style existant, faire une sauvegarde avant une modification risquée, ne jamais supprimer sans confirmation, ne jamais écrire de secret, journaliser les décisions importantes et ne pas refactorer hors sujet [1]. Elles forment une bonne politique par défaut pour un agent de code.

Le harness doit les rendre opposables : espace de travail isolé, patch/diff obligatoire, snapshots ou branche éphémère, détection de secrets avant écriture et après commande, allowlist des commandes, limites réseau et séparation des identités. « Faire un backup » doit être une opération vérifiable ; une phrase dans le prompt n’est pas un backup.

### 5. Verify : preuves plutôt que déclaration

Le skill interdit de conclure sans preuve et propose, selon le contexte, tests unitaires, build, lint, smoke test, requête HTTP, inspection visuelle, vérification de fichier, comparaison avant/après, recherche de secrets et lecture du diff [1]. Si les tests ne tournent pas, il demande d’expliquer pourquoi et d’utiliser une vérification alternative.

C’est un bon catalogue d’adaptateurs de vérification. Dans un harness, chaque vérificateur doit produire un résultat structuré : commande, environnement, horodatage, code de sortie, sortie normalisée, artefacts et statut. Les preuves doivent être produites par un composant distinct du modèle lorsque c’est possible. Il faut séparer « test non exécuté », « test échoué » et « test passé » ; une vérification alternative ne doit pas être automatiquement équivalente au test nominal.

### 6. Iterate : correction contrôlée

Après un échec, le protocole prescrit l’identification de la cause racine, une correction à la fois, une nouvelle vérification et un arrêt après trois cycles sans progrès [1]. Cette règle donne un plafond simple contre les boucles infinies et encourage une attribution causale.

À compléter par détection de progrès objective, budget global, backoff, arrêt sur répétition de mêmes commandes/erreurs et conservation du diff de chaque cycle. Le nombre « trois » est une heuristique optionnelle, pas une garantie de convergence : un bug peut nécessiter quatre cycles, tandis que trois changements aveugles peuvent déjà être dangereux.

### 7. Report : sortie auditable

Le rapport final demandé contient objectif, critère, fait, vérification, résultat, risques restants et prochaine action, avec citation des preuves : commandes, URLs, fichiers, captures ou logs [1]. C’est l’interface de sortie minimale à conserver dans un harness. Elle doit inclure aussi l’identité de l’agent/modèle, les outils appelés, les permissions, les coûts, les artefacts et les approbations.

## Garde-fous à adopter

Le skill impose une confirmation avant l’envoi d’emails/SMS/messages à des tiers, le déclenchement d’un paiement, l’exposition ou l’utilisation d’un secret, la suppression de données sans backup, la modification de DNS ou d’une infrastructure critique sans rollback, la publication d’une application contenant des données personnelles et un changement de décision produit ouverte [1].

À adopter comme **politique de capacités** :

- lecture et écriture locale limitées au workspace approuvé ;
- réseau sortant désactivé par défaut ou limité à une allowlist ;
- secrets injectés uniquement au dernier moment, jamais dans le contexte ou les logs ;
- paiements, messages, publication, DNS, production et suppressions placés derrière des outils séparés exigeant une approbation ;
- backup/rollback vérifiés avant mutation destructive ;
- journal append-only des décisions, commandes, résultats et approbations ;
- expiration de tâche, plafond d’itérations et plafond de coût ;
- arrêt automatique en cas d’ambiguïté produit, échec de contrôle de sécurité ou divergence du périmètre.

La politique de sécurité du dépôt confirme sa portée défensive : ne pas attaquer de systèmes tiers, contourner des contrôles d’accès, récolter des identifiants ou scanner sans autorisation ; en cas de secret accidentel, elle recommande révocation/rotation, suppression des fichiers, inspection de l’historique et recours à un vrai gestionnaire de secrets [4]. Ces points doivent être repris dans le harness, mais la rotation réelle doit être exécutée par un opérateur ou un intégrateur autorisé, pas improvisée par le modèle.

## Limites et risques

**Ce n’est pas une garantie de sécurité.** Les lignes rouges reposent sur l’interprétation de l’agent et sur la capacité de l’environnement à distinguer une action locale d’un effet externe. Un agent peut mal classer une commande, exfiltrer une donnée via un outil autorisé ou déclarer une vérification trop faible.

**Le protocole ne définit pas d’isolation.** Il ne dit rien sur conteneur, VM, permissions Unix, accès réseau, montage de secrets, quotas CPU/mémoire, persistance ou multi-tenant. Ces fonctions sont indispensables dans un harness exécutable et doivent être fournies par la plateforme d’exécution.

**La vérification peut être auto-référentielle.** Le même agent peut écrire le code, choisir le test, l’exécuter et interpréter le résultat. Pour les tâches à risque, utiliser des vérificateurs déterministes ou un second rôle indépendant, avec des tests d’acceptation définis avant l’exécution.

**Le rollback est seulement nommé.** Aucun format de snapshot, transaction, stratégie de migration ou restauration n’est spécifié. Pour bases, DNS et déploiements, le harness doit imposer un runbook et vérifier sa restaurabilité avant d’autoriser l’action.

**Le langage « continuer jusqu’au succès » peut sur-optimiser.** Le prompt de lancement demande de continuer jusqu’au succès vérifié ou au blocage réel [1]. Sans budget dur, cela peut multiplier les appels, coûts et changements. Le harness doit rendre les plafonds non négociables, même si l’agent affirme être proche du succès.

**Pas de contexte de production ni de conformité.** Le skill reste générique. Il ne traite pas précisément de classification des données, conservation, consentement, séparation des tenants, exigences réglementaires, revue humaine par domaine ou gestion d’incident.

## Maturité et dépendances observables

Le dépôt indique une licence MIT et une installation par copie du fichier dans le répertoire de skills de l’agent [2]. La vue publique du dépôt expose une racine réduite (`README.md`, `LICENSE`, `SECURITY.md`, `docs/`, `skills/`) et ne montre ni tests automatisés ni workflow CI dans cette publication [5]. L’API GitHub retourne un seul commit pour le fichier, « Initial public release of agentic SaaS factory skills », daté du 2 juillet 2026, non signé [6].

Cela correspond à un **prototype documentaire public utile**, pas à un composant mature de contrôle ou à une preuve d’efficacité en production. Sa dépendance principale est l’agent hôte capable de lire `SKILL.md`, de manipuler des fichiers/outils et d’exécuter des vérifications. Sa licence MIT facilite l’adaptation, mais l’attribution précise que le contenu public ne comprend pas les éléments privés retirés [3].

## Décision pour le harness

### À adopter obligatoirement

1. Le contrat de preflight structuré avec objectif, critères, périmètre, risques, budget et lignes rouges.
2. La machine d’état explicite `discovery → plan → exec → verify → iterate → report`.
3. Les preuves de vérification indépendantes et les statuts distincts pass/échec/non exécuté.
4. Le diff, le snapshot et le rollback avant toute mutation risquée.
5. Les plafonds d’itérations, durée, coût et changements.
6. Les approbations humaines et outils séparés pour paiements, communications, secrets, données personnelles, production, DNS et suppressions.
7. Le rapport final avec artefacts, commandes, sorties, risques restants et prochaine action.

### À conserver comme options

Le résumé Discovery en trois lignes, la limite de trois cycles sans progrès, l’inspection visuelle et la comparaison avant/après sont de bonnes heuristiques, à activer selon le type de tâche. Les tests peuvent être remplacés par une vérification alternative uniquement si le rapport marque clairement la couverture manquante et le risque résiduel.

### À éviter ou isoler

Ne pas traiter `SKILL.md` comme un sandbox, une politique d’autorisation complète, un secret manager, un orchestrateur durable ou une preuve de conformité. Ne pas laisser le modèle définir seul le critère de succès d’une opération sensible, s’auto-attribuer une approbation, exécuter des commandes arbitraires ou transformer « absence de test » en « succès ». Ne pas importer de contenu privé présumé de Rudy ni prétendre disposer de fonctionnalités non attestées par les sources publiques.

## Architecture minimale recommandée

Le harness peut implémenter le skill comme une machine d’état persistante autour de six interfaces :

- `TaskContract` : objectif, critères, scope, budget, données, capacités et approbations requises ;
- `DiscoveryRecord` : fichiers/instructions lus, snapshot initial, hypothèses et résumé ;
- `ExecutionPlan` : étapes, commandes/outils autorisés, risques, rollback et vérificateurs ;
- `ActionGateway` : exécution sandboxée avec policy-as-code et capacités temporaires ;
- `VerificationResult` : preuve structurée, indépendante si nécessaire, avec couverture et limites ;
- `RunReport` : résultat, diff, logs, artefacts, coûts, risques et décision de livraison.

Le modèle propose et explique. Le contrôleur de politique décide si l’outil peut être appelé. Le vérificateur observe l’état réel. L’approbateur humain autorise seulement les effets externes explicitement listés. Cette séparation transforme la bonne discipline du skill en contrôle exploitable, tout en respectant sa portée publique et ses limites.

## Références

[1]: https://github.com/rudy-io/agentic-saas-factory-skills/blob/main/skills/boucle-autonome/SKILL.md "Skill public Boucle autonome"
[2]: https://raw.githubusercontent.com/rudy-io/agentic-saas-factory-skills/main/README.md "README public du dépôt Agentic SaaS Factory Skills"
[3]: https://raw.githubusercontent.com/rudy-io/agentic-saas-factory-skills/main/docs/ATTRIBUTION.md "Attribution et limites de la publication"
[4]: https://raw.githubusercontent.com/rudy-io/agentic-saas-factory-skills/main/SECURITY.md "Politique de sécurité publique"
[5]: https://api.github.com/repos/rudy-io/agentic-saas-factory-skills/contents "Contenu public de la racine du dépôt via l’API GitHub"
[6]: https://api.github.com/repos/rudy-io/agentic-saas-factory-skills/commits?path=skills/boucle-autonome/SKILL.md&per_page=10 "Historique public du fichier SKILL.md"
[7]: https://www.nist.gov/itl/ai-risk-management-framework "NIST AI Risk Management Framework"

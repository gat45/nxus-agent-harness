# Mode réflexion avant action de Nxus : évaluation pour un harness agentique

## Conclusion opérationnelle

Le sujet Nxus décrit un **contrôle de changement en deux phases** : l’agent analyse et formalise d’abord un plan dans `PLAN.md`, puis attend une validation humaine explicite avant de modifier le code. Après exécution, il produit un compte rendu comparant le plan au résultat réel. La page ne décrit pas un produit Nxus, un protocole, un modèle ou une implémentation propriétaire : c’est un cas d’usage et une pratique de pilotage pour des agents de code tels que Claude Code et Cursor. Source primaire : [NXUS, « Mode réflexion avant action »](https://nxus.fr/cas-usage-agents-ia/mode-reflexion-avant-action-agent).

Pour le harness, il faut donc adopter **le gating séparant proposition, approbation et exécution**, mais ne pas traiter `PLAN.md` comme une frontière de sécurité suffisante. L’autorisation doit être imposée par le moteur d’exécution et la politique d’outils, avec validation atomique de l’action exacte, isolation de l’environnement, limites de portée et journal d’audit.

## Ce que la source Nxus établit réellement

Nxus part de trois problèmes concrets : l’agent peut foncer dans le code et casser des éléments adjacents, une modification non planifiée est difficile à relire ou à annuler proprement, et les effets de bord non anticipés augmentent le temps de débogage. L’approche proposée est : instruire l’agent de produire `PLAN.md` avant le code ; y lister les fichiers touchés, les risques et les alternatives ; faire valider ou modifier le plan ; exécuter uniquement ce qui est acté ; puis produire un résumé post-action comparant le plan initial à ce qui a effectivement été fait. [NXUS](https://nxus.fr/cas-usage-agents-ia/mode-reflexion-avant-action-agent)

Les trois étapes publiées sont : **rédaction du plan de réflexion**, **validation humaine**, puis **exécution et rapport post-action**. L’exemple de prompt demande une stratégie de pagination, les fichiers concernés, les risques et les alternatives écartées. Le verdict Nxus est favorable, surtout pour les changements structurels, tout en reconnaissant un ralentissement léger. [NXUS](https://nxus.fr/cas-usage-agents-ia/mode-reflexion-avant-action-agent)

La portée est volontairement limitée : la page ne garantit ni la qualité du raisonnement, ni la détection complète des fichiers affectés, ni la conformité effective de l’agent à un plan modifié. Elle n’atteste pas d’un dépôt public, d’une API, d’un schéma de `PLAN.md`, d’un système d’approbation cryptographique, d’un sandbox, d’un journal infalsifiable ou d’une capacité Nxus d’exécuter les actions. Aucun accès à du code privé ou à des prompts système privés n’est revendiqué dans ce rapport.

## Mécanismes utiles à reprendre

### 1. Un état explicite de session

Le harness devrait modéliser au minimum les états `DRAFTING`, `AWAITING_APPROVAL`, `APPROVED`, `EXECUTING`, `VERIFYING`, `COMPLETED` et `ABORTED`. Un plan approuvé doit être immuable ou versionné ; toute modification du périmètre, des paramètres ou des outils revient à `AWAITING_APPROVAL`.

### 2. Un artefact de plan structuré

`PLAN.md` est utile comme artefact humain et partageable. Pour l’exécution, il faut lui adjoindre un manifeste structuré (par exemple JSON) contenant : identifiant de session, objectif, commit de base, fichiers et ressources ciblés, opérations autorisées, commandes de test, risques, alternatives, préconditions, durée d’expiration, approbateur et empreinte du plan. Le Markdown est l’interface de revue ; le manifeste est l’interface de politique.

Le plan doit distinguer **lecture**, **analyse**, **écriture**, **commande**, **réseau**, **déploiement** et **actions externes**. « Fichiers concernés » ne suffit pas pour une commande shell pouvant toucher indirectement d’autres chemins ou appeler un réseau.

### 3. Une approbation liée à l’action exacte

Le principe Nxus de « feu vert explicite » doit devenir une décision vérifiable par le moteur, et non une instruction dans le prompt. OWASP recommande que l’autorisation soit vérifiée hors du contexte du modèle, liée à l’acteur, à l’outil, à la ressource, aux paramètres normalisés, à l’expiration et à un identifiant d’approbation ; la vérification et la consommation doivent être atomiques pour empêcher la réutilisation ou la course concurrente. [OWASP AI Agent Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/AI_Agent_Security_Cheat_Sheet.html)

### 4. Une exécution strictement bornée

Après approbation, le harness doit recalculer les appels d’outils et refuser ceux qui sortent du manifeste. Les chemins doivent être normalisés, les liens symboliques contrôlés et les commandes interprétées par une politique, pas simplement comparées comme des chaînes. Les secrets, fichiers de configuration sensibles et accès de production doivent rester hors de portée par défaut.

Les règles publiques de Claude Code illustrent cette séparation : les règles de permission sont appliquées par l’outil et non par le modèle ou le prompt ; elles peuvent `allow`, `ask` ou `deny`, avec une priorité deny puis ask puis allow. [Claude Code — Configure permissions](https://docs.anthropic.com/en/docs/claude-code/permissions). Ce point est transposable au harness, sans supposer que le harness utilise Claude Code.

### 5. Une vérification post-action indépendante

Le rapport post-action Nxus est une bonne interface de traçabilité. Il devrait comparer le manifeste approuvé au diff réel : fichiers ajoutés, supprimés et modifiés ; commandes exécutées ; sorties et échecs ; tests lancés ; changements de dépendances ; accès réseau ; écarts ; approbations ; et décision finale. La revue doit porter sur l’état réel du dépôt, pas uniquement sur le résumé produit par le même agent.

Cursor documente un mécanisme complémentaire de revue dédiée des changements locaux, automatique ou manuelle, avec une profondeur « Quick » ou « Deep » adaptée respectivement aux petits diffs et aux changements complexes ou sensibles à la sécurité. [Cursor — Agent Review](https://cursor.com/docs/agent/agent-review). C’est un modèle utile pour la phase `VERIFYING`, mais une revue LLM ne remplace ni les tests déterministes ni une politique d’autorisation.

## Interfaces et artefacts recommandés

- **Entrée de tâche** : objectif, contraintes, périmètre, niveau de risque et critères d’acceptation.
- **Plan lisible** : `PLAN.md`, éditable par l’humain, avec fichiers, approche, risques, alternatives, tests et questions ouvertes.
- **Manifeste machine** : version du plan, empreinte, outil et paramètres autorisés, ressources, budgets, expiration et approbateur.
- **Écran d’approbation** : diff du plan, risques, permissions demandées, ressources externes, changement de mode et bouton de refus/commentaire.
- **Journal append-only** : événements horodatés et corrélés à la session ; redaction des secrets ; conservation adaptée aux exigences de conformité.
- **Rapport post-action** : plan contre réalité, diff, tests, écarts, incidents et recommandation de suite.
- **Interface d’arrêt** : annulation immédiate, révocation des jetons et nettoyage de l’environnement de travail.

Le plan doit être enregistré dans un emplacement dédié et versionné. Cursor indique que ses plans peuvent être enregistrés par défaut dans le répertoire utilisateur ou déplacés dans l’espace de travail pour partage et documentation. [Cursor — Plan Mode](https://cursor.com/docs/agent/plan-mode). Cette pratique montre l’intérêt du partage, mais le chemin exact et le comportement de Cursor ne doivent pas être présumés pour un autre harness.

## Garde-fous indispensables

1. **Deny by default** pour les outils d’écriture, shell, réseau, secrets, identité, déploiement et actions externes ; n’autoriser que le minimum requis pour le plan approuvé. OWASP demande le moindre privilège, un cloisonnement par outil et des allowlists de chemins/opérations. [OWASP](https://cheatsheetseries.owasp.org/cheatsheets/AI_Agent_Security_Cheat_Sheet.html)
2. **Séparer décision et exécution** : le modèle propose ; un policy engine indépendant valide ; un executor borné applique.
3. **Validation de toutes les entrées externes** : documents, pages web, résultats d’API et sorties d’outils sont des données non fiables, potentiellement porteuses d’injection. [OWASP](https://cheatsheetseries.owasp.org/cheatsheets/AI_Agent_Security_Cheat_Sheet.html)
4. **Approbation courte et non rejouable** : TTL, nonce ou identifiant consommé, paramètres normalisés et confirmation renforcée pour suppression, paiement, changement de privilège, publication ou production. [OWASP](https://cheatsheetseries.owasp.org/cheatsheets/AI_Agent_Security_Cheat_Sheet.html)
5. **Sandbox et isolation** : branche ou worktree dédié, système de fichiers limité, réseau sortant filtré, ressources et durée plafonnées. Le plan réduit le risque de dérive mais ne neutralise pas une injection de prompt.
6. **Hooks ou middleware pré-outil** : si un framework en fournit, utiliser un point avant exécution capable d’autoriser, demander, refuser ou réécrire l’appel. Claude Code documente `PreToolUse` et l’injection de `plan`/`planFilePath` pour `ExitPlanMode`, ainsi que la possibilité de bloquer ou modifier un appel ; cela atteste d’un mécanisme Claude Code, pas d’une fonctionnalité Nxus. [Claude Code — Hooks reference](https://docs.anthropic.com/en/docs/claude-code/hooks)
7. **Observabilité** : journaliser décisions, appels, résultats, coûts, taux d’échec et événements de sécurité en masquant les secrets. OWASP recommande l’audit des appels et décisions, la détection d’anomalies et des métadonnées structurées pour les actions à risque. [OWASP](https://cheatsheetseries.owasp.org/cheatsheets/AI_Agent_Security_Cheat_Sheet.html)
8. **Tests déterministes et diff** : tests ciblés, lint, analyse de sécurité, vérification de dépendances et revue humaine selon le risque. Un résumé agentique seul ne prouve pas la conformité.

## Limites, maturité et dépendances

**Maturité du concept.** Le mode Nxus est une pratique de workflow simple, compréhensible et immédiatement applicable. Sa maturité est celle d’un pattern de gouvernance, pas celle d’une spécification de sécurité ou d’un composant logiciel certifié. Son efficacité dépend de la qualité de l’exploration, de la granularité du plan, de la disponibilité d’un approbateur et de la capacité du harness à faire respecter le plan.

**Dépendance humaine.** La validation réduit les surprises mais crée une charge et un risque d’approbation superficielle. Les approbateurs doivent voir les permissions, les impacts et le diff, pas seulement un texte convaincant. Pour les tâches répétitives à faible impact, on peut autoriser une politique prévalidée ; pour les tâches à fort impact, conserver l’approbation nominative et éventuellement une seconde personne.

**Dépendance au modèle.** L’agent peut omettre un fichier, mal estimer un risque ou produire un plan conforme en apparence puis dériver. Un plan est une intention, non une preuve. Les contrôles d’exécution, le sandboxing et la comparaison plan/réalité sont donc obligatoires.

**Dépendance à l’outil.** Claude Code documente un plan mode où l’agent lit et explore sans modifier les sources jusqu’à approbation, puis propose des choix de sortie vers des modes d’exécution ; `PreToolUse` et les permissions peuvent contrôler les appels. [Claude Code — Common workflows](https://docs.anthropic.com/en/docs/claude-code/common-workflows) [Claude Code — Permission modes](https://docs.anthropic.com/en/docs/claude-code/permission-modes). Cursor documente un Plan Mode avec questions, recherche, plan révisable et bouton de construction. [Cursor — Plan Mode](https://cursor.com/docs/agent/plan-mode). Ces comportements sont des références publiques de produits précis et ne doivent pas être attribués à Nxus ni généralisés à tous les agents.

**Dépendance aux versions et configurations.** Les modes de permission, hooks, chemins de plans, règles et options peuvent évoluer. Le harness doit tester explicitement la version du runtime, vérifier les capacités au démarrage et échouer fermé si une garantie attendue n’est pas disponible.

## À adopter, optionnel ou à isoler

### À adopter par défaut

- Cycle explicite plan → approbation → exécution → vérification.
- Artefact humain `PLAN.md` doublé d’un manifeste structuré et versionné.
- Approbation liée à l’action exacte, courte, non rejouable et contrôlée hors modèle.
- Allowlist d’outils, chemins, commandes, réseau et budget ; deny par défaut.
- Exécution isolée, diff réel, tests et rapport plan/réalité.
- Journal d’audit avec redaction, corrélation de session et arrêt d’urgence.

### Optionnel selon risque et coût

- Questions de clarification avant le plan pour les exigences ambiguës.
- Revue LLM dédiée Quick/Deep inspirée d’Agent Review, en complément des outils déterministes. [Cursor — Agent Review](https://cursor.com/docs/agent/agent-review)
- Worktree par tâche et exécution parallèle, si le dépôt et le CI le permettent.
- Seconde approbation, signature ou step-up authentication pour actions critiques.
- Plan mode par défaut pour changements structurels ; exécution directe seulement pour tâches faibles, bornées et réversibles.

### À éviter ou à isoler

- Croire qu’un fichier `PLAN.md` ou une phrase « respecte le plan » constitue un contrôle de sécurité.
- Donner au modèle un shell illimité, des secrets, un accès production ou un réseau sortant sans médiation.
- Autoriser une approbation globale du type « oui pour tout » sans borne de durée, de ressource et de paramètres.
- Utiliser le propre résumé de l’agent comme unique preuve de ce qu’il a exécuté.
- Persister sans filtrage des sorties web, documents ou messages dans la mémoire de l’agent.
- Activer un mode bypass pour gagner du temps sur des tâches non isolées : la documentation Claude Code avertit que ce mode ne protège pas contre l’injection ni les actions involontaires. [Claude Code — Permission modes](https://docs.anthropic.com/en/docs/claude-code/permission-modes)

## Architecture cible minimale

`Task intake` crée une session et un périmètre. `Planner` lit uniquement les ressources autorisées et écrit `PLAN.md` plus le manifeste. `Policy engine` valide le schéma, le risque, les permissions et la présence d’un approbateur. `Approval service` émet un artefact court et lié à l’empreinte du manifeste. `Executor` exécute dans un worktree/sandbox avec middleware pré-outil. `Verifier` compare le diff, exécute les contrôles et produit le rapport. `Audit store` conserve les événements redigés. Toute erreur de politique, d’identité, de journal ou de validation doit interrompre l’action ; les actions externes doivent être idempotentes ou demander une confirmation renforcée.

Ce design reprend le bénéfice central de Nxus — **réduire les changements impulsifs et rendre la décision relisible** — tout en ajoutant les contrôles nécessaires pour qu’un harness agentique soit réellement sécurisé et exécutable.

## Références

- [NXUS — Mode réflexion avant action : l’agent raisonne avant de toucher au code](https://nxus.fr/cas-usage-agents-ia/mode-reflexion-avant-action-agent)
- [Anthropic — Common workflows](https://docs.anthropic.com/en/docs/claude-code/common-workflows)
- [Anthropic — Configure permissions](https://docs.anthropic.com/en/docs/claude-code/permissions)
- [Anthropic — Permission modes](https://docs.anthropic.com/en/docs/claude-code/permission-modes)
- [Anthropic — Hooks reference](https://docs.anthropic.com/en/docs/claude-code/hooks)
- [Cursor — Plan Mode](https://cursor.com/docs/agent/plan-mode)
- [Cursor — Agent Review](https://cursor.com/docs/agent/agent-review)
- [OWASP — AI Agent Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/AI_Agent_Security_Cheat_Sheet.html)

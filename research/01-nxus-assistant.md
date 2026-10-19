# Assistant public Nxus : analyse pour un harness agentique

## Constat principal

L’« Assistant NXUS » public est présenté comme un assistant conversationnel spécialisé dans l’offre Nxus : formations IA, financement, inscription et développement professionnel. La page publique le décrit comme « en ligne » et avertit explicitement que « les réponses peuvent contenir des erreurs » ([page officielle de l’assistant](https://nxus.fr/assistant)). Rien, sur cette page publique, n’atteste un accès à des outils, à un CRM, à une boîte mail, à un navigateur, à un terminal, à une mémoire persistante ou à une capacité d’action autonome. Il faut donc le traiter comme une **interface de question-réponse publique**, et non comme la preuve d’un agent généraliste ou d’un système d’orchestration.

L’objectif et le domaine annoncés sont utiles pour un harness : l’assistant doit rester borné à une base de connaissances Nxus et à des parcours d’information, avec une sortie prudente quand l’information n’est pas connue. En revanche, son implémentation interne, son modèle, son prompt système, ses données d’entraînement, sa politique de rétention, ses fournisseurs et ses endpoints ne sont pas attestés par les sources publiques consultées. Ce rapport ne prétend donc pas les connaître.

## Ce qui est publiquement observable

La page `/assistant` expose une page web rendue par l’application Nxus, avec un titre et une description indiquant le périmètre « formations NXUS, financement, inscription et développement professionnel » ([assistant](https://nxus.fr/assistant)). L’HTML public référence des ressources Next.js et les liens publics du site ; cette observation ne permet pas d’inférer le backend, le modèle ou un prompt privé. Aucun dépôt public Nxus ni documentation développeur officielle identifiant le code ou une API de cet assistant n’a été établi dans les sources consultées. Il faut donc isoler toute intégration supposée derrière un contrat explicite, plutôt que de reproduire des détails non documentés.

La maturité observable est **moyenne pour un point d’entrée éditorial et conversationnel**, mais **non démontrée pour un harness agentique exécutable**. Le produit est accessible sans que la page étudiée ne documente une configuration, un export de conversation, des appels d’outils, des métriques, une API publique, une politique de permissions ou une procédure de reprise. La formulation « les réponses peuvent contenir des erreurs » est un garde-fou utilisateur important, mais ne constitue ni une vérification factuelle ni une garantie de sécurité ([assistant](https://nxus.fr/assistant)).

## Mécanismes et étapes utiles à reprendre

Nxus décrit, dans son guide public, un agent comme un programme qui poursuit une mission, décompose le travail, agit dans des outils, vérifie son résultat et rend le travail terminé. Le guide résume la boucle par **analyse, plan, exécution, vérification**, et insiste sur le réglage du périmètre et de l’autonomie ([guide Agent IA](https://nxus.fr/agent-ia)). Pour le harness, cette boucle est une bonne structure, mais elle ne doit pas être attribuée à l’Assistant public lui-même : elle relève du guide général Nxus.

Le premier mécanisme à adopter est donc une séparation nette entre : (1) question utilisateur ; (2) récupération de contexte autorisé ; (3) réponse ; (4) vérification de couverture et de fraîcheur ; (5) escalade humaine si l’information touche un financement, une inscription, un engagement commercial ou une situation individuelle. Le glossaire Nxus recommande le RAG pour répondre à partir d’une base documentaire et réduire les erreurs, tout en rappelant la réalité des hallucinations ([glossaire IA](https://nxus.fr/glossaire-ia)). Un harness devrait exiger des passages récupérés et conserver leurs URL, titres, dates de mise à jour et scores, puis répondre « information non trouvée » plutôt que compléter de manière spéculative.

Le second mécanisme est le bornage de mission. Nxus conseille de commencer par une tâche fréquente, vérifiable et non critique, puis de tester et d’élargir progressivement l’autonomie ([guide Agent IA](https://nxus.fr/agent-ia)). Appliqué ici, le périmètre initial doit être : expliquer les formations et parcours documentés, orienter vers les pages officielles et recueillir une demande de contact sans décision automatique. Les questions hors périmètre doivent recevoir une réponse de limite, pas un transfert silencieux vers des outils non attestés.

Le troisième mécanisme, uniquement si un futur harness ajoute des actions, est l’interface d’outils à permissions explicites. Nxus présente MCP comme un protocole standard pour connecter un agent à des outils et sources externes, et le function calling comme le mécanisme qui déclenche ces fonctions ([glossaire IA](https://nxus.fr/glossaire-ia), [catégorie Intégrations & MCP](https://nxus.fr/cas-usage-agents-ia/categorie/integrations-mcp)). Cela justifie une couche d’adaptateurs, mais ne justifie pas de supposer que l’assistant public utilise MCP. Chaque outil doit avoir un schéma, une portée, une identité d’appelant, un budget, une liste d’objets accessibles et une journalisation.

## Garde-fous à adopter

**Lecture seule par défaut.** Le guide Nxus conseille de commencer par des accès en lecture seule, puis de faire valider les actions sensibles comme l’envoi, la suppression et le paiement ([guide Agent IA](https://nxus.fr/agent-ia)). Pour un assistant public, aucune écriture dans un système métier ne doit être activée implicitement. Une demande de contact doit produire un brouillon ou une collecte contrôlée, avec consentement et confirmation avant transmission.

**Validation humaine avant l’irréversible.** Nxus recommande une liste d’actions sensibles (`delete`, `send`, `pay`, `push`), un résumé lisible avant appel d’outil, une confirmation explicite et un timeout qui annule et journalise l’action ([garde-fous et validations](https://nxus.fr/cas-usage-agents-ia/garde-fous-validation-actions-sensibles-agent)). Ce mécanisme est à adopter si le périmètre évolue ; il est inutile et risqué de donner directement à l’Assistant public le pouvoir d’envoyer, supprimer ou payer.

**Isolation.** Pour les agents qui manipulent fichiers ou réseau, Nxus propose un conteneur non-root, un système de fichiers en lecture seule sauf montages explicites, un réseau limité aux domaines autorisés, un volume de travail dédié et une supervision externe ([sandbox](https://nxus.fr/cas-usage-agents-ia/sandboxer-agent-ia-isolation-securite)). Dans le harness, cela devient une frontière d’exécution : le moteur de dialogue ne doit pas avoir de secret ni d’accès réseau général ; les connecteurs tournent dans des workers séparés avec allowlist et limites de temps.

**Défense contre l’injection indirecte.** Nxus décrit le risque d’instructions malveillantes placées dans un email ou une page web, et propose de lire les données externes dans un contexte sans outils, de faire valider les actions par un contexte indépendant, de détecter les signaux d’exfiltration et de conserver un journal immuable ([protection contre l’injection](https://nxus.fr/cas-usage-agents-ia/protection-injection-prompt-agent-ia)). À adopter : données non fiables marquées comme données, jamais comme instructions ; lecture et action séparées ; validation déterministe des destinataires, URLs, fichiers et volumes ; blocage par défaut en cas de conflit.

**Secrets et minimisation.** Nxus recommande un coffre de secrets, une identité par agent ou machine, des droits scopés et une injection en mémoire au runtime plutôt que des fichiers `.env` en clair ([gestion des secrets](https://nxus.fr/cas-usage-agents-ia/chiffrement-gestion-secrets-agent-ia)). Pour le harness, les secrets ne doivent jamais entrer dans le prompt, les logs, les sorties utilisateur ou les traces d’évaluation. Les jetons doivent être dédiés, révocables et limités à l’action concernée.

**Traçabilité.** Dans son cas CRM, Nxus recommande de journaliser toutes les actions dans le CRM avec un tag de traçabilité ([assistant CRM](https://nxus.fr/cas-usage-agents-ia/assistant-crm-24-7)). Pour un harness complet, journaliser l’identifiant de session, l’utilisateur, la version du corpus, les documents récupérés, les outils proposés, les décisions de politique, les confirmations et le résultat. Les logs doivent être redacted, append-only et séparés des données de conversation.

## Limites, dépendances et points à isoler

La limite la plus importante est l’absence d’attestation publique sur le moteur réel. Le texte de la page ne permet pas de conclure quel LLM est utilisé, si un RAG est actif, si les conversations sont conservées, si un opérateur humain intervient, ni si les réponses sont évaluées. Ces points doivent être représentés comme **inconnus** dans la documentation du harness et vérifiés contractuellement ou par un test autorisé, jamais déduits de l’interface.

La qualité dépendra fortement de la qualité, de la fraîcheur et de la couverture des sources Nxus. Nxus le reconnaît dans son cas CRM : la valeur dépend de la qualité des données existantes ([assistant CRM](https://nxus.fr/cas-usage-agents-ia/assistant-crm-24-7)). Il faut donc versionner le corpus, vérifier les pages canonique et les tarifs/dates, détecter les documents contradictoires et distinguer information pédagogique, promesse commerciale et conseil individuel.

Les intégrations MCP, navigateur, email, CRM, computer use, voix, automatisations n8n, modèles locaux ou agents persistants sont des **options documentées dans le catalogue de cas d’usage Nxus**, pas des capacités prouvées de l’Assistant public ([Intégrations & MCP](https://nxus.fr/cas-usage-agents-ia/categorie/integrations-mcp), [Assistant perso](https://nxus.fr/cas-usage-agents-ia/categorie/assistant-perso)). Elles doivent être isolées derrière des modules facultatifs et désactivés par défaut. Ne pas réutiliser un nom d’agent, une mention de fournisseur ou un exemple de prompt comme preuve d’une dépendance technique dans `/assistant`.

Le modèle local est une option de confidentialité, pas une garantie globale. Nxus décrit Ollama et des modèles locaux pour éviter la sortie de données, mais recommande aussi de vérifier le réseau ([LLM local](https://nxus.fr/cas-usage-agents-ia/llm-local-donnees-clients-sensibles)). Même avec un modèle local, les connecteurs, journaux, navigateur et canaux de notification peuvent exfiltrer des données. La décision cloud/local doit donc porter sur tout le trajet de données.

## Recommandation pour le harness

**À adopter immédiatement :** un assistant en lecture seule, borné au corpus Nxus public ; RAG avec citations et dates ; refus explicite hors périmètre ; message d’incertitude ; tests adversariaux d’injection ; redaction des secrets et PII ; journal d’audit ; versionnement du corpus et des réponses ; supervision humaine pour toute demande d’inscription, financement ou engagement.

**À rendre optionnel :** MCP et connecteurs ; collecte de leads ; notifications Slack/Telegram ; automatisation n8n ; CRM ; modèles locaux ; voix ; mémoire persistante. Chaque module doit être installé séparément, avec permissions et politique d’expiration propres.

**À éviter ou isoler :** exécution arbitraire de code ; accès général au navigateur ou au filesystem ; envoi d’emails, suppression, paiement ou modification CRM sans confirmation ; partage d’un secret entre agents ; confiance dans le texte récupéré comme instruction ; prétention à reproduire un prompt ou un backend privé ; collecte de données sensibles sans finalité, consentement et politique de rétention documentés.

Le bon niveau de confiance est donc : **Assistant public Nxus = démonstrateur/point d’accès conversationnel spécialisé, utile comme spécification de périmètre et de prudence ; pas une preuve publique d’agent autonome ni une implémentation à cloner**. Le harness doit encapsuler cette interface et ses éventuels changements, avec un contrat d’observabilité et de sécurité indépendant de Nxus.

## Références

- [Assistant IA | NXUS](https://nxus.fr/assistant)
- [Agent IA : définition, exemples concrets et comment démarrer](https://nxus.fr/agent-ia)
- [Glossaire de l’intelligence artificielle](https://nxus.fr/glossaire-ia)
- [Cas d’usage des agents IA comme assistant personnel](https://nxus.fr/cas-usage-agents-ia/categorie/assistant-perso)
- [Assistant 24/7 branché sur ton CRM](https://nxus.fr/cas-usage-agents-ia/assistant-crm-24-7)
- [Cas d’usage : intégrations et MCP](https://nxus.fr/cas-usage-agents-ia/categorie/integrations-mcp)
- [Sandboxer son agent IA](https://nxus.fr/cas-usage-agents-ia/sandboxer-agent-ia-isolation-securite)
- [Protéger son agent contre les injections de prompt](https://nxus.fr/cas-usage-agents-ia/protection-injection-prompt-agent-ia)
- [Garde-fous et validations avant toute action sensible](https://nxus.fr/cas-usage-agents-ia/garde-fous-validation-actions-sensibles-agent)
- [Chiffrer et gérer les secrets accessibles à ton agent](https://nxus.fr/cas-usage-agents-ia/chiffrement-gestion-secrets-agent-ia)
- [Faire tourner un LLM en local pour traiter des données clients sensibles](https://nxus.fr/cas-usage-agents-ia/llm-local-donnees-clients-sensibles)

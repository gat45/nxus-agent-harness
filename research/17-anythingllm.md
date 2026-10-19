# AnythingLLM comme espace de travail RAG et agents

## Positionnement réel

AnythingLLM est une application tout-en-un qui combine chat avec documents, RAG et agents, avec une orientation local-first et des déploiements Desktop ou Docker. La documentation officielle le décrit comme une application « all-in-one » pour RAG et AI Agents, tandis que le dépôt public annonce le support des LLM locaux ou cloud, des bases vectorielles, des pipelines documentaires et du multi-utilisateur ([documentation produit](https://docs.anythingllm.com/introduction), [README du dépôt](https://github.com/Mintplex-Labs/anything-llm)). Ce n’est donc pas, à lui seul, un harness générique d’orchestration : c’est une application de workspace qui fournit une interface, un stockage documentaire, une chaîne RAG et une couche d’outils agentiques.

Le dépôt est public, sous licence MIT, et sépare notamment `frontend`, `server`, `collector`, `docker`, `embed` et `browser-extension`. Le serveur Node/Express gère les interactions, le vector store et les appels LLM ; le collector traite et parse les documents ([README, Technical Overview](https://github.com/Mintplex-Labs/anything-llm)). Cette séparation est utile pour comprendre les interfaces à intégrer, mais ne doit pas être interprétée comme une garantie de sécurité ou de stabilité d’API.

## Mécanismes utiles à reprendre

### Workspace et portée des données

Le workspace est l’unité fonctionnelle centrale : il rassemble conversations, configuration LLM/agent et documents accessibles. Un document simplement attaché dans un chat est limité au workspace et au thread ; un document embarqué devient disponible dans tous les threads du workspace et, en mode multi-utilisateur, pour tous les utilisateurs autorisés à ce workspace ([Using Documents in AnythingLLM](https://docs.anythingllm.com/chatting-with-documents/introduction)). Le harness doit donc conserver une notion explicite de **tenant/workspace**, de thread, d’utilisateur et de politique d’accès, plutôt que de traiter le corpus comme une mémoire globale.

### Pipeline RAG

L’embedding/RAG découpe les documents en morceaux, calcule des représentations vectorielles et ne récupère qu’un petit nombre de passages sémantiquement pertinents. Cela réduit le contexte transmis au modèle, mais peut omettre une information présente ailleurs dans le document ([Using Documents in AnythingLLM](https://docs.anythingllm.com/chatting-with-documents/introduction)). Le produit expose au niveau workspace le nombre maximal de snippets, le seuil de similarité et, avec LanceDB, un mode de recherche avec reranking. La documentation recommande généralement 4–6 snippets pour éviter le dépassement de contexte ; le reranking est plus lent et est annoncé comme ajoutant environ 100–500 ms selon l’instance ([même source](https://docs.anythingllm.com/chatting-with-documents/introduction)).

À adopter dans le harness : ingestion versionnée, métadonnées de provenance, séparation entre document source et chunks, seuils configurables, reranking optionnel et tests de rappel/précision. À ne pas copier aveuglément : un seuil numérique fixe (par exemple 20 %) n’est pas une mesure universelle de pertinence ; la documentation précise que le score dépend du modèle d’embedding, de la densité des vecteurs et de la requête ([même source](https://docs.anythingllm.com/chatting-with-documents/introduction)).

Le produit permet aussi le « pinning » : insertion plein texte d’un document déjà embarqué, si le contexte le permet. C’est utile pour un petit document critique, mais doit rester une exception contrôlée car cela augmente coût, latence et risque de dépassement de contexte ([même source](https://docs.anythingllm.com/chatting-with-documents/introduction)).

### Agents et outils

Dans la documentation, un agent est essentiellement un LLM muni d’outils simples. Il est appelé dans un workspace via `@agent`, puis la session se termine avec `/exit` ; selon le fournisseur, le mode agentique peut aussi être activé automatiquement ([AI Agents](https://docs.anythingllm.com/features/ai-agents), [AI Agent Usage](https://docs.anythingllm.com/agent/usage/overview)). Les outils documentés comprennent recherche RAG, navigation et scraping web, liste et résumé de documents, sauvegarde de fichiers, génération de graphiques, SQL Agent, File System Agent et création de tâches planifiées ([AI Agent Usage](https://docs.anythingllm.com/agent/usage/overview)).

Le RAG Search permet à l’agent d’interroger le corpus déjà embarqué du workspace. La documentation indique que l’agent peut aussi enregistrer une synthèse dans sa propre mémoire sous forme de document virtuel non administrable directement ([RAG Search](https://docs.anythingllm.com/agent/usage/rag-search)). Pour un harness, il faut distinguer trois états : connaissance source récupérée, mémoire dérivée par l’agent et conversation. Toute mémoire dérivée doit être traçable, réversible, soumise à une politique de rétention et marquée comme une assertion générée, non comme une source primaire.

Les compétences se configurent globalement dans `Settings > Agent Skills`, et peuvent être activées ou désactivées dans l’interface du chat. Le modèle d’agent peut être choisi par workspace ([Agent Setup](https://docs.anythingllm.com/agent/setup)). Le mécanisme d’Intelligent Tool Selection ne transmet au contexte que les outils jugés utiles, au lieu d’injecter toutes les définitions à chaque requête ; la documentation revendique une réduction pouvant atteindre 80 %, mais cela reste une affirmation du produit à valider par benchmark ([Agent Setup](https://docs.anythingllm.com/agent/setup)). Pour le harness, cette sélection peut être adoptée comme optimisation, jamais comme contrôle de sécurité : l’autorisation doit être décidée avant l’appel et vérifiée par un exécuteur indépendant.

### Interfaces et intégration

Le dépôt publie une spécification OpenAPI 3.0 pour la Developer API. Elle décrit un serveur `/api`, une vérification de jeton via `/v1/auth`, des routes d’administration et des opérations de workspace/embed ; la sécurité globale est déclarée en Bearer token ([OpenAPI public](https://raw.githubusercontent.com/Mintplex-Labs/anything-llm/master/server/swagger/openapi.json)). Cette API est une interface utile pour piloter une instance, provisionner des utilisateurs, intégrer un chat ou synchroniser des documents. Le harness doit toutefois encapsuler cette API derrière son propre adaptateur, épingler une version, vérifier les réponses et ne pas supposer que toute capacité UI est disponible via API. Un Developer API key est documenté par la politique de sécurité comme un identifiant système donnant un accès complet à `/v1/*`, équivalent à un accès administrateur ([SECURITY.md](https://github.com/Mintplex-Labs/anything-llm/blob/master/SECURITY.md)).

## Garde-fous et limites

### Authentification et isolation

Le mode Docker fournit un mode mono-utilisateur protégé par mot de passe et un mode multi-utilisateur avec rôles Admin, Manager et Default. Le rôle Default ne peut discuter que dans les workspaces auxquels il a été explicitement ajouté ; l’administrateur possède les privilèges système les plus élevés ([Security and Access](https://docs.useanything.com/features/security-and-access)). Le mode multi-utilisateur ne peut pas être réverti vers le mode mono-utilisateur selon la documentation ([même source](https://docs.useanything.com/features/security-and-access)). Pour un harness exposé, adopter le multi-utilisateur, le moindre privilège et une ACL de workspace. Éviter le déploiement sans authentification : la politique officielle reconnaît qu’une instance sans mot de passe est accessible à quiconque connaît l’URL ([SECURITY.md](https://github.com/Mintplex-Labs/anything-llm/blob/master/SECURITY.md)).

### Outils à haut risque

La politique de sécurité précise que le scraping vers des hôtes internes et les URL de services administrativement configurées sont des fonctionnalités intentionnelles, notamment en VPC ; elle indique aussi que SQL Agent et les outils filesystem sont désactivés par défaut et nécessitent une activation/configuration administrateur ([SECURITY.md](https://github.com/Mintplex-Labs/anything-llm/blob/master/SECURITY.md)). C’est un point critique pour le harness : le contrôle ne doit pas reposer sur des filtres de prompt ou des regex. Il faut exécuter les outils avec comptes SQL en lecture seule, chemins filesystem explicitement montés et bornés, egress réseau allowlisté, timeouts, quotas, journal d’audit et approbation humaine pour les écritures. La capacité SSRF/document collector doit être isolée dans un réseau de collecte dédié ; elle ne doit jamais être exposée comme une permission implicite d’un agent généraliste.

La même politique avertit que `open-computer` est à un état primitif et n’est pas prêt pour la production ([SECURITY.md](https://github.com/Mintplex-Labs/anything-llm/blob/master/SECURITY.md)). Il faut donc l’éviter dans un harness de production ou le cantonner à un bac à sable jetable.

### Confidentialité, effacement et sorties réseau

Le produit collecte une télémétrie annoncée comme anonyme, désactivable dans les réglages. Le README précise que les événements portent sur le type d’installation, ajout/suppression de document, type de vector store, modèle utilisé et envoi de chat, sans contenu de documents ou de chats ; même télémétrie désactivée, des intégrations externes, un CDN de modèles ou GitHub peuvent générer des connexions sortantes ([README, Telemetry & Privacy](https://github.com/Mintplex-Labs/anything-llm), [Privacy & Data Handling](https://docs.anythingllm.com/features/privacy-and-data-handling)). En environnement sensible, désactiver la télémétrie, bloquer l’egress par défaut et documenter chaque fournisseur LLM/embedder/vector DB.

L’effacement est subtil : retirer un document d’un workspace supprime ses vecteurs de ce workspace mais conserve la source parsée et les embeddings dans la bibliothèque ; supprimer le document depuis `My Documents` efface la source, le cache et les références dans tous les workspaces ([Privacy & Data Handling](https://docs.anythingllm.com/features/privacy-and-data-handling)). Le harness doit implémenter un workflow d’effacement complet, avec inventaire des copies, caches, index, logs et mémoires dérivées ; une simple suppression d’association ne satisfait pas une demande d’effacement.

Le self-hosted peut être local-first et fonctionner en air-gap avec des fournisseurs locaux, mais les intégrations externes transmettent les données aux prestataires concernés ; la responsabilité de firewall, TLS et contrôle d’accès revient à l’opérateur ([TERMS_SELF_HOSTED.md](https://github.com/Mintplex-Labs/anything-llm/blob/master/TERMS_SELF_HOSTED.md)). « Local » ne signifie donc pas automatiquement « aucune sortie ».

## Maturité, dépendances et implications

La maturité est suffisante pour servir de composant applicatif open source : dépôt MIT actif, documentation structurée, Docker/Desktop, API OpenAPI, plusieurs fournisseurs LLM/embedder/vector DB et une chaîne document/agent déjà opérationnelle ([README](https://github.com/Mintplex-Labs/anything-llm), [OpenAPI public](https://raw.githubusercontent.com/Mintplex-Labs/anything-llm/master/server/swagger/openapi.json)). En revanche, le produit évolue rapidement : la documentation affichait la version 1.17.0 au moment de la consultation ([documentation](https://docs.anythingllm.com/introduction)). Le harness doit épingler une release, tester les migrations, vérifier les contrats API et surveiller les avis de sécurité. Ne pas fonder une garantie de sécurité sur le nombre de commits, la mention « production-ready » du README ou l’existence d’une interface graphique.

Les dépendances fonctionnelles comprennent un LLM (local ou distant), un modèle d’embedding, un parseur/collector, un vector store et, selon les outils, des moteurs de recherche web, SQL, filesystem ou planification. Le vector store est configuré au niveau système et non atomiquement par workspace ; changer de base ne migre pas automatiquement les embeddings et impose de supprimer/ré-embarquer les documents ([Vector Databases](https://docs.anythingllm.com/setup/vector-database-configuration/overview)). Pour le harness, ce point impose un choix d’index, un plan de migration et des tests de compatibilité avant mise en production.

## Décision pour le harness

**À adopter :** le modèle workspace/tenant avec ACL explicite ; ingestion et retrieval séparés ; provenance de chaque chunk ; configuration RAG par workspace ; API OpenAPI derrière un adaptateur versionné ; activation explicite des compétences ; exécution outillée avec least privilege, audit, quotas, timeouts et approbation ; désactivation télémétrie/egress par défaut ; procédures d’effacement et de réindexation testées.

**Optionnel :** reranking, document pinning sur petits documents critiques, Intelligent Tool Selection, mémoire agentique, navigation web, SQL ou filesystem. Chacune de ces options doit être activée par politique, mesurée et isolée selon son risque.

**À éviter ou isoler :** instance sans authentification ; clé Developer API dans un client ou un agent non fiable ; SQL en écriture ; filesystem large ou monté sur l’hôte ; scraping vers des réseaux internes depuis le plan agent ; mémoire virtuelle non traçable ; `open-computer` en production ; dépendance à une API non versionnée ou à des prompts système supposés. AnythingLLM peut fournir le socle RAG/workspace et une couche d’outils, mais le harness doit rester l’autorité de sécurité, de gouvernance, d’observabilité et de décision d’action.

## Références

Les URL exactes sont placées près de chaque affirmation factuelle ; les principales sont :

- [AnythingLLM — Introduction](https://docs.anythingllm.com/introduction)
- [AnythingLLM — Using Documents](https://docs.anythingllm.com/chatting-with-documents/introduction)
- [AnythingLLM — AI Agents](https://docs.anythingllm.com/features/ai-agents)
- [AnythingLLM — Agent Usage](https://docs.anythingllm.com/agent/usage/overview)
- [AnythingLLM — Agent Setup](https://docs.anythingllm.com/agent/setup)
- [AnythingLLM — Security and Access](https://docs.useanything.com/features/security-and-access)
- [AnythingLLM — Privacy & Data Handling](https://docs.anythingllm.com/features/privacy-and-data-handling)
- [AnythingLLM — Vector Databases](https://docs.anythingllm.com/setup/vector-database-configuration/overview)
- [AnythingLLM — GitHub README](https://github.com/Mintplex-Labs/anything-llm)
- [AnythingLLM — SECURITY.md](https://github.com/Mintplex-Labs/anything-llm/blob/master/SECURITY.md)
- [AnythingLLM — TERMS_SELF_HOSTED.md](https://github.com/Mintplex-Labs/anything-llm/blob/master/TERMS_SELF_HOSTED.md)
- [AnythingLLM — OpenAPI](https://raw.githubusercontent.com/Mintplex-Labs/anything-llm/master/server/swagger/openapi.json)

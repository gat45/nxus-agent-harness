# Model Context Protocol (MCP) pour la connexion aux outils

## Conclusion opérationnelle

MCP est un **protocole ouvert d’échange de contexte et d’appel de capacités** entre une application hôte, des clients MCP embarqués dans cette application et des serveurs MCP. Il standardise le transport des messages, la découverte et l’usage de ressources, prompts et outils ; il **ne définit ni l’orchestration de l’agent, ni le choix du modèle, ni la politique de décision** ([spécification MCP](https://modelcontextprotocol.io/specification/2026-07-28), [architecture](https://modelcontextprotocol.io/docs/2026-07-28/learn/architecture)). Pour un harness, MCP est donc une **couche d’adaptation et de contrôle des capacités externes**, pas un agent complet et pas une frontière de sécurité suffisante à elle seule.

La recommandation est d’adopter MCP derrière un broker/policy gateway du harness : inventaire signé ou approuvé des serveurs, isolation par serveur, filtrage des primitives, validation indépendante des schémas et des résultats, consentement humain pour les opérations sensibles, quotas/timeout/audit et gestion stricte des identités et tokens. Le transport STDIO est le choix par défaut pour des serveurs locaux de confiance limitée mais sandboxés ; Streamable HTTP est à réserver aux serveurs distants avec authentification et validation réseau robustes. Les extensions, prompts distants, élicitation et tâches longues doivent rester opt-in et isolés tant que leur nécessité n’est pas démontrée.

## Rôle réel et modèle d’architecture

MCP sépare deux couches. La **couche données** utilise des messages JSON-RPC et porte la découverte, les capacités, les primitives et les notifications. La **couche transport** définit l’établissement de la connexion, le framing, l’acheminement et l’authentification ([architecture officielle](https://modelcontextprotocol.io/docs/2026-07-28/learn/architecture)).

Les rôles sont distincts : l’**hôte** est l’application IA qui coordonne plusieurs connexions ; un **client MCP** est le connecteur dédié à un serveur ; le **serveur MCP** fournit contexte et capacités. En pratique, le harness doit créer une identité et un canal séparés par serveur, plutôt qu’un canal global qui agrège toutes les permissions ([architecture officielle](https://modelcontextprotocol.io/docs/2026-07-28/learn/architecture)). Un serveur peut être local ou distant ; « serveur » décrit sa fonction, pas son emplacement.

Les trois primitives serveur sont :

- **Tools** : fonctions exécutables, par exemple API, base de données ou opérations fichiers ; elles sont model-controlled et peuvent être découvertes puis invoquées ([Tools](https://modelcontextprotocol.io/specification/2026-07-28/server/tools)).
- **Resources** : données adressées par URI, par exemple fichiers, schémas ou réponses API ; elles sont application-driven et l’hôte décide comment les injecter dans le contexte ([Resources](https://modelcontextprotocol.io/specification/2026-07-28/server/resources)).
- **Prompts** : modèles de messages et instructions structurées ; ils sont user-controlled dans le modèle recommandé, c’est-à-dire sélectionnés explicitement par l’utilisateur, même si leur contenu est fourni par le serveur ([Prompts](https://modelcontextprotocol.io/specification/2026-07-28/server/prompts)).

Cette distinction est importante pour le harness : un outil peut produire un effet externe ; une ressource peut exfiltrer des données ou injecter des instructions ; un prompt distant peut influencer le comportement du modèle. Ils doivent donc avoir des politiques différentes, même s’ils transitent par le même protocole.

## Mécanismes et séquence utile

### 1. Sélection et attestation du serveur

Le harness doit d’abord sélectionner un serveur selon une allowlist, son origine, son transport, sa version, ses dépendances et sa politique de permissions. Le dépôt officiel de spécification contient la spécification, le schéma TypeScript et le schéma JSON ([dépôt officiel](https://github.com/modelcontextprotocol/modelcontextprotocol)). Le dépôt de serveurs indique explicitement que ses implémentations sont des **références pédagogiques et non des solutions prêtes pour la production** ([serveurs de référence](https://github.com/modelcontextprotocol/servers)). Il ne faut donc pas traiter la présence dans ce dépôt comme une certification de confiance.

### 2. Connexion et transport

Les transports standard sont :

- **STDIO** : messages JSON-RPC délimités par lignes sur les entrées/sorties d’un sous-processus lancé par le client ; performant et sans réseau, mais le harness doit gérer le cycle de vie, l’environnement, les secrets, le sandboxing et les limites de ressources ([transports](https://modelcontextprotocol.io/specification/2026-07-28/basic/transports)).
- **Streamable HTTP** : chaque message est un POST vers un endpoint MCP ; une réponse JSON ou un flux SSE lié à la requête peut être utilisé ([transports](https://modelcontextprotocol.io/specification/2026-07-28/basic/transports)). Il convient aux serveurs distants mais ajoute DNS, TLS, proxy, authentification, SSRF et exposition réseau.

Les sémantiques JSON-RPC sont communes aux transports. Les transports personnalisés sont permis, mais doivent conserver le format JSON-RPC, les patterns de messages et les métadonnées par requête ([transports](https://modelcontextprotocol.io/specification/2026-07-28/basic/transports)). Pour un premier harness, il faut éviter un transport personnalisé.

### 3. Version, identité et capacités

Dans la révision documentée `2026-07-28`, chaque requête transporte la version, l’identité client et les capacités dans `_meta`; il n’y a pas de handshake de négociation obligatoire. Le serveur doit implémenter `server/discover`; le client peut l’appeler avant toute autre requête pour connaître les versions et capacités ([versioning et compatibilité](https://modelcontextprotocol.io/specification/2026-07-28/basic/lifecycle)). Le harness doit gérer explicitement les erreurs de version et, si une compatibilité avec des serveurs plus anciens est nécessaire, isoler le mode dual-era (`initialize` legacy) plutôt que mélanger les sémantiques.

Les extensions sont opt-in et doivent être annoncées dans les capacités ; si un seul côté les supporte, il doit revenir au comportement de base ou rejeter la requête ([spécification](https://modelcontextprotocol.io/specification/2026-07-28)). Le harness doit journaliser la version et les extensions effectivement négociées.

### 4. Découverte et cache

Le client appelle `tools/list`, `resources/list`/`resources/templates/list` et `prompts/list`. Les listes peuvent être paginées, mises en cache et changer avec le temps. Les serveurs peuvent notifier les changements s’ils annoncent `listChanged` ([Tools](https://modelcontextprotocol.io/specification/2026-07-28/server/tools), [Resources](https://modelcontextprotocol.io/specification/2026-07-28/server/resources), [Prompts](https://modelcontextprotocol.io/specification/2026-07-28/server/prompts)).

Le harness doit conserver un catalogue par serveur et par identité/portée d’autorisation, invalider le cache sur notification ou expiration et imposer une taille maximale. Les noms, descriptions, annotations, icônes et schémas sont des **métadonnées non fiables** ; la spécification des outils exige notamment de considérer les annotations comme non fiables sauf serveur de confiance ([Tools](https://modelcontextprotocol.io/specification/2026-07-28/server/tools)). Ils ne doivent jamais devenir une permission implicite.

### 5. Validation et exécution d’un outil

Une définition d’outil comprend un nom, une description, un `inputSchema` JSON Schema et éventuellement un `outputSchema` et des annotations. L’appel utilise `tools/call` et retourne des blocs de contenu avec `isError`; les erreurs de protocole doivent être distinguées des erreurs d’exécution récupérables ([Tools](https://modelcontextprotocol.io/specification/2026-07-28/server/tools)).

Le pipeline recommandé est : (1) sélectionner un outil déjà autorisé ; (2) revalider le nom et les arguments contre le schéma côté harness ; (3) classer l’impact et présenter les paramètres à l’utilisateur si requis ; (4) appliquer politique, quota, timeout et budget ; (5) appeler ; (6) valider, borner et nettoyer le résultat ; (7) ne transmettre au modèle que le résultat autorisé et marqué comme données non fiables ; (8) journaliser l’appel et la décision. Le serveur doit lui-même valider ses entrées, appliquer l’accès, limiter le débit et nettoyer les sorties ; le client devrait aussi valider les résultats, limiter le temps et auditer ([sécurité des Tools](https://modelcontextprotocol.io/specification/2026-07-28/server/tools)).

### 6. Accès aux ressources

`resources/read` lit une URI ; les templates utilisent des URI templates. La spécification exige de valider les URI, de contrôler les permissions et de prévenir la traversée de répertoires pour `file://` ([Resources](https://modelcontextprotocol.io/specification/2026-07-28/server/resources)). Le harness doit traiter toute URI comme une entrée hostile : allowlist de schémas et d’hôtes, normalisation prudente, limites de taille et de profondeur, détection de contenu binaire, redaction de secrets et protection contre prompt injection avant remise au modèle.

Les ressources `https://` peuvent parfois être récupérées directement par le client. Cette possibilité doit être désactivée par défaut dans un harness qui veut centraliser l’egress, sinon elle contourne les contrôles du serveur MCP ([Resources](https://modelcontextprotocol.io/specification/2026-07-28/server/resources)).

### 7. Prompts et entrées utilisateur

`prompts/get` renvoie des messages texte, images, audio ou ressources embarquées. Les arguments et sorties doivent être validés contre injection et accès non autorisé ([Prompts](https://modelcontextprotocol.io/specification/2026-07-28/server/prompts)). Un harness sécurisé doit afficher l’origine du prompt, le traiter comme contenu non fiable et empêcher qu’un prompt de serveur ne remplace silencieusement les politiques système du harness. L’usage automatique de prompts distants doit être isolé derrière confirmation ou configuration explicite.

### 8. Autorisation HTTP

L’autorisation MCP est optionnelle, mais la documentation la recommande fortement pour données utilisateur, opérations administratives, audit et environnements d’entreprise ([guide d’autorisation](https://modelcontextprotocol.io/docs/2026-07-28/tutorials/security/authorization)). Pour un serveur HTTP protégé, le flux documenté passe par une réponse `401`, le Protected Resource Metadata, la découverte de l’Authorization Server, une inscription préenregistrée ou dynamique, OAuth Authorization Code avec PKCE puis des requêtes `Authorization: Bearer` ([guide d’autorisation](https://modelcontextprotocol.io/docs/2026-07-28/tutorials/security/authorization)).

Les exigences normatives importantes sont : inclure le paramètre OAuth `resource` dans demande d’autorisation et demande de token, utiliser l’URI canonique du serveur, envoyer le token uniquement dans l’en-tête, valider audience et expiration, et ne jamais accepter ou relayer un token destiné à une autre ressource ([autorisation MCP](https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization)). Le harness doit stocker les tokens dans un coffre, les associer au serveur et à l’audience, éviter les logs de secrets et refuser le « token passthrough » générique.

## Garde-fous obligatoires pour le harness

1. **Consentement et humain dans la boucle.** MCP recommande qu’un humain puisse refuser une invocation et que l’interface montre les outils, leurs paramètres et les indicateurs d’exécution ([Tools](https://modelcontextprotocol.io/specification/2026-07-28/server/tools)). La politique doit distinguer lecture, écriture, suppression, exfiltration, action financière, action irréversible et opérations d’administration.
2. **Confiance minimale.** Descriptions, annotations, prompts, ressources et résultats sont des entrées externes. Ils ne peuvent pas modifier la politique, accorder une permission ou déclencher un autre outil sans repasser par le policy engine.
3. **Isolation locale.** Chaque serveur STDIO doit tourner avec utilisateur, répertoire, environnement, réseau et limites CPU/mémoire/processus dédiés. Les secrets doivent être injectés au strict nécessaire ; ne pas transmettre l’environnement complet.
4. **Défense réseau.** Pour HTTP : TLS vérifié, allowlist d’origines et d’hôtes, blocage des IP privées/link-local et des redirections dangereuses, validation stricte de `Origin`, limites de taille/durée et protection DNS rebinding/SSRF. La documentation de sécurité MCP décrit notamment le risque de confused deputy pour les proxies OAuth et exige un consentement par client avant de lancer le flux tiers ([Security Best Practices](https://modelcontextprotocol.io/docs/2026-07-28/tutorials/security/security_best_practices)).
5. **OAuth correct.** PKCE, état anti-CSRF, validation de l’émetteur `iss` quand annoncé, audience/ressource exacte, redirect URI exacte, séparation des tokens et rotation/expiration. Un proxy doit associer le consentement à chaque `client_id`, montrer scopes et redirect URI et empêcher le clickjacking ([Security Best Practices](https://modelcontextprotocol.io/docs/2026-07-28/tutorials/security/security_best_practices)).
6. **Validation des données.** JSON Schema indépendant, résolution `$ref` contrôlée, allowlist des MIME types et schémas URI, limites de sortie et redaction. Les résultats d’erreur d’outil peuvent être fournis au modèle pour permettre l’auto-correction, mais les erreurs doivent rester bornées et ne jamais divulguer secrets ou traces internes ([Tools](https://modelcontextprotocol.io/specification/2026-07-28/server/tools)).
7. **Observabilité et réversibilité.** Journaliser serveur, version, transport, outil/URI, hash ou résumé des arguments, décision de politique, identité, latence, résultat et erreur ; exclure secrets et données sensibles. Prévoir kill switch par serveur, outil, utilisateur et session.
8. **Résilience.** Timeout par appel, annulation, circuit breaker, quota de volume/coût, pagination obligatoire, limites de concurrence et backpressure. Les opérations longues/extensions Tasks doivent utiliser des handles et une politique de rétention, sans bloquer la boucle principale.

## Maturité, dépendances et limites

Le protocole est suffisamment structuré pour une intégration interopérable : spécification normative, schéma TypeScript et JSON Schema publics, SDK officiels et serveurs de référence. La documentation classe les SDK : TypeScript, Python, C#, Go, Rust et Ruby en Tier 1 ; Java en Tier 2 ; Swift, PHP et Kotlin en Tier 3 ([SDK officiels](https://modelcontextprotocol.io/docs/2026-07-28/sdk)). Le choix le plus prudent pour le cœur du harness est donc un SDK Tier 1, avec tests de conformité et pinning de version.

La maturité n’est cependant pas celle d’une plateforme de sécurité complète. Le dépôt de serveurs avertit que ses serveurs sont des références et non des implémentations de production ([serveurs de référence](https://github.com/modelcontextprotocol/servers)). Le protocole ne peut pas imposer au niveau protocolaire le consentement, l’interface utilisateur, le confinement du processus, la sûreté du code métier, la confidentialité des données ni la résistance aux prompt injections ; la spécification demande aux implémentations de construire ces contrôles ([spécification MCP](https://modelcontextprotocol.io/specification/2026-07-28)).

La compatibilité temporelle est une dépendance réelle : la documentation décrit une ère moderne stateless et des clients/serveurs legacy à handshake `initialize`, avec mécanismes de repli spécifiques à chaque transport ([versioning](https://modelcontextprotocol.io/specification/2026-07-28/basic/lifecycle)). Un harness devra tester les versions supportées plutôt que supposer que toute implémentation MCP est interchangeable.

Les extensions MCP Apps, Tasks et autres capacités spécialisées sont optionnelles et négociées explicitement ([spécification](https://modelcontextprotocol.io/specification/2026-07-28)). Elles augmentent la surface d’attaque et le coût de test. Il faut les isoler, les désactiver par défaut et exiger une justification fonctionnelle.

## Décisions pour le harness

### À adopter

- MCP comme **adaptateur de capacités externes**, avec un MCP client/broker par serveur.
- JSON-RPC, `server/discover`, capacités, versions par requête et allowlists explicites.
- STDIO sandboxé pour processus locaux ; Streamable HTTP uniquement via egress contrôlé et OAuth/audience stricts.
- Découverte paginée et cache par serveur/identité, avec invalidation sur changement.
- Validation indépendante des outils, arguments, URI, sorties et erreurs.
- Consentement humain et affichage des paramètres avant toute opération sensible.
- Audit, quotas, timeout, annulation, limites de taille et kill switch.
- SDK Tier 1 épinglé, schémas officiels et tests d’interopérabilité avec au moins un serveur local et un serveur HTTP de test.

### Optionnel, à activer par besoin

- Resources, si le harness possède un pipeline de classification/redaction et de lutte contre l’injection.
- Prompts, uniquement comme commandes explicitement sélectionnées ; jamais comme politique système.
- OAuth/DCR pour serveurs distants ; préenregistrement préféré quand le parc est contrôlé.
- Subscriptions, elicitation et tâches longues après mise en place d’un modèle de session et d’audit.
- Extensions UI/Apps ou transports personnalisés, seulement avec revue de menace et tests dédiés.

### À éviter ou isoler

- Exécuter sans sandbox un serveur téléchargé via `npx`, `uvx` ou équivalent ; les exemples publics ne sont pas une garantie de production ([serveurs de référence](https://github.com/modelcontextprotocol/servers)).
- Donner à un modèle un accès automatique à tous les outils découverts.
- Faire confiance aux descriptions, annotations, prompts ou sorties pour décider des permissions.
- Relayer des tokens reçus pour un autre serveur, mettre des tokens dans des URL ou partager un token entre serveurs.
- Autoriser les URI arbitraires, `file://` hors racine, fetch HTTP direct non contrôlé ou redirections vers réseaux privés.
- Activer par défaut DCR, prompts distants, élicitation ou extensions UI.
- Construire l’agent, sa mémoire, son planificateur ou sa politique de sécurité « dans MCP » : ces responsabilités restent dans le harness.

## Architecture cible minimale

`LLM/orchestrateur → policy engine → MCP broker → [client STDIO sandboxé | client Streamable HTTP egress contrôlé] → serveur MCP`.

Le broker conserve pour chaque serveur : origine et hash/version, transport, capacités, primitives autorisées, schémas approuvés, scopes OAuth/audience, quotas, règles de consentement, statut de santé et journaux. Le modèle ne reçoit qu’un sous-ensemble filtré des outils et des schémas ; un appel passe toujours par le policy engine. Les résultats entrants sont étiquetés comme non fiables, bornés, validés et séparés du canal de contrôle. Les ressources et prompts ne sont injectés qu’après décision de contexte ; aucun contenu serveur ne peut écrire directement la politique ou le prompt système du harness.

Cette architecture respecte le rôle attesté de MCP tout en ajoutant les contrôles qu’il laisse nécessairement à l’hôte : MCP standardise la connexion et les artefacts d’interface, alors que le harness doit fournir l’identité, la confiance, l’isolation, le consentement, l’audit et la gouvernance d’exécution.

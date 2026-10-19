# Crawlee pour le crawling et l’automatisation web

## Rôle réel

Crawlee est une bibliothèque open source de scraping, crawling et automatisation de navigateur pour JavaScript/TypeScript et Python. Son rôle est celui d’un **moteur d’exécution de collectes web** : il orchestre les requêtes, les handlers utilisateur, les retries, la concurrence, les sessions et les stockages. Ce n’est ni un agent généraliste, ni un navigateur isolé, ni une politique de conformité. La page officielle la présente comme une bibliothèque qui prend en charge le blocage, le crawling, les proxies et les navigateurs ([crawlee.dev/js](https://crawlee.dev/js)).

Pour un harness agentique, Crawlee est donc une bonne couche d’outil bornée : l’agent propose une mission et des URLs autorisées ; un exécuteur Crawlee réalise la navigation/extraction ; le harness valide les domaines, les actions, le volume et les sorties. Il ne faut pas confondre les capacités d’anti-blocage documentées avec une autorisation de contourner une restriction d’accès.

## Mécanismes et étapes utiles

1. **Choisir le niveau d’exécution.** Les crawlers HTTP sont rapides et adaptés aux pages dont le contenu est disponible sans JavaScript ; les crawlers navigateur utilisent Playwright ou Puppeteer pour rendre le JavaScript. La documentation Python décrit aussi un crawler adaptatif qui choisit HTTP ou navigateur par requête ([architecture overview](https://crawlee.dev/python/docs/guides/architecture-overview)). Dans le harness, commencer par HTTP, puis escalader vers un navigateur seulement si le besoin est démontré.
2. **Initialiser des requêtes contrôlées.** `RequestQueue` accepte des URLs initiales et des URLs découvertes dynamiquement, avec déduplication et ordre breadth/depth-first ; `RequestList` convient à une liste connue et immuable ([request storage](https://crawlee.dev/js/docs/guides/request-storage)). Le handler peut extraire, publier des résultats et mettre en file les liens. Le routeur supporte handlers par label, handler par défaut, erreurs, échecs et hooks pré-navigation ([architecture overview](https://crawlee.dev/python/docs/guides/architecture-overview)).
3. **Limiter l’empreinte.** `maxConcurrency`, `minConcurrency` et `maxRequestsPerMinute` bornent les requêtes ; la concurrence s’ajuste aux ressources, avec un avertissement officiel contre un `minConcurrency` trop élevé ([scaling crawlers](https://crawlee.dev/js/docs/guides/scaling-crawlers)). Le harness doit imposer ses propres plafonds par domaine, même si Crawlee fournit l’auto-scaling.
4. **Gérer les sessions.** `SessionPool` associe une identité de session à cookies, erreurs, durée d’usage et éventuellement proxy ; une session peut être marquée bonne, mauvaise ou retirée. Les sessions retirées ou les proxies bloqués sont écartés et les cookies peuvent être persistés par session ([session management](https://crawlee.dev/js/docs/guides/session-management)). Cette fonction est utile pour la robustesse de sites autorisés, mais doit être désactivée ou strictement contrôlée dans les scénarios où l’anti-détection serait disproportionnée.
5. **Configurer les proxies explicitement.** `ProxyConfiguration` accepte des URLs statiques, une fonction de sélection et des niveaux de proxy ; le même `sessionId` peut conserver le même proxy ([proxy management](https://crawlee.dev/js/docs/guides/proxy-management)). Les secrets de proxy doivent venir d’un coffre/secret manager, jamais des prompts, logs ou datasets.
6. **Persister et reprendre.** `Dataset` est un stockage append-only de résultats structurés ; `KeyValueStore` stocke JSON, fichiers, captures ou configuration ; `RequestQueue` suit les requêtes en attente/traitées. Les stockages nommés persistent entre exécutions, tandis que les stockages anonymes peuvent être purgés au démarrage ([storages Python](https://crawlee.dev/python/docs/guides/storages)). La version JavaScript utilise par défaut `./storage`, configurable par `CRAWLEE_STORAGE_DIR` ([request storage](https://crawlee.dev/js/docs/guides/request-storage)).
7. **Observer l’exécution.** L’architecture Python expose événements de persistance d’état, informations système, migration, arrêt et statut crawler, ainsi que statistiques de requêtes, retries et erreurs ([architecture overview](https://crawlee.dev/python/docs/guides/architecture-overview)). Le harness doit convertir ces signaux en journaux structurés, métriques et décision d’arrêt.

## Interfaces et artefacts

Les interfaces principales sont : crawler (`BasicCrawler` et spécialisations), `requestHandler`, `Router`, contexte de crawling, `RequestQueue`/`RequestList`, `Dataset`, `KeyValueStore`, `SessionPool`, `ProxyConfiguration`, hooks, statistiques et événements. Les artefacts sont les requêtes dédupliquées, résultats tabulaires append-only, fichiers/HTML/JSON/captures, état de reprise, logs et métriques. La documentation Python précise que des storage clients distincts peuvent fournir mémoire, filesystem ou Apify, et qu’un client custom peut implémenter l’interface de stockage ([architecture overview](https://crawlee.dev/python/docs/guides/architecture-overview)).

Pour un harness, le contrat recommandé est un adaptateur interne qui accepte : `allowed_origins`, URLs initiales, profondeur/max-requests, mode `http|browser|adaptive`, rate limit, schéma d’extraction, taille maximale des artefacts et durée maximale. Il renvoie des éléments versionnés avec URL finale, URL source, horodatage, statut, type de contenu, hash, provenance et erreurs ; les données brutes et les cookies sont isolés des sorties destinées au modèle.

## Limites et dépendances

Crawlee ne garantit ni sélecteurs corrects, ni disponibilité, ni exactitude sémantique : la page officielle indique explicitement qu’il ne corrige pas les sélecteurs cassés ([crawlee.dev/js](https://crawlee.dev/js)). Il ne décide pas si une collecte est licite, conforme aux conditions d’utilisation, respectueuse des robots.txt, du droit d’auteur, de la vie privée ou des contrôles d’accès. Il faut donc une politique de domaine et de données en amont.

Le navigateur est plus coûteux et ajoute une surface d’attaque : JavaScript tiers, téléchargements, pop-ups, SSRF via redirections, exfiltration de cookies et consommation mémoire. Playwright n’est pas inclus dans l’installation JavaScript de Crawlee pour réduire la taille ; il faut l’installer séparément ([dépôt JS](https://github.com/apify/crawlee)). En Python, les fonctionnalités sont des extras optionnels et l’installation des navigateurs Playwright est une étape distincte ([dépôt Python](https://github.com/apify/crawlee-python)). Le sandbox doit donc isoler le processus, limiter CPU/RAM/temps, bloquer les schémas non HTTP(S), filtrer DNS/réseau privé et contrôler téléchargements et sous-processus.

La persistance locale est pratique mais n’est pas, en soi, un stockage chiffré, multi-tenant ou transactionnel. Les datasets sont append-only et le stockage clé-valeur remplace une valeur plutôt que de faire des mises à jour partielles ([storages Python](https://crawlee.dev/python/docs/guides/storages)). Le harness doit gérer chiffrement, rétention, contrôle d’accès, quotas disque et nettoyage des données personnelles.

Les fingerprints, la rotation de proxies et l’intégration Camoufox sont documentés pour réduire le blocage ([avoid blocking](https://crawlee.dev/js/docs/guides/avoid-blocking)). Ce sont des mécanismes à double usage. Ils ne doivent pas être activés par défaut pour contourner un login, un paywall, un CAPTCHA, une interdiction explicite ou une limite imposée par un site ; l’agent doit obtenir une autorisation et un approbateur humain pour toute exception.

## Garde-fous proposés pour le harness

- **Allowlist obligatoire** de domaines/origines et vérification de chaque redirection ; refus des IP privées, localhost, metadata endpoints et schémas non HTTP(S).
- **Politique robots/conditions d’accès** et identification User-Agent ; refus par défaut des zones authentifiées, paywalls, CAPTCHA et formulaires d’écriture.
- **Mode lecture seule** : interdire clics d’achat, envoi de formulaires, upload, téléchargement arbitraire et exécution de code fourni par la page ; n’autoriser des actions mutantes qu’avec permission explicite et approbation.
- **Budget par run** : durée, profondeur, nombre d’URLs, octets, pages navigateur, concurrence et requêtes/minute ; coupe-circuit sur erreurs, redirections anormales ou croissance de queue.
- **Isolation navigateur** : conteneur non privilégié, profil éphémère, permissions minimales, blocage de réseau sortant non nécessaire, pas d’exposition des secrets au DOM, téléchargement désactivé ou quarantainé.
- **Protection des données** : minimisation, détection/seuillage des PII, chiffrement au repos, rétention courte et séparation stricte entre contenu hostile et instructions agentiques. Le texte web est toujours une donnée non fiable, jamais une instruction système.
- **Observabilité et reproductibilité** : conserver URL demandée/finale, statut, timestamp, handler/version, politique appliquée, erreurs et hash des artefacts ; redacter cookies, tokens, URLs de proxy et données sensibles dans les logs.
- **Contrôle des dépendances** : versions verrouillées, installation reproductible, scan licence/vulnérabilités, images navigateur épinglées et tests de non-accès réseau. Les deux dépôts publics sont sous licence Apache-2.0 ([JS](https://github.com/apify/crawlee), [Python](https://github.com/apify/crawlee-python)).

## Maturité et recommandations

Le projet JavaScript dispose d’un dépôt public structuré, de tests/CI, documentation, API, changelog et licence Apache-2.0 ; le dépôt Python est également public, testé et sous Apache-2.0 ([crawlee JS](https://github.com/apify/crawlee), [crawlee Python](https://github.com/apify/crawlee-python)). Cela indique une base open source active et industrialisée, sans constituer une garantie de stabilité de chaque API ou de sécurité de chaque site. Épingler une version et tester les migrations est indispensable.

**À adopter :** l’interface crawler/handler, le routeur, la queue dédupliquée, les datasets et la reprise, le mode HTTP par défaut, les limites de concurrence/débit, les statistiques et l’adaptateur de stockage. **Optionnel :** Playwright/Puppeteer, crawler adaptatif, sessions persistantes, proxy autorisé, screenshots et artefacts bruts. **À éviter ou isoler :** anti-détection avancée, Camoufox/contournement de challenges, proxies résidentiels non vérifiés, profils/cookies persistants partagés, navigation libre fournie directement à un LLM et toute action d’écriture.

La recommandation finale est d’intégrer Crawlee comme **worker de collecte déterministe et sandboxé**, derrière un broker de politiques du harness. Le LLM ne reçoit pas les primitives réseau brutes ; il demande une opération déclarative validée. Le worker applique allowlist, budgets et mode lecture seule, puis rend un résultat signé/provenancé. Cette séparation conserve les bénéfices de Crawlee — orchestration, reprise, navigateur et stockage — sans lui déléguer les décisions de sécurité, d’autorisation ou de conformité.

## Références

- [1]: https://crawlee.dev/js "Crawlee JavaScript — présentation officielle"
- [2]: https://crawlee.dev/python/docs/guides/architecture-overview "Crawlee Python — architecture overview"
- [3]: https://crawlee.dev/js/docs/guides/request-storage "Crawlee JavaScript — request storage"
- [4]: https://crawlee.dev/python/docs/guides/storages "Crawlee Python — storages"
- [5]: https://crawlee.dev/js/docs/guides/session-management "Crawlee JavaScript — session management"
- [6]: https://crawlee.dev/js/docs/guides/proxy-management "Crawlee JavaScript — proxy management"
- [7]: https://crawlee.dev/js/docs/guides/scaling-crawlers "Crawlee JavaScript — scaling crawlers"
- [8]: https://crawlee.dev/js/docs/guides/avoid-blocking "Crawlee JavaScript — avoid getting blocked"
- [9]: https://github.com/apify/crawlee "Dépôt public Crawlee JavaScript/TypeScript"
- [10]: https://github.com/apify/crawlee-python "Dépôt public Crawlee Python"

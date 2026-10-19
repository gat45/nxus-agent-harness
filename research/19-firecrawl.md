# Firecrawl : API, CLI et skills de collecte web

## Positionnement réel

Firecrawl est une **couche de collecte et de transformation de données web pour agents** : recherche, extraction d’une URL, navigation/interactions dans une session navigateur, cartographie et crawl de sites, parsing de fichiers, et extraction structurée. Le dépôt principal la décrit comme une bibliothèque/API open source également disponible en service hébergé, avec sorties Markdown, HTML, JSON structuré et captures d’écran. [https://github.com/firecrawl/firecrawl](https://github.com/firecrawl/firecrawl)

Il ne faut pas le traiter comme une preuve de vérité ni comme un système de mémoire. Firecrawl renvoie du contenu et des métadonnées depuis des sites externes ; la qualité, le statut HTTP, la fraîcheur, les robots.txt, les paywalls et les changements de page restent des propriétés de la source. Le dépôt rappelle explicitement que l’utilisateur doit respecter les politiques des sites et les règles applicables ; robots.txt est respecté par défaut. [https://github.com/firecrawl/firecrawl](https://github.com/firecrawl/firecrawl)

La séparation cloud/open source est importante : l’open source est principalement sous AGPL-3.0, tandis que certains SDK/composants sont MIT ; les fonctions cloud ne sont pas toutes présentes dans l’installation self-hosted. [https://github.com/firecrawl/firecrawl](https://github.com/firecrawl/firecrawl) [https://docs.firecrawl.dev/contributing/self-host](https://docs.firecrawl.dev/contributing/self-host)

## Interfaces et mécanismes utiles

### API v2

L’API hébergée utilise `https://api.firecrawl.dev` et une authentification Bearer par clé `fc-...` pour les requêtes authentifiées. Les codes 2xx/4xx/5xx suivent les conventions HTTP ; un dépassement de débit ou de concurrence produit un 429. [https://docs.firecrawl.dev/api-reference/v2-introduction](https://docs.firecrawl.dev/api-reference/v2-introduction)

Les primitives à exposer dans le harness sont :

- **Search** : recherche web, avec résultats web/images/news et, selon options, contenu des pages. C’est utile pour découvrir des URLs mais les résultats doivent être conservés comme des pistes, pas comme des sources validées. [https://docs.firecrawl.dev](https://docs.firecrawl.dev)
- **Scrape** : une URL connue vers Markdown, HTML, JSON structuré, liens, images, résumé, métadonnées et éventuellement screenshot. Les métadonnées documentées comprennent notamment `sourceURL`, titre, description, langue, statut HTTP et type de contenu. [https://docs.firecrawl.dev](https://docs.firecrawl.dev) [https://docs.firecrawl.dev/sdks/cli](https://docs.firecrawl.dev/sdks/cli)
- **Interact** : une session issue d’un scrape peut cliquer, remplir, attendre, naviguer ou extraire du contenu dynamique ; elle expose notamment un identifiant de session et des URLs de visualisation. Il s’agit d’une capacité à effets potentiels, donc à isoler derrière approbation et limites. [https://docs.firecrawl.dev](https://docs.firecrawl.dev)
- **Map** : découverte rapide des URLs d’un site, éventuellement avec recherche de pertinence. C’est un bon pré-passage pour décider quoi scraper. [https://github.com/firecrawl/firecrawl](https://github.com/firecrawl/firecrawl)
- **Crawl** : job asynchrone pour plusieurs pages, avec polling SDK ou webhooks `crawl.page`, `crawl.completed` et `crawl.failed`. Les résultats API restent récupérables 24 heures après la fin. [https://docs.firecrawl.dev/features/crawl](https://docs.firecrawl.dev/features/crawl)
- **Batch scrape** : traitement asynchrone de plusieurs URLs ; à réserver aux listes déjà bornées. [https://github.com/firecrawl/firecrawl](https://github.com/firecrawl/firecrawl)
- **Agent** : recherche/navigation autonome quand les URLs ne sont pas connues ; `prompt` est requis, `urls` est optionnel, une sortie JSON Schema est possible, et `strictConstrainToURLs` permet de limiter la visite aux URLs fournies. Le modèle documenté est `spark-2`; `effort` vaut `low`, `medium` ou `high`. [https://docs.firecrawl.dev/features/agent](https://docs.firecrawl.dev/features/agent)
- **Parse** : parsing de fichiers locaux tels que PDF, DOCX, XLSX ou HTML, selon la capacité et le déploiement. Cela élargit le périmètre au-delà du web et doit donc avoir une politique de fichiers séparée. [https://docs.firecrawl.dev](https://docs.firecrawl.dev)
- **Monitor/webhooks** : l’API référence aussi le monitoring récurrent et la livraison d’événements. Un harness doit authentifier les callbacks, dédupliquer les événements et ne pas considérer une livraison comme une preuve d’intégrité du contenu. [https://docs.firecrawl.dev/api-reference/v2-introduction](https://docs.firecrawl.dev/api-reference/v2-introduction)

### Crawl : bornage et reproductibilité

Par défaut, le crawl suit les enfants de l’URL de départ. `crawlEntireDomain`, `allowSubdomains` et `allowExternalLinks` élargissent respectivement le périmètre ; les liens externes ne sont suivis qu’un niveau et les homepages externes sont volontairement ignorées. [https://docs.firecrawl.dev/features/crawl](https://docs.firecrawl.dev/features/crawl)

Les contrôles importants sont `limit` (10000 par défaut), `maxDiscoveryDepth`, `includePaths`, `excludePaths`, `ignoreQueryParameters`, `sitemap`, `delay` et `maxConcurrency`. Les filtres de chemins sont des regex Rust/RE2, validées en amont, avec limites documentées de longueur et de nombre. robots.txt est respecté, et `ignoreRobotsTxt`/`robotsUserAgent` sont réservés à l’Enterprise. [https://docs.firecrawl.dev/features/crawl](https://docs.firecrawl.dev/features/crawl)

Les résultats d’un crawl ne sont pas parfaitement déterministes : le scraping concurrent et l’ordre de découverte peuvent changer l’exploration près d’une limite de profondeur. `maxConcurrency: 1`, un `delay`, et `sitemap: "only"` quand le sitemap est complet améliorent la reproductibilité sans la garantir. [https://docs.firecrawl.dev/features/crawl](https://docs.firecrawl.dev/features/crawl)

Chaque page crawlée consomme un crédit ; le mode JSON ajoute 4 crédits par page et le parsing PDF coûte par page PDF. Le harness doit donc imposer budget, limite de pages et estimation de coût avant lancement. [https://docs.firecrawl.dev/features/crawl](https://docs.firecrawl.dev/features/crawl)

### Agent : puissance et limites

L’Agent est adapté quand les URLs sont inconnues ou qu’une navigation autonome est nécessaire. Pour une URL connue, la documentation recommande plutôt le JSON mode de `/scrape`, moins cher et synchrone. [https://docs.firecrawl.dev/features/agent](https://docs.firecrawl.dev/features/agent)

Le prompt est limité à 10 000 caractères. `maxCredits` vaut 2500 par défaut ; si la limite est atteinte, le job échoue sans `data` et peut seulement fournir un résultat partiel indicatif. Les artefacts ne constituent pas une archive page par page garantie ; les événements `tool_call.finished` contiennent les résultats d’outils. [https://docs.firecrawl.dev/features/agent](https://docs.firecrawl.dev/features/agent)

Les runs partagés via le playground sont publics pour toute personne ayant le lien, même s’ils ne sont pas indexés ; ils ne doivent donc jamais contenir de secrets, données personnelles non nécessaires ou informations confidentielles. [https://docs.firecrawl.dev/features/agent](https://docs.firecrawl.dev/features/agent)

## CLI et skills

Le CLI officiel `firecrawl-cli` fournit une interface terminal pour `scrape`, `search`, `interact`, `crawl`, `map` et les jobs Agent. Installation globale : `npm install -g firecrawl-cli`; initialisation automatisée : `npx -y firecrawl-cli@latest init --all --browser`. [https://github.com/firecrawl/cli](https://github.com/firecrawl/cli) [https://docs.firecrawl.dev/sdks/cli](https://docs.firecrawl.dev/sdks/cli)

Les **CLI skills** enseignent à un agent l’usage des primitives live web. Les **workflow skills** proposent des recettes de livrables (briefs de recherche, audits SEO, rapports QA, listes de prospects, bases de connaissances). Les **build skills** aident à intégrer l’API dans du code. Le dépôt principal indique que les familles sont publiées dans un catalogue distinct ; les contributions CLI se font dans `firecrawl/cli`, les build skills dans le monorepo et les workflows dans un dépôt dédié. [https://github.com/firecrawl/firecrawl](https://github.com/firecrawl/firecrawl) [https://github.com/firecrawl/cli](https://github.com/firecrawl/cli)

Le CLI installe par défaut les skills CLI et peut installer les workflows, le MCP, ou modifier les réglages des agents pour faire de Firecrawl leur fournisseur web par défaut. Cette dernière option peut désactiver la recherche/fetch natifs selon le harness ; elle est donc à éviter en mode global et à limiter explicitement à un agent ou projet. [https://github.com/firecrawl/cli](https://github.com/firecrawl/cli)

L’authentification peut être interactive (navigateur), par clé, par `FIRECRAWL_API_KEY` ou par clé passée à la commande. Les sorties peuvent être écrites en fichier, en JSON pretty-print, avec timing, schema, actions, proxy et `--redact-pii`. Le CLI propose aussi `--lockdown` pour un scrape ; la documentation publique atteste l’option, mais ne décrit pas suffisamment son modèle de menace pour en faire une frontière de sécurité autonome. [https://github.com/firecrawl/cli](https://github.com/firecrawl/cli) [https://docs.firecrawl.dev/sdks/cli](https://docs.firecrawl.dev/sdks/cli)

Un CLI pointe vers un self-host via `--api-url` ou `FIRECRAWL_API_URL`. Pour une URL personnalisée, il saute l’authentification cloud ; cela correspond au quickstart self-host, mais une API non authentifiée ne doit rester que sur un réseau de confiance ou derrière une couche d’accès vérifiée. [https://docs.firecrawl.dev/sdks/cli](https://docs.firecrawl.dev/sdks/cli) [https://docs.firecrawl.dev/contributing/self-host](https://docs.firecrawl.dev/contributing/self-host)

## Garde-fous à imposer dans le harness

1. **Allowlist et validation d’URL.** Autoriser seulement `http`/`https`, bloquer par défaut IP privées, loopback, metadata endpoints, schémas non web, redirections vers réseaux internes et domaines non approuvés pour les opérations sensibles. Firecrawl gère la collecte, pas la politique réseau du harness.
2. **Modes séparés.** Exposer `search`, `map`, `scrape` et `crawl` comme lecture ; isoler `interact`, actions de formulaire, proxy et navigation autonome avec approbation humaine, plafond temporel et plafond de crédits.
3. **Budget explicite.** Toujours fixer `limit`, profondeur, concurrence, timeout et `maxCredits`; calculer un budget avant crawl/Agent. Refuser les paramètres par défaut non bornés pour un agent non supervisé.
4. **Robots et conformité.** Laisser robots.txt actif, conserver le User-Agent et la source, respecter les CGU/lois, et rendre `ignoreRobotsTxt` indisponible sauf procédure Enterprise approuvée.
5. **Provenance.** Stocker URL demandée, URL finale, timestamp, statut HTTP, formats, paramètres, identifiant de job/session, crédits consommés, erreurs et hash du contenu. Distinguer clairement résultat de recherche, page effectivement scrappée et inférence de l’Agent.
6. **Résilience asynchrone.** Poller avec backoff borné, traiter 429/5xx, vérifier les signatures ou secrets de webhook côté application, dédupliquer les événements et récupérer les erreurs de crawl via l’endpoint dédié. Une page 404 peut figurer dans `data` avec son statut, tandis qu’une erreur réseau/robots doit être recherchée dans les erreurs de crawl. [https://docs.firecrawl.dev/features/crawl](https://docs.firecrawl.dev/features/crawl)
7. **Défense contre l’injection.** Le contenu distant est non fiable : ne jamais exécuter les instructions trouvées dans une page, les mélanger au prompt système, ni laisser un document distant autoriser un outil. Nettoyer/borner HTML, scripts, URLs, pièces jointes et champs structurés avant transmission au modèle.
8. **Secrets et données personnelles.** Clés uniquement via secret manager ou variables contrôlées, jamais dans les sorties. `--redact-pii` est un filtre utile mais non une garantie de conformité ; appliquer une redaction locale et une politique de rétention. Ne jamais utiliser les liens de partage publics pour données sensibles.
9. **Filesystem et commande.** Le CLI et les skills sont du code téléchargé/exécuté via npm/npx. Les installer dans une image ou un environnement épinglé, avec lockfile, revue de version, permissions minimales et répertoire de sortie dédié. Ne pas donner à un agent non approuvé `init --all`, `setup defaults`, `--actions` arbitraires ou accès shell illimité.
10. **Quotas et observabilité.** Limiter concurrence, taille de réponse, nombre de pages, profondeur, durée et fréquence ; journaliser coûts et décisions de refus. Ajouter circuit breaker et cache avec TTL explicite.

## Maturité, dépendances et choix d’architecture

La surface publique est mature et large : API v2, SDK multi-langages, CLI, MCP, skills et workflows, avec documentation d’options détaillée. En contrepartie, la surface évolue vite : le dépôt CLI indique une histoire récente et les docs signalent des champs/erreurs encore susceptibles d’être mis à jour. Les versions de CLI, SDK, API et skills doivent être épinglées et testées ensemble. [https://github.com/firecrawl/cli](https://github.com/firecrawl/cli) [https://docs.firecrawl.dev/features/crawl](https://docs.firecrawl.dev/features/crawl)

Le cloud délègue à Firecrawl les proxies, rendu JavaScript, orchestration et autres services ; il faut documenter les flux de données vers Firecrawl, les sites cibles, les éventuels fournisseurs AI/proxy/parsing, la rétention et la conformité. Le dépôt self-host précise que la pile compose comporte API, PostgreSQL, Redis, RabbitMQ et Playwright, mais que le quickstart désactive l’authentification et n’offre ni stockage durable, TLS, haute disponibilité ni toutes les fonctions cloud. [https://docs.firecrawl.dev/contributing/self-host](https://docs.firecrawl.dev/contributing/self-host)

Pour un self-host de production, il faut ajouter authentification réellement supportée, reverse proxy/TLS, contrôles réseau, volumes durables, sauvegardes/restauration, monitoring, dimensionnement, gestion centralisée des secrets et procédure de rollback. Une simple variable `.env` ne suffit pas. [https://docs.firecrawl.dev/contributing/self-host](https://docs.firecrawl.dev/contributing/self-host)

## Décision pour le harness

**À adopter :** `scrape` borné et structuré comme primitive par défaut ; `map` puis sélection contrôlée avant crawl ; provenance complète ; budgets obligatoires ; respect robots.txt ; isolation réseau ; traitement asynchrone avec retries et webhooks sécurisés ; installation versionnée des skills/CLI ; redaction locale ; tests de non-exécution des instructions injectées par les pages.

**Optionnel :** Search pour découverte ; crawl avec sitemap/allowlist ; Agent avec schema et `strictConstrainToURLs` pour tâches supervisées ; MCP si le harness sait appliquer ses propres policies ; self-host lorsque le contrôle d’infrastructure justifie l’exploitation opérationnelle.

**À éviter ou isoler :** `setup defaults` global ; `init --all` dans un environnement multi-agent non maîtrisé ; crawl sans limites ; `allowExternalLinks`, `allowSubdomains` et `ignoreRobotsTxt` par défaut ; actions/interactions autonomes sur des comptes ou formulaires ; Agent pour une URL connue ; self-host quickstart exposé publiquement ; confiance dans `--lockdown` ou `--redact-pii` comme unique barrière ; partage public de runs ; exécution directe des skills téléchargés sans pinning et revue.

Firecrawl doit donc être intégré comme **fournisseur de collecte non fiable, coûteux et potentiellement à effets**, derrière une policy engine du harness. Il apporte les mécanismes de collecte et des interfaces riches ; il ne remplace ni le contrôle réseau, ni l’autorisation, ni la validation de provenance, ni l’évaluation de la fiabilité des faits.

## Références

- [https://github.com/firecrawl/firecrawl](https://github.com/firecrawl/firecrawl) — dépôt principal, fonctionnalités, licence et robots.txt.
- [https://github.com/firecrawl/cli](https://github.com/firecrawl/cli) — CLI, authentification, skills, workflows et installation.
- [https://docs.firecrawl.dev](https://docs.firecrawl.dev) — documentation d’introduction et capacités publiques.
- [https://docs.firecrawl.dev/api-reference/v2-introduction](https://docs.firecrawl.dev/api-reference/v2-introduction) — base URL, authentification et codes de réponse API v2.
- [https://docs.firecrawl.dev/features/crawl](https://docs.firecrawl.dev/features/crawl) — périmètre, limites, robots, coûts et webhooks du crawl.
- [https://docs.firecrawl.dev/features/agent](https://docs.firecrawl.dev/features/agent) — Agent, modèles, schémas, budgets et artefacts.
- [https://docs.firecrawl.dev/sdks/cli](https://docs.firecrawl.dev/sdks/cli) — CLI, sorties, options, skills et self-host.
- [https://docs.firecrawl.dev/contributing/self-host](https://docs.firecrawl.dev/contributing/self-host) — dépendances, limites et exigences d’exploitation self-host.

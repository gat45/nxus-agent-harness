# Scrapling pour l’extraction web résiliente

## Conclusion opérationnelle

Le nom **Scrapling** recouvre ici deux projets publics distincts qu’il faut absolument séparer dans le harness :

1. `kernelmethod/scrapling`, la source de départ fournie, est un petit crawler Go (MIT), créé en 2021, avec 10 commits et une surface fonctionnelle très limitée : GET concurrent, parsing HTML, extraction des liens et parcours borné par profondeur.
2. `D4Vinci/Scrapling` est le projet Python moderne documenté sur Read the Docs et PyPI (BSD-3-Clause), dont le rôle est plus large : parsing HTML, sélection adaptative, fetch HTTP ou navigateur, spiders asynchrones, sorties structurées et serveur MCP pour agents.

Le harness doit donc adopter **le second comme composant d’extraction contrôlé**, et ne pas attribuer ses fonctions avancées au dépôt `kernelmethod`. Le dépôt Go peut servir de référence historique ou de crawler minimal isolé, mais il ne constitue pas un socle agentique sécurisé.

## 1. Rôle réel et mécanismes utiles

### 1.1 Dépôt `kernelmethod/scrapling` : crawler minimal

Le README le décrit comme « A simple, high-performance web crawler », installable avec Go et piloté par `scrapling -h` : [dépôt et README kernelmethod](https://github.com/kernelmethod/scrapling). Son CLI accepte une URL unique, une profondeur `-d` (par défaut 0), un nombre maximal de requêtes concurrentes `-t` (par défaut 10) et un mode `--external-domains` : [main.go](https://raw.githubusercontent.com/kernelmethod/scrapling/main/main.go).

Le parcours est simple : une goroutine traite une URL, fait un `http.Get`, parse le HTML avec `golang.org/x/net/html`, extrait les seuls attributs `href` des balises `<a>`, imprime chaque URL nouvellement vue et lance récursivement les liens à profondeur décroissante : [workers.go](https://raw.githubusercontent.com/kernelmethod/scrapling/main/workers.go), [scrape.go](https://raw.githubusercontent.com/kernelmethod/scrapling/main/scrape.go). Deux filtres Cuckoo dédupliquent les URL traitées et imprimées. La restriction par défaut compare `parsedTaskURL.Host` à l’hôte initial et n’autorise que `http` et `https`; elle peut être désactivée avec `--external-domains` : [workers.go](https://raw.githubusercontent.com/kernelmethod/scrapling/main/workers.go).

Ce projet fournit donc un **graphe de liens**, pas une extraction sémantique : pas de CSS/XPath métier, pas de données structurées, pas de navigateur JavaScript, pas de session, pas de stockage de crawl, pas d’API d’agent. Les dépendances déclarées sont anciennes et peu nombreuses (`go 1.15`, `cuckoofilter`, `x/net`) : [go.mod](https://raw.githubusercontent.com/kernelmethod/scrapling/main/go.mod).

### 1.2 Projet Python D4Vinci : chaîne d’extraction résiliente

La documentation présente trois familles de fetchers : `Fetcher` pour HTTP rapide, `DynamicFetcher` pour les pages JavaScript via Playwright, et `StealthyFetcher` pour des protections plus fortes. Les classes de session correspondantes gardent cookies et état entre appels; la documentation recommande de choisir le niveau le moins coûteux qui suffit : [Fetchers basics](https://scrapling.readthedocs.io/en/latest/fetching/choosing.html).

Chaque fetcher renvoie un objet `Response` contenant notamment le code HTTP, headers, cookies, historique de redirections, corps brut, métadonnées et, pour le navigateur, les réponses XHR capturées : [Fetchers basics](https://scrapling.readthedocs.io/en/latest/fetching/choosing.html). Les interfaces d’extraction comprennent CSS3, XPath, recherche par filtres, texte et regex, avec pseudo-sélecteurs `::text` et `::attr(...)` : [Querying elements](https://scrapling.readthedocs.io/en/latest/parsing/selection.html).

La fonction distinctive est l’**adaptive scraping**. En phase de sauvegarde, Scrapling conserve dans SQLite par défaut des propriétés de l’élément : balise, texte, attributs, frères, chemin, parent et contexte. En phase de correspondance, il compare les candidats et retourne ceux dont le score de similarité est le plus élevé. L’activation est explicite (`adaptive=True`); un sélecteur peut sauvegarder avec `auto_save=True`, puis relocaliser après changement de structure avec `adaptive=True` : [Adaptive scraping](https://scrapling.readthedocs.io/en/latest/parsing/adaptive.html).

Cette résilience est heuristique, pas une garantie d’identité. La documentation signale notamment que, lors d’une sauvegarde, seul le premier élément de résultats est mémorisé; une relocalisation peut donc retourner le premier élément correspondant. Elle recommande de fournir un identifiant et un contexte suffisamment spécifiques : [Adaptive scraping](https://scrapling.readthedocs.io/en/latest/parsing/adaptive.html). `find_similar()` filtre par profondeur, balises parentales et similarité floue des attributs; les seuils et attributs ignorés influencent directement les faux positifs : [Querying elements](https://scrapling.readthedocs.io/en/latest/parsing/selection.html).

### 1.3 Crawl, artefacts et interfaces

Le framework de spiders est asynchrone et inspiré de Scrapy. Le flux documenté est : génération de `Request`, mise en file prioritaire et fingerprint, respect de la concurrence et éventuellement de `robots.txt`, routage vers une session, détection/réessai des réponses bloquées, callback, puis nouvelles requêtes ou items : [Spiders architecture](https://scrapling.readthedocs.io/en/latest/spiders/architecture.html).

Les artefacts exploitables par le harness sont : `Request`, `Response`, callbacks asynchrones, dictionnaires d’items, `CrawlStats`, `ItemList`, et export JSON, JSONL, CSV ou XML. Le scheduler déduplique par URL, méthode, corps et identifiant de session. `crawldir` permet des checkpoints atomiques contenant requêtes en attente et URL vues; un cache de réponses existe pour le développement, mais la documentation le déconseille en production : [Spiders architecture](https://scrapling.readthedocs.io/en/latest/spiders/architecture.html).

Pour un pipeline RAG ou agentique, `Response.markdown()` produit du Markdown nettoyé, avec option `main_content_only` et `css_selector`; scripts, styles et contenus cachés sont retirés avant conversion. Le projet fournit aussi le template `SiteToMarkdownSpider` : [Fetchers basics](https://scrapling.readthedocs.io/en/latest/fetching/choosing.html), [release v0.4.15](https://github.com/D4Vinci/Scrapling/releases/tag/v0.4.15).

## 2. Serveur MCP et implications agentiques

Le serveur MCP expose des outils one-shot et des outils de session : requêtes HTTP (`make_request`), fetch dynamique, fetch furtif, opérations bulk, ouverture/fermeture de sessions, fetch dans une session, capture de screenshot et capture XHR. Les outils permettent de réduire le contenu transmis à l’agent avec un sélecteur CSS, au lieu de remettre toute la page au modèle : [MCP server](https://scrapling.readthedocs.io/en/latest/ai/mcp-server.html).

Un garde-fou utile est le nettoyage automatique du contenu caché lorsque `main_content_only` est activé par défaut : éléments masqués par CSS, `aria-hidden`, `<template>`, commentaires HTML et caractères Unicode invisibles sont retirés afin de réduire les injections de prompt. Cette mesure est une sanitation de contenu, **pas** une frontière de confiance complète : le texte visible, les attributs, les redirections, les données retournées par API et les effets de navigation restent des entrées non fiables : [MCP server](https://scrapling.readthedocs.io/en/latest/ai/mcp-server.html).

Depuis la version 0.4.15, le transport HTTP est authentifié par défaut et écoute sur `127.0.0.1`; `--auth-token` ou `SCRAPLING_MCP_AUTH_TOKEN` est requis, tandis que `--no-auth` est un choix explicite. Pour une écoute réseau il faut demander `--host 0.0.0.0`, configurer `--allowed-host` contre le DNS rebinding et placer le service derrière TLS, car le token HTTP seul est transmis en clair. Il s’agit d’une clé partagée, non de comptes par client : [MCP server](https://scrapling.readthedocs.io/en/latest/ai/mcp-server.html), [release v0.4.15](https://github.com/D4Vinci/Scrapling/releases/tag/v0.4.15).

Dans le harness, le MCP doit être traité comme une **capacité réseau à haut risque**. L’agent ne doit jamais obtenir implicitement un fetch arbitraire depuis le réseau interne. Il faut imposer une allowlist de domaines, bloquer IP privées/link-local/loopback et schémas non HTTP(S), limiter ports, redirections, taille de réponse, temps CPU, téléchargements, screenshots et nombre de pages, journaliser chaque appel et séparer les sessions par tâche. Le serveur seul ne prouve pas ces contrôles applicatifs.

## 3. Limites, maturité et dépendances

Le projet Python déclare explicitement le statut PyPI **“4 - Beta”**, requiert Python `>=3.10`, et publie les extras `fetchers`, `rag`, `ai`, `shell` et `all` : [pyproject.toml](https://raw.githubusercontent.com/D4Vinci/Scrapling/main/pyproject.toml), [PyPI](https://pypi.org/project/scrapling/). Les dépendances de base incluent `lxml`, `cssselect`, `orjson`, `tld` et `w3lib`; les fetchers ajoutent notamment `curl_cffi`, Playwright, Patchright, BrowserForge et des composants d’empreinte navigateur; l’extra AI ajoute MCP et Markdownify : [pyproject.toml](https://raw.githubusercontent.com/D4Vinci/Scrapling/main/pyproject.toml).

La version publique consultée est 0.4.15 et la release signale des changements cassants du MCP, des corrections de solver Cloudflare et une réutilisation des onglets de navigateur : [release v0.4.15](https://github.com/D4Vinci/Scrapling/releases/tag/v0.4.15). Le dépôt principal affiche une suite de tests, une documentation étendue, un Dockerfile et une activité de releases, mais PyPI conserve le classement Beta : [dépôt D4Vinci/Scrapling](https://github.com/D4Vinci/Scrapling), [PyPI](https://pypi.org/project/scrapling/). Le harness doit donc épingler une version, tester ses contrats et prévoir les breaking changes, en particulier sur MCP.

Les fetchers navigateur ont un coût et une surface d’attaque supérieurs à HTTP simple : Chromium/Chrome, Playwright/Patchright, cookies, JavaScript, proxies, fingerprinting et éventuelle résolution de challenge. Les capacités dites stealth/anti-bot ne doivent pas être considérées comme une garantie de disponibilité ni comme une permission de contourner des contrôles d’accès. L’usage doit rester conforme aux autorisations du site, à ses conditions et au droit applicable.

## 4. À adopter, optionnel, à isoler

### À adopter

- **Adapter d’extraction derrière une interface interne** (`fetch`, `parse`, `extract`, `evidence`) afin que l’agent ne dépende pas directement des classes Scrapling.
- Commencer par `Fetcher` HTTP, parser CSS/XPath et `Response` borné; passer à `DynamicFetcher` seulement si le HTML initial ne contient pas le contenu requis.
- Utiliser `adaptive` uniquement pour des champs stables et surveillés, avec identifiant explicite, domaine logique explicite et validation de schéma, cardinalité et score avant acceptation.
- Utiliser le scheduler/spider pour les crawls autorisés, avec `allowed_domains`, limites globales/par domaine, `robots_txt_obey`, profondeur/pages maximales, checkpoints et sortie JSONL versionnée.
- Conserver l’URL, le statut, l’horodatage, les headers utiles, le sélecteur, la version Scrapling et un extrait de preuve; distinguer valeur extraite, valeur absente et extraction incertaine.
- Garder `main_content_only=True`, sélectionner avant transmission au modèle et effectuer une seconde validation hors LLM.
- Épingler Python, Scrapling et dépendances, installer dans une image non privilégiée, séparer processus navigateur et orchestrateur, et appliquer egress filtering.

### Optionnel

- Sessions persistantes pour un site nécessitant cookies ou plusieurs pages; les fermer explicitement à la fin avec `close_session` : [MCP server](https://scrapling.readthedocs.io/en/latest/ai/mcp-server.html).
- `capture_xhr` quand l’API publique de la page est la source la plus fiable, en traitant les réponses capturées comme données non fiables et en contrôlant leur taille.
- Markdown/RAG et `SiteToMarkdownSpider` pour constituer un corpus, seulement après filtrage de domaine, budget et détection de duplicats.
- MCP local en stdio pour un outil mono-processus; HTTP uniquement si l’authentification, TLS, allowlist et isolation réseau sont effectivement déployés.
- Proxy et rotation si l’organisation les autorise et si les secrets sont injectés hors code; ne pas les activer par défaut.

### À éviter ou à isoler

- **Ne pas mélanger les deux projets homonymes.** Le dépôt Go n’offre pas l’adaptive scraping, les fetchers navigateur ou le MCP du projet Python.
- Ne pas laisser l’agent fournir une URL arbitraire à `make_request`, `fetch` ou `stealthy_fetch`; c’est une primitive SSRF potentielle.
- Ne pas exposer `--http --no-auth` avec `--host 0.0.0.0`; la documentation avertit que tous les outils deviennent accessibles à quiconque atteint le port : [MCP server](https://scrapling.readthedocs.io/en/latest/ai/mcp-server.html).
- Ne pas traiter un succès HTTP ou un score adaptatif comme preuve de justesse. Rejeter ou mettre en quarantaine les résultats dont le score, la cardinalité, le type ou les invariants métier sont inattendus.
- Ne pas utiliser le cache de réponses de développement comme cache de production, ni partager un `crawldir`/SQLite adaptatif entre tâches non isolées : [Spiders architecture](https://scrapling.readthedocs.io/en/latest/spiders/architecture.html), [Adaptive scraping](https://scrapling.readthedocs.io/en/latest/parsing/adaptive.html).
- Ne pas intégrer le crawler Go sans le durcir : son code appelle `http.Get` directement, n’impose ni timeout explicite ni taille maximale de corps, lance une goroutine par lien et utilise des filtres probabilistes; [workers.go](https://raw.githubusercontent.com/kernelmethod/scrapling/main/workers.go). Ses tests montrent même que l’extracteur de liens reconnaît des `file:` et `mailto:` avant que la validation de crawl ne les écarte, ce qui confirme la nécessité d’une validation en amont : [scrape_test.go](https://raw.githubusercontent.com/kernelmethod/scrapling/main/scrape_test.go).

## 5. Architecture de harness recommandée

Le contrôleur doit produire une requête Scrapling à partir d’une **politique déclarative** : domaine autorisé, schémas, profondeur, budget de pages/octets/temps, niveau de fetcher, sélecteurs approuvés et destination de sortie. Un proxy egress vérifie à nouveau DNS et IP après résolution et bloque les réseaux privés. Le worker Scrapling tourne en sandbox sans secrets d’agent, avec limites de fichiers, mémoire, processus et navigateur.

Le pipeline doit être : (1) validation de cible et consentement; (2) fetch minimal; (3) extraction ciblée; (4) nettoyage/sanitisation; (5) validation typée et cardinalité; (6) conservation de preuve; (7) transmission au modèle uniquement du sous-ensemble nécessaire. Le modèle peut proposer un sélecteur, mais ne doit pas pouvoir élargir seul l’allowlist, désactiver `main_content_only`, activer un proxy secret, changer de domaine ou relancer indéfiniment.

L’adaptive scraping doit être observé comme une stratégie de récupération : le chemin normal est le sélecteur explicite; si absent, Scrapling tente la relocalisation; si plusieurs candidats, score faible ou résultat incohérent, le harness arrête et demande une revue. Les fixtures HTML anciennes/nouvelles doivent tester les changements de DOM, les doublons, les éléments malveillants, les redirections, les gros corps, les pages JS et les erreurs de navigateur.

## Références

[1]: https://github.com/kernelmethod/scrapling "Dépôt Go kernelmethod/scrapling"
[2]: https://raw.githubusercontent.com/kernelmethod/scrapling/main/main.go "CLI du crawler Go"
[3]: https://raw.githubusercontent.com/kernelmethod/scrapling/main/workers.go "Workers et validation du crawler Go"
[4]: https://raw.githubusercontent.com/kernelmethod/scrapling/main/scrape.go "Extraction des hrefs du crawler Go"
[5]: https://raw.githubusercontent.com/kernelmethod/scrapling/main/scrape_test.go "Tests publics du crawler Go"
[6]: https://raw.githubusercontent.com/kernelmethod/scrapling/main/go.mod "Dépendances Go"
[7]: https://github.com/D4Vinci/Scrapling "Dépôt Python officiel D4Vinci/Scrapling"
[8]: https://scrapling.readthedocs.io/en/latest/fetching/choosing.html "Fetchers et Response"
[9]: https://scrapling.readthedocs.io/en/latest/parsing/selection.html "Sélection HTML et éléments similaires"
[10]: https://scrapling.readthedocs.io/en/latest/parsing/adaptive.html "Adaptive scraping"
[11]: https://scrapling.readthedocs.io/en/latest/spiders/architecture.html "Architecture des spiders"
[12]: https://scrapling.readthedocs.io/en/latest/ai/mcp-server.html "Serveur MCP et garde-fous"
[13]: https://raw.githubusercontent.com/D4Vinci/Scrapling/main/pyproject.toml "Métadonnées et dépendances Python"
[14]: https://github.com/D4Vinci/Scrapling/releases/tag/v0.4.15 "Release 0.4.15"
[15]: https://pypi.org/project/scrapling/ "Paquet PyPI Scrapling"

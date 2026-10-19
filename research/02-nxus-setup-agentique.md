# Méthode NXUS de mise en place d’un assistant agentique — évaluation pour un harness sécurisé

## Conclusion opérationnelle

La « méthode NXUS » n’est pas un framework ni une implémentation publique de harness. C’est le retour d’expérience de Rudy Molinillo sur une organisation personnelle : un agent installé sur un poste, des fichiers Markdown pour le contexte, des outils (commandes, API, MCP et contrôle d’interface), plusieurs machines/services, un coffre de secrets, du versionnage, de la supervision et une validation humaine. L’article dit lui-même que son environnement utilise des accès étendus pour montrer ce qui est possible, et que ce n’est pas une recommandation de commencer avec des droits administrateur [1].

Pour un harness complet, il faut donc adopter **la séparation des responsabilités et les artefacts explicites**, mais ne pas copier l’infrastructure ni l’autonomie par défaut. Le cœur à retenir est : état de projet lisible, outils typés et limités, exécution isolée, vérification indépendante, approbation humaine pour les effets irréversibles, et traçabilité. Les fichiers `AGENTS.md`/`CLAUDE.md` sont du contexte chargé dans le prompt, pas des barrières de sécurité : Claude précise qu’ils sont traités comme des instructions et qu’un hook `PreToolUse` est nécessaire pour bloquer réellement une action [3].

## Ce que décrit exactement NXUS

L’article place le PC principal au centre, avec un portable et un téléphone pour piloter à distance, un serveur local pour certains services et sauvegardes, un VPS pour les applications accessibles en ligne, et des services externes pour les modèles, médias, paiements ou builds [1]. Cette topologie est un choix d’exploitation, pas une exigence agentique. Elle introduit des dépendances (réseau, identités, disponibilité, coûts, sauvegardes) et augmente la surface d’attaque à mesure que l’agent franchit des frontières de machine.

La mémoire proposée commence par des fichiers Markdown. Un fichier d’entrée pointe vers les projets et conventions ; chaque projet documente objectif, état, décisions, commandes et prochaines étapes. NXUS distingue utilement les **règles durables**, l’**état courant** et les **documents de référence** [1]. Le RAG est présenté comme complément pour de grands corpus, non comme prérequis. Syncthing sert à synchroniser des notes, tandis que Git sert au versionnage du code ; branches ou espaces de travail distincts évitent les collisions entre tâches [1].

Les mécanismes d’action sont quatre : commandes locales, API, connexions MCP, et contrôle d’interface (navigateur ou logiciel) [1]. Le tutoriel NXUS qualifie le MCP d’« API améliorée » et montre que le contrôle direct est généralement plus rapide et contrôlable que la souris [2]. Cette formulation est pédagogique, mais le rôle réel de MCP est plus précis : protocole d’échange de contexte entre un hôte IA et des serveurs, avec primitives `tools`, `resources` et `prompts`; MCP ne dicte ni l’usage du LLM ni la gestion des permissions [4].

Pour une application, le parcours proposé est : cadrage du besoin ; création du dossier ; construction et vérification ; versionnage ; préparation de la mise en ligne ; distribution mobile éventuelle [1]. L’agent peut prendre une grande partie des opérations dans un environnement préparé, mais le périmètre autorisé, les tests et la décision de publication restent humains. L’article ne promet ni délai de livraison ni acceptation par une boutique.

La maintenance décrite relie erreurs Sentry, notifications Telegram, investigation assistée, correction, tests et vérification après mise en ligne [1]. NXUS souligne qu’un conteneur « sain » ne prouve pas que le parcours utilisateur fonctionne, et qu’un outil d’erreurs ne remplace ni tests ni contrôle de disponibilité [1]. C’est une distinction importante pour le harness : **observation technique, validation fonctionnelle et décision de déploiement sont trois étapes différentes**.

## Artefacts et interfaces à reprendre

### 1. Contrat de projet versionné

Adopter un petit contrat vérifiable dans chaque workspace :

- `AGENTS.md` ou `CLAUDE.md` pour les règles de travail, la politique d’autorisation, les commandes de test et les limites ;
- `projet.md` pour objectif, utilisateurs, périmètre et décisions ;
- `etat.md` pour faits vérifiés, changements, risques, tests exécutés et prochaines étapes ;
- un journal d’exécution append-only (identifiant de tâche, outils appelés, paramètres redacted, résultat, approbations) ;
- un manifeste d’outils et de permissions, versionné avec le projet ;
- des branches/worktrees ou snapshots pour isoler les tâches.

La proposition NXUS d’actualiser `etat.md` en distinguant vérifié et incertain est particulièrement utile [1]. Le harness devrait rendre cette distinction structurée, par exemple avec des champs `evidence`, `status`, `verified_at` et `owner`, plutôt que de la laisser seulement dans du texte libre.

Les interfaces éditeur confirment l’intérêt mais aussi la limite de ce modèle. Codex découvre les instructions globales puis celles des répertoires, les concatène du plus général au plus spécifique, et impose par défaut une limite de 32 KiB [5]. Claude charge `CLAUDE.md`/`AGENTS.md` et une mémoire automatique ; la mémoire automatique est limitée aux 200 premières lignes ou 25 KiB [3]. Le harness doit donc afficher les fichiers effectivement chargés, leur ordre, leur hash et les éventuelles troncatures. Un nom de fichier ne garantit jamais qu’un agent donné l’a lu.

### 2. Registre d’outils typés

Adopter une interface d’outil explicite : nom, version, schéma d’entrée, préconditions, effets, niveau de risque, timeout, idempotence, résultat structuré et procédure de rollback. Privilégier API/CLI/MCP aux clics d’interface. Réserver le contrôle GUI aux logiciels sans interface programmable, dans une session dédiée et observable.

MCP peut servir de protocole d’exposition, pas de système d’autorisation complet. L’architecture officielle sépare un host, un client par serveur, et des serveurs locaux ou distants ; la couche transport peut utiliser STDIO ou HTTP « Streamable », avec authentification HTTP et recommandation OAuth pour le distant [4]. Chaque serveur doit donc être traité comme une dépendance distincte : provenance, version épinglée, allowlist d’outils, permissions réseau, limites de débit et journalisation. L’harness ne doit pas transformer automatiquement tout `tools/list` en capacité autorisée.

### 3. Exécution isolée

Adopter un runner par tâche : workspace temporaire, utilisateur non privilégié, limites CPU/mémoire/disque/temps, réseau fermé par défaut, montage minimal des fichiers et suppression des secrets de l’environnement. Les actions dangereuses (`rm`, publication, achat, envoi externe, migration, rotation de clé, installation) doivent être des outils spécialisés avec confirmation et, lorsque possible, simulation/dry-run.

Le contrôle humain NXUS est un bon principe, mais il doit être placé au **point d’effet** et non seulement au début d’une conversation. Une validation doit montrer l’intention normalisée, les paramètres, les fichiers/ressources touchés, le coût, la réversibilité et l’identité qui exécute. Après approbation, le serveur d’outils doit encore vérifier la politique ; l’interface ne doit pas pouvoir contourner cette décision.

### 4. État, tests et preuves

Adopter un cycle déterministe : comprendre le brief ; proposer un plan ; obtenir les approbations requises ; modifier dans un workspace isolé ; exécuter tests/lint/build ; inspecter le résultat ; produire un diff et un rapport de preuves ; seulement ensuite publier. Le résultat final doit séparer : fait observé, affirmation du modèle, test automatisé, validation humaine et incertitude.

Les alertes Sentry/Telegram de NXUS sont utiles comme signaux d’entrée, mais non comme oracle. Le harness doit compléter par health checks, tests de régression, tests de parcours utilisateur et corrélation entre version déployée et événement observé [1].

## Garde-fous à rendre obligatoires

**Moindre privilège.** Ne pas donner de droits administrateur, accès global au disque ou accès illimité au réseau à un agent débutant. Le tutoriel NXUS montre explicitement le mode « accès complet » comme démonstration, puis avertit que ce n’est pas prudent [2]. Utiliser des identités séparées par environnement et par outil, avec permissions minimales et expiration.

**Séparation instructions/données.** Un fichier, ticket, email, log, page web, commit ou résultat d’outil est une donnée non fiable, même si l’utilisateur l’a transmis. OWASP décrit les injections directes et indirectes, l’empoisonnement RAG, la manipulation d’outils et la pollution de mémoire [7]. Structurer les messages pour distinguer instructions fiables, données externes et observations, mais ne jamais considérer un simple délimiteur textuel comme une frontière de sécurité ; la décision d’autorisation doit être appliquée au niveau outil [7].

**Défense en profondeur.** Mettre en place validation d’entrée, détection d’encodage/obfuscation, validation de sortie, surveillance des appels d’outils, allowlists, limites de taille et de débit, journaux sans secrets, tests d’injection, kill switch et procédure d’incident. OWASP recommande explicitement HITL, moindre privilège, monitoring complet et tests réguliers, tout en rappelant les limites des défenses contre les attaques persistantes [7]. Aucun filtre lexical ne doit être traité comme preuve de sûreté.

**Secrets.** Ne jamais placer de secret dans le brief, la mémoire, le dépôt ou le journal. Un coffre contrôle la distribution ; il ne rend pas un secret invisible à un processus autorisé. `infisical run` récupère les secrets puis lance la commande avec des variables d’environnement [8]. Pour un harness, préférer un broker/proxy qui évite d’exposer la valeur à l’agent et journaliser l’identité, la portée et l’expiration. La rotation réduit la durée d’exploitation d’une fuite ; Infisical décrit un cycle active → inactive → revoked et précise que rotation et révocation sont des phases distinctes [9]. Révoquer une identité ne remplace donc pas la rotation d’une clé déjà copiée.

**Accès réseau et authentification.** Pour un service distant, ne pas exposer directement l’origine. Cloudflare recommande de masquer l’IP, restreindre les connexions et surveiller la santé ; Tunnel crée une connexion sortante sans IP publiquement routable, tandis que l’allowlist d’IP seule est seulement « moderately secure » et vulnérable à l’usurpation [6]. Un OTP par email est un code à usage unique de dix minutes, pas une preuve générale de MFA ; Cloudflare documente séparément l’exigence MFA par IdP ou par Access [10] [11]. Le harness doit utiliser des facteurs indépendants, des sessions courtes, des comptes de service séparés et une révocation testée.

**Auditabilité et arrêt.** Chaque décision doit être corrélable à un run, un modèle, une version d’instructions, un outil et une approbation. Prévoir interruption utilisateur, expiration de lease, budget de pas/tokens/coût, circuit breaker sur erreurs répétées et arrêt d’urgence indépendant du LLM.

## À adopter, optionnel, à isoler ou à éviter

### À adopter

- documentation projet courte et structurée, versionnée ;
- état vérifié/incertain et preuves de tests ;
- outils typés, idempotents autant que possible, avec dry-run et rollback ;
- workspaces isolés, Git et artefacts reproductibles ;
- approbation humaine au moment des effets irréversibles ;
- moindre privilège, identités séparées, secrets hors contexte ;
- observabilité, tests de parcours et kill switch ;
- MCP comme adaptateur standardisé, derrière une politique d’outils.

### Optionnel

- RAG, lorsque le corpus dépasse une documentation de projet lisible ;
- Syncthing ou autre synchronisation de notes ;
- serveur local, VPS, Ollama et plusieurs modèles ;
- contrôle de navigateur/GUI, uniquement si aucune API fiable n’existe ;
- automatisations récurrentes et notifications externes. NXUS précise que ses routines ne tournent que lorsque le PC est allumé ; une exécution permanente exige un service distant [2].

### À isoler ou à éviter

- mode accès complet/administrateur ; à réserver à un environnement jetable et explicitement borné ;
- agent qui installe des logiciels, ouvre des ports, publie ou dépense sans approbation dédiée ;
- secrets injectés directement dans l’environnement d’un modèle ou dans les logs ;
- confiance implicite dans les documents récupérés, la mémoire automatique, les sorties « succès » ou la santé d’un conteneur ;
- GUI non isolée sur le poste personnel, source de collisions de « colocation du PC » [1] ;
- exposition publique d’un MCP ou d’un agent sans authentification forte, filtrage réseau, quotas et journalisation.

## Maturité, dépendances et limites

La maturité de la méthode NXUS est **pragmatique et démonstrative**, pas celle d’un standard certifié. Elle est suffisamment concrète pour définir un premier harness : elle nomme les fichiers, les machines, les interfaces et un flux de livraison. Elle ne fournit toutefois pas, dans l’article public, de code de harness, de schémas d’autorisation formels, de modèle de menace exhaustif, de garanties de confinement, de benchmarks de sécurité ou de SLO. Les vidéos et les exemples restent des retours d’expérience ; l’auteur signale lui-même les décisions discutables et les limites [1] [2].

Les dépendances sont nombreuses : Codex/Claude ou autre host, modèle distant ou local, OS et permissions, Git, éventuellement MCP et ses SDK, services API, gestionnaire de secrets, réseau/Cloudflare, observabilité, CI/CD, hébergement et sauvegardes. Chaque dépendance a son propre cycle de mise à jour et sa propre identité. Le harness doit donc posséder un inventaire de versions, une politique de changement et des tests de compatibilité.

Il existe une homonymie à traiter avec prudence. `nxus-SYSTEMS/nxusKit` est un dépôt public distinct, décrit comme un SDK multi-langage pour LLM, moteurs de règles, réseaux bayésiens et CLI [12]. La documentation publique de `nxus.SYSTEMS` le présente comme l’organisation GitHub de ce projet [13]. Rien dans les sources consultées n’établit que ce SDK est le code ou le harness utilisé par l’auteur de nxus.fr. Il ne faut donc ni l’attribuer à la méthode NXUS de l’article, ni supposer qu’il implémente ses prompts privés ou ses fonctionnalités. Il peut éventuellement être évalué séparément comme composant d’orchestration/raisonnement, après revue de code, licence, sécurité et adéquation.

## Architecture cible minimale

Un harness exécutable devrait séparer : (1) **orchestrateur** qui planifie mais n’autorise pas seul ; (2) **registre de contexte** qui versionne instructions, état et preuves ; (3) **policy engine** déterministe qui décide selon identité, outil, ressource, environnement et risque ; (4) **tool gateway** qui valide schémas, quotas, secrets, réseau et approbations ; (5) **runner isolé** par tâche ; (6) **verifier** qui exécute tests et contrôles indépendants ; (7) **audit/observabilité** redacted ; (8) **human approval UI** ; (9) **kill switch** et gestion des leases. Le LLM ne doit être qu’un composant de proposition/raisonnement au milieu de cette chaîne.

Le premier jalon recommandé est un seul agent, un seul dépôt, des outils lecture + édition dans un workspace temporaire, tests automatiques et approbation obligatoire avant réseau sortant, suppression, publication ou dépense. Étendre ensuite par preuves : chaque nouvelle capacité doit apporter son schéma, sa politique, son test adversarial, son rollback et son propriétaire. Cela conserve le meilleur de NXUS — contexte, action et vérification — sans transformer une démonstration personnelle en autorité de sécurité.

## Références

[1]: https://nxus.fr/blog/setup-ia-agentique-memoire-outils-securite "NXUS — Mon setup d’IA agentique : mémoire, outils et contrôle humain"
[2]: https://nxus.fr/blog/installer-agent-ia-pc-tuto-debutant "NXUS — Installer un agent IA sur ton PC : le tuto débutant"
[3]: https://code.claude.com/docs/en/memory "Anthropic — How Claude remembers your project"
[4]: https://modelcontextprotocol.io/docs/learn/architecture "Model Context Protocol — Architecture overview"
[5]: https://developers.openai.com/codex/guides/agents-md/ "OpenAI — Custom instructions with AGENTS.md"
[6]: https://developers.cloudflare.com/fundamentals/security/protect-your-origin-server/ "Cloudflare — Protect your origin server"
[7]: https://cheatsheetseries.owasp.org/cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.html "OWASP — LLM Prompt Injection Prevention Cheat Sheet"
[8]: https://infisical.com/docs/cli/commands/run "Infisical — run command"
[9]: https://infisical.com/docs/documentation/platform/secrets-mgmt/concepts/secrets-rotation "Infisical — Secret rotation"
[10]: https://developers.cloudflare.com/cloudflare-one/integrations/identity-providers/one-time-pin/ "Cloudflare — One-time PIN login"
[11]: https://developers.cloudflare.com/cloudflare-one/access-controls/policies/mfa-requirements/ "Cloudflare — Enforce MFA"
[12]: https://github.com/nxus-SYSTEMS/nxusKit "GitHub — nxus-SYSTEMS/nxusKit"
[13]: https://docs.nxus.systems/github/ "nxus.SYSTEMS Docs — GitHub Repositories"

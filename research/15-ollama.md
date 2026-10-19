# Ollama comme moteur local de modèles

## Conclusion opérationnelle

Ollama est un **runtime d’inférence et de gestion de modèles** qui expose une API HTTP locale, un CLI et des bibliothèques Python/JavaScript. Son rôle n’est pas celui d’un orchestrateur agentique complet : il produit des sorties de modèle, des appels d’outils et des embeddings, mais le harness doit conserver la responsabilité de la boucle agentique, de l’autorisation, de l’exécution des outils, de la validation, de la journalisation et de l’isolation. La documentation officielle présente Ollama comme un moyen de construire avec des modèles ouverts, en local ou dans le cloud, avec des prompts locaux non vus par Ollama.com ([page d’accueil](https://ollama.com/); [API](https://docs.ollama.com/api)).

**Décision recommandée : adopter Ollama comme adaptateur de fournisseur local interchangeable**, derrière une interface de modèle du harness. L’activation par défaut doit être locale (`http://localhost:11434`), avec cloud désactivé pour les charges sensibles. L’accès réseau distant, le téléchargement/push de modèles et les modèles cloud doivent être explicitement opt-in et protégés par une politique séparée.

## Rôle réel et interfaces

Le serveur local écoute par défaut sur `127.0.0.1:11434`; `OLLAMA_HOST` permet de modifier l’adresse d’écoute ([FAQ officielle](https://docs.ollama.com/faq)). L’API Ollama utilise notamment `POST /api/chat`, `POST /api/generate`, `POST /api/embed`, ainsi que des endpoints de gestion des modèles. Les mêmes fonctions sont accessibles par l’API officielle Python et JavaScript ([API](https://docs.ollama.com/api); [dépôt principal](https://github.com/ollama/ollama); [SDK Python](https://github.com/ollama/ollama-python)). L’API n’est pas strictement versionnée, mais Ollama annonce une compatibilité ascendante attendue et des dépréciations rares ([API](https://docs.ollama.com/api)); le harness doit néanmoins épingler une version et tester les contrats.

Ollama fournit aussi une compatibilité partielle OpenAI (`/v1/chat/completions`, `/v1/completions`, `/v1/embeddings`, et une partie de `/v1/responses`). Cette compatibilité est utile pour brancher un client existant, mais elle n’est pas une équivalence complète : `tool_choice`, logprobs et plusieurs champs ne sont pas pris en charge, et l’API Responses ne fournit pas les requêtes stateful ([compatibilité OpenAI](https://docs.ollama.com/api/openai-compatibility)). Le harness doit donc préférer l’adaptateur natif quand il a besoin des sémantiques Ollama, et tester les fonctionnalités réellement supportées par modèle et version.

Le dépôt public `ollama/ollama` est sous licence MIT et contient le serveur, le CLI, les API, les backends et les tests visibles ([dépôt](https://github.com/ollama/ollama)). Il documente une intégration avec `llama.cpp` et fournit des images Docker officielles. Les installations publiques couvrent macOS, Windows, Linux, Docker et des variantes GPU ([README du dépôt](https://github.com/ollama/ollama); [Linux](https://docs.ollama.com/linux)). Cela indique une maturité pratique élevée pour un runtime local généraliste, mais ne constitue ni une garantie SLA, ni une certification de sécurité, ni une preuve de qualité uniforme des modèles.

## Mécanismes utiles au harness

### Boucle d’outils

L’API Chat accepte une liste d’outils sous forme de fonctions JSON Schema. Le modèle renvoie des `tool_calls`; le client exécute la fonction, ajoute un message `tool`, puis rappelle le modèle. La documentation montre les modes single-shot, appels parallèles, boucle multi-tour et accumulation des fragments en streaming ([tool calling](https://docs.ollama.com/capabilities/tool-calling)). **Ollama ne fournit pas l’exécution sécurisée de la fonction** : les exemples appellent directement des fonctions Python/JavaScript. Le harness doit donc maintenir une table blanche `nom -> implémentation`, valider les arguments, imposer des budgets d’itérations/appels et refuser tout nom inconnu.

Le streaming doit être traité comme un flux non fiable : en mode streaming, le client accumule `thinking`, `content` et `tool_calls`, puis soumet l’ensemble avec les résultats d’outils ([tool calling](https://docs.ollama.com/capabilities/tool-calling); [streaming](https://docs.ollama.com/capabilities/streaming)). Ne jamais exécuter un outil sur un fragment partiel. Le harness doit gérer timeouts, annulation, réponses tronquées, doublons, appels parallèles non idempotents et absence d’appel final.

### Sorties structurées

Le champ `format` accepte `json` ou un JSON Schema. La documentation recommande de valider côté client, par exemple avec Pydantic ou Zod, et de baisser la température pour améliorer la déterminisme ([structured outputs](https://docs.ollama.com/capabilities/structured-outputs)). C’est adapté aux plans d’action, décisions de routage et enveloppes de résultat, mais **ce n’est pas une preuve de vérité ni une validation métier**. Le harness doit parser strictement, valider le schéma et les invariants métier, rejeter/réessayer avec un budget, puis dégrader vers une sortie sûre. La documentation indique explicitement que le cloud Ollama ne supporte pas les structured outputs ([structured outputs](https://docs.ollama.com/capabilities/structured-outputs)).

### Embeddings et RAG

`/api/embed` transforme du texte en vecteurs normalisés utilisables pour recherche sémantique, base vectorielle et RAG. La documentation recommande notamment `embeddinggemma`, `qwen3-embedding` et `all-minilm`, et exige d’utiliser le même modèle pour indexation et requête ([embeddings](https://docs.ollama.com/capabilities/embeddings)). Le harness peut adopter ce chemin pour une mémoire documentaire locale, mais doit versionner le modèle d’embedding, la segmentation, les métadonnées et la distance utilisée. Ollama ne fournit pas à lui seul la base vectorielle, la politique de provenance ou le contrôle d’accès aux documents.

### Modèles, artefacts et reproductibilité

Un `Modelfile` est le blueprint d’un modèle personnalisé. Il peut déclarer `FROM`, paramètres de génération, template, message système, licence, exemples de messages, version minimale requise et capacités ([Modelfile](https://docs.ollama.com/modelfile)). Le harness doit traiter le nom/tag de modèle comme une dépendance non suffisante : enregistrer l’identifiant/digest quand disponible, le Modelfile, la licence, la version Ollama, le template et les paramètres (`temperature`, `seed`, `num_ctx`, `num_predict`, `stop`). La graine peut aider à reproduire une sortie, sans garantir une reproductibilité absolue entre matériel, backend, quantification ou versions.

Les modèles peuvent être importés depuis GGUF ou Safetensors et sont stockés dans un répertoire configurable par `OLLAMA_MODELS` ([Modelfile](https://docs.ollama.com/modelfile); [FAQ](https://docs.ollama.com/faq)). Les téléchargements sont une chaîne d’approvisionnement : autoriser uniquement des sources et tags approuvés, vérifier les digests/signatures disponibles, scanner les artefacts et isoler le compte système. Ne pas accepter un Modelfile ou un modèle utilisateur comme s’il s’agissait d’un prompt système de confiance.

### Contexte, ressources et concurrence

La longueur de contexte dépend fortement de la VRAM : la documentation indique des valeurs par défaut de 4k sous 24 GiB, 32k entre 24 et 48 GiB, et 256k à partir de 48 GiB; les agents et outils devraient viser au moins 64k lorsque le matériel le permet ([context length](https://docs.ollama.com/context-length)). Augmenter le contexte augmente la mémoire requise. Le harness doit mesurer le budget de tokens, tronquer de façon contrôlée, résumer l’historique et refuser les tâches dépassant la capacité effective au lieu de supposer qu’un grand contexte est disponible.

Ollama peut garder un modèle en mémoire (5 minutes par défaut), précharger, décharger avec `keep_alive`, mettre en file les requêtes et traiter plusieurs requêtes selon la mémoire. `OLLAMA_MAX_QUEUE`, `OLLAMA_MAX_LOADED_MODELS` et `OLLAMA_NUM_PARALLEL` influencent la charge ([FAQ](https://docs.ollama.com/faq)). Le harness doit définir ses propres limites de concurrence, timeout, backpressure et quotas afin d’éviter OOM, starvation et latence non bornée; surveiller `ollama ps`/les métriques de processus et distinguer erreur de surcharge (503) d’erreur de modèle.

## Garde-fous et limites

**Réseau et confidentialité.** En local, Ollama indique ne pas voir les prompts et données. En cloud, les prompts/réponses sont traités pour fournir le service, même si la FAQ affirme ne pas stocker ni entraîner sur leur contenu ([FAQ](https://docs.ollama.com/faq)). Le harness doit faire respecter une classification des données plutôt que de se fier à une promesse fournisseur. Pour une politique strictement locale, `disable_ollama_cloud` dans `~/.ollama/server.json` ou `OLLAMA_NO_CLOUD=1` désactive les fonctions cloud et la recherche web ([FAQ](https://docs.ollama.com/faq)).

Une instance exposée au réseau ne doit pas être considérée comme authentifiée : la documentation montre `OLLAMA_HOST=0.0.0.0:11434` et recommande de passer par un proxy si nécessaire, tandis que l’API OpenAI locale accepte une clé factice ignorée ([FAQ](https://docs.ollama.com/faq); [compatibilité OpenAI](https://docs.ollama.com/api/openai-compatibility)). Par défaut, lier à loopback, filtrer par pare-feu et placer toute exposition distante derrière un proxy mTLS/OIDC ou une passerelle avec authentification, autorisation, quotas et audit. Restreindre `OLLAMA_ORIGINS`; ne jamais ouvrir toutes les extensions navigateur sans besoin explicite ([FAQ](https://docs.ollama.com/faq)).

**Outils et prompt injection.** Le schema d’outil décrit une intention au modèle; il n’accorde aucun droit. Les résultats d’outils et documents peuvent contenir des instructions adversariales. Séparer messages de contrôle, contenu utilisateur et résultats externes; ne pas laisser le modèle modifier sa propre politique; exiger une confirmation humaine pour effets irréversibles; exécuter les outils dans des workers isolés avec capacités minimales, chemins autorisés, réseau sortant filtré et secrets absents par défaut.

**Modèles et licences.** Ollama fournit une bibliothèque de modèles mais les licences et capacités dépendent du modèle. Le champ `LICENSE` du Modelfile documente la licence déclarée, sans remplacer la vérification juridique de l’artefact ([Modelfile](https://docs.ollama.com/modelfile)). Établir une allowlist de modèles approuvés, conserver la licence et les évaluations de sécurité, et isoler les modèles expérimentaux.

**Mises à jour et incidents.** Le dépôt public recommande de maintenir Ollama à jour, sécuriser les instances hébergées et surveiller les activités inhabituelles ([SECURITY.md](https://github.com/ollama/ollama/blob/main/SECURITY.md)). Les versions et binaires sont publiés sur GitHub, avec installations spécifiques possibles via `OLLAMA_VERSION` ([releases](https://github.com/ollama/ollama/releases); [Linux](https://docs.ollama.com/linux)). En production, épingler une version, vérifier les sommes/digests, tester en préproduction et prévoir rollback. L’endpoint HTTP local et les SDK doivent être traités comme composants faillibles : journaliser version, modèle, latence, tokens, erreurs et décisions du harness, sans enregistrer les secrets ni données sensibles par défaut.

## À adopter, optionnel, à éviter

**À adopter par défaut :** l’adaptateur REST/SDK local; modèles et Modelfiles versionnés; validation JSON Schema côté harness; boucle d’outils explicitement contrôlée; quotas de tokens/temps/itérations; isolation des workers; loopback et cloud désactivé pour données sensibles; tests de contrat sur la version épinglée; observabilité redacted; fallback vers un autre fournisseur ou une sortie humaine.

**Optionnel :** compatibilité OpenAI pour réutiliser des clients; streaming pour UX; embeddings Ollama pour RAG entièrement local; parallélisme si la capacité mémoire est mesurée; préchargement et `keep_alive` pour latence stable; multimodalité si le modèle et la politique de données le permettent.

**À éviter ou isoler :** exposition directe de `11434` sur Internet/LAN; clé OpenAI factice comme contrôle d’accès; exécution directe des fonctions proposées par le modèle; confiance dans le JSON sans validation; contexte immense sans budget VRAM; téléchargement automatique de modèles inconnus; cloud pour données classifiées; dépendance à des champs de compatibilité non attestés; utilisation d’un modèle local comme arbitre de sécurité ou comme preuve factuelle.

## Évaluation finale pour le harness

Ollama est **mature comme runtime local et surface d’intégration**, avec un écosystème public actif, des SDK, Docker, API natives et une compatibilité partielle OpenAI. Il est **incomplet comme fondation de sécurité agentique** : authentification réseau, autorisation des outils, sandbox d’exécution, mémoire durable, workflow, provenance et gouvernance doivent venir du harness. La frontière d’architecture doit donc être nette : Ollama est le moteur probabiliste, tandis que le harness est le plan de contrôle déterministe qui décide si une sortie est acceptable, si un outil peut être appelé et si une action peut être commise.

## Références

- [Page d’accueil Ollama](https://ollama.com/)
- [API](https://docs.ollama.com/api)
- [Tool calling](https://docs.ollama.com/capabilities/tool-calling)
- [Structured outputs](https://docs.ollama.com/capabilities/structured-outputs)
- [Embeddings](https://docs.ollama.com/capabilities/embeddings)
- [Context length](https://docs.ollama.com/context-length)
- [FAQ](https://docs.ollama.com/faq)
- [Modelfile Reference](https://docs.ollama.com/modelfile)
- [OpenAI compatibility](https://docs.ollama.com/api/openai-compatibility)
- [Linux](https://docs.ollama.com/linux)
- [Dépôt principal](https://github.com/ollama/ollama)
- [SDK Python](https://github.com/ollama/ollama-python)
- [SECURITY.md](https://github.com/ollama/ollama/blob/main/SECURITY.md)
- [Releases](https://github.com/ollama/ollama/releases)

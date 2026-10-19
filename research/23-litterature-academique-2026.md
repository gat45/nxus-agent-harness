# Littérature académique et projets publics (recherche 2026)

Analyse ajoutée le 18/10/2026, en appui des évolutions `llm_planner.py`,
`memory.py` et du tag OWASP dans `policy.py`. Recherche web (requêtes
standard), pas de lecture intégrale des articles — les résumés ci-dessous
reflètent les abstracts/snippets trouvés, pas une relecture complète.

## Articles académiques (arXiv)

- **« Reason Less, Verify More: Deterministic Gates Recover a Silent
  Policy-Violation Failure Mode in Tool-Using LLM Agents »**
  (arXiv:2607.07405, atelier KDD). Sur le benchmark τ²-bench (domaine
  compagnie aérienne), des portes déterministes qui vérifient chaque
  écriture proposée avant exécution font passer le taux de succès complet
  de 29,6 % à 42,0 % avec gpt-4o-mini. Les auteurs décrivent ce résultat
  comme borné : une porte déterministe ne garantit pas la réussite de la
  tâche, seulement l'absence de violation silencieuse de politique.
  **Pertinence pour ce projet** : validation externe de l'architecture déjà
  en place ici (`ReflectionReview` puis `PolicyEngine.authorize()` avant
  toute exécution) — ce n'est pas une nouveauté à ajouter, mais une
  confirmation que l'approche adoptée dès le MVP initial correspond à ce que
  la littérature mesure comme efficace.
  [arxiv.org/pdf/2607.07405](https://arxiv.org/pdf/2607.07405)

- **« Capability Gates Are Not Authorization »** (arXiv:2606.28679). Audite
  LangChain/LangGraph, LlamaIndex et le Stripe Agent Toolkit : aucun des
  trois ne fournit par défaut une porte d'autorisation déterministe par
  appel. Propose ScopeGate, un design en cinq étapes : périmètre,
  autorisation, plafond monétaire, idempotence, refus par défaut.
  **Pertinence** : ce harness couvre déjà périmètre (allowed_paths/tools),
  autorisation (grants exacts), idempotence (grant à usage unique, testé en
  T05) et refus par défaut (policy fail-closed) ; le plafond monétaire ne
  s'applique pas (aucun outil de paiement). Les quatre points pertinents
  étaient déjà couverts avant cette recherche — elle confirme l'absence de
  trou plutôt que d'en révéler un.
  [emergentmind.com/papers/2606.28679](https://www.emergentmind.com/papers/2606.28679)

- **« Solver-Aided Verification of Policy Compliance in Tool-Augmented LLM
  Agents »** (arXiv:2603.20449). Traduit des politiques en langage naturel
  en contraintes SMT-LIB ; un solveur Z3 vérifie chaque appel planifié avant
  exécution. **Pertinence** : approche plus lourde (preuve formelle) que la
  vérification déterministe par règles de ce MVP ; pertinent si une future
  politique devient trop complexe pour rester lisible comme suite de `if`
  dans `policy.py`, pas nécessaire au stade actuel.
  [arxiv.org/abs/2603.20449](https://arxiv.org/abs/2603.20449)

- **« Fault-Tolerant Sandboxing for AI Coding Agents »** (arXiv:2512.12806).
  Traite chaque appel d'outil comme une transaction atomique avec retour en
  arrière ; 100 % d'interception des commandes à risque et 100 % de succès
  de rollback dans leurs mesures, ~14,5 % de surcoût (≈1,8 s/transaction).
  **Pertinence** : ce MVP n'a pas de rollback automatique — le seul
  mécanisme de retour en arrière documenté est manuel (voir
  [docs/runbooks/rollback.md](../docs/runbooks/rollback.md), suppression du
  brouillon). Piste pour une évolution future, pas implémentée ici.
  [arxiv.org/html/2512.12806v1](https://arxiv.org/html/2512.12806v1)

- **« Towards Verifiably Safe Tool Use for LLM Agents »** (arXiv:2601.08012).
  Analyse de risques STPA + MCP à capacités étiquetées pour forcer des
  séquences d'outils et des flux de données spécifiques. **Pertinence** :
  hors périmètre (MCP explicitement désactivé dans ce MVP, voir
  architecture-blueprint.md) ; à revisiter si MCP est un jour intégré.
  [alphaxiv.org/abs/2601.08012](https://alphaxiv.org/abs/2601.08012)

## Projets publics comparables

- **AgentGate** (agentkitai) : gateway d'approbation humaine pour les
  appels d'outils d'agents, avec politique auto-approve/auto-deny/humain et
  étiquetage de chaque entrée d'audit par le risque OWASP LLM Top-10 qu'elle
  mitige. **Repris ici** : l'idée d'étiquetage OWASP, appliquée à
  `PolicyDecision` dans `policy.py` (voir `_OWASP_LLM_RISK`) — annotation
  pure, aucune logique de décision copiée ou modifiée.
- **Keep** (majorcontext) : gateway de politique au niveau API avec règles
  YAML testables hors ligne avant déploiement. **Non repris** : ce MVP
  encode ses règles en Python typé (`PolicyEngine.authorize`) plutôt qu'en
  YAML déclaratif ; un format déclaratif gagnerait en lisibilité mais
  perdrait en vérifiabilité statique (pas de typage).

## Documentation technique

- **llama.cpp — sortie structurée par schéma JSON** (docs.liquid.ai,
  mintlify ggml-org/llama.cpp) : `response_format` de type `json_schema`
  est compilé par `llama-server` en grammaire GBNF qui contraint la
  génération token par token, contrairement à `json_object` qui ne force
  qu'un JSON syntaxiquement valide sans forme précise. **Repris ici** :
  `llm_planner.py` construit un schéma JSON réel (une branche par outil
  autorisé, `tool_id` en `const`) au lieu de `json_object` seul — vérifié
  en conditions réelles contre un `llama-server` + Qwen3.8 9B : avec
  `json_object` seul, le modèle enveloppait parfois sa réponse dans un bloc
  markdown ` ```json ... ``` ` malgré l'instruction système ; avec le
  schéma JSON strict, la sortie est restée du JSON brut à chaque essai.
  [docs.liquid.ai/.../structured-output](https://docs.liquid.ai/deployment/on-device/llama-cpp/structured-output.md)

## Ce qui n'a pas été changé malgré ces lectures

- Pas de solveur SMT (2603.20449) : jugé disproportionné pour les règles
  actuelles de `policy.py`, toutes exprimables comme comparaisons directes.
- Pas de sandboxing transactionnel avec rollback auto (2512.12806) : le MVP
  reste volontairement sans exécution shell/réseau réelle, donc sans besoin
  de rollback système ; seule une écriture de fichier existe, déjà réversible
  manuellement.
- Pas d'intégration MCP à capacités étiquetées (2601.08012) : MCP reste hors
  périmètre du MVP par décision déjà documentée dans le blueprint.

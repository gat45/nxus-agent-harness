# Modèle de menace du MVP

## Actifs protégés

- **Politique et registre d’outils** : ne doivent jamais être modifiés par un contenu de tâche, de Web, de RAG ou de tool result.
- **Périmètre de workspace** : seules les écritures explicitement prévues dans le manifeste sont admises.
- **Grants d’approbation** : ils sont courts, liés à l’action exacte et à usage unique.
- **Journal d’audit** : son chaînage rend une altération détectable ; sa redaction réduit les fuites accidentelles.
- **Provenance** : un claim critique ne doit pas être présenté comme supporté sans évidence résolue.

## Menaces couvertes en P0/P1

| Menace | Contrôle MVP | Test associé |
|---|---|---|
| Injection dans un document | Le contenu est retourné avec `untrusted: true`; aucune donnée ne peut modifier la policy | T03 |
| Élargissement d’outil ou de chemin | Registre fermé, manifeste exact, profil et allowlist de chemins | T04, T08 |
| Rejeu ou substitution d’approbation | Hash d’arguments, TTL, nonce et consommation atomique | T05 |
| Appel externe inattendu | R2–R4, réseau, shell et outils externes refusés par défaut | T06 |
| Schéma d’outil ambigu | Arguments typés, champs supplémentaires interdits | T07 |
| Succès auto-déclaré | Vérificateur séparé, résultat `not_run` distinct de `pass` | T09 |
| Claim sans source | Evidence store et blocage des claims critiques non résolus | T10 |
| Fuite de secret dans les traces | Redaction avant append audit et vérification de chaîne | T11 |
| Interruption pendant action | Kill switch, révocation des grants, état `ABORTED` | T12 |
| Mélange de tenants | Répertoires de runs séparés et aucun store partagé | T14 |

## Limites connues

- Le sandboxing est **logique et applicatif** dans ce MVP : le runner n’utilise pas encore un conteneur/VM non-root avec cgroups, mount namespaces et egress filtré. Il n’exécute toutefois ni shell ni réseau.
- Le chaînage de hash ne remplace pas un stockage WORM, une signature d’opérateur ou un service d’audit externe.
- Les regex de redaction ne constituent pas un DLP complet. Ne jamais injecter des secrets réels dans les fixtures ou le CLI.
- Le modèle Ollama optionnel n’est pas un arbitre de sécurité. Toute sortie structurée reste validée localement et aucun tool call n’est exécuté automatiquement.
- Le modèle llama.cpp optionnel (modèles GGUF locaux, voir llama_cpp_adapter.py) a exactement le même statut qu’Ollama ici : ni fiable ni arbitre de sécurité, loopback uniquement, aucun tool call exécuté automatiquement.
- MCP, Open WebUI, AnythingLLM et les collecteurs Web ne font pas partie du TCB du MVP ; ils sont désactivés jusqu’à l’existence d’adaptateurs et de tests dédiés.
- `LlmPlanner` (llm_planner.py) remplace la SOURCE du plan, jamais son autorité : un plan proposé par un modèle n’est ni plus ni moins privilégié qu’un plan simulé — les deux retraversent `ReflectionReview.review()` puis `PolicyEngine.authorize()` identiquement. Limite connue : avec un petit modèle local, une proposition malformée (type incorrect, champ en trop) fait échouer le run au lieu d’être silencieusement corrigée — comportement voulu (fail-closed), pas une tolérance de robustesse à ajouter sans réflexion.
- `MemoryStore` (memory.py) n’est écrit QUE par le harness lui-même après `verify_and_complete()`, jamais depuis une sortie de modèle ou une fixture — contrairement à `retrieve_fixture`, ses entrées ne sont pas marquées `untrusted`. Elle reste cependant un CONTEXTE de prompt, jamais un chemin d’autorisation : relire la mémoire n’accorde aucun droit, ne pré-approuve rien, et un plan informé par la mémoire suit le même chemin de validation que n’importe quel autre.

## Conditions avant un connecteur R2+

1. Propriétaire du connecteur, version et provenance documentés.
2. Menace, classification des données, egress et rétention définis.
3. Broker dédié avec schémas, quotas, timeout, kill switch et audit redacted.
4. Identité à privilège minimal et secrets éphémères hors prompts/logs.
5. Tests d’injection indirecte, SSRF, redirection, erreur, reprise et non-régression.
6. Dry-run, idempotence, backup et rollback pour toute action R3/R4.

Le blueprint contient le séquencement d’implémentation complet et les références publiques associées.

## Connecteurs R2 : execute_python et fetch_url (18/10/2026)

Premiers connecteurs R2 du MVP, évalués contre la checklist ci-dessus.

1. **Propriétaire/version/provenance** : `tools.py` (harness lui-même, v1.0), aucune dépendance tierce — `subprocess`/`urllib` stdlib uniquement.
2. **Menace/données/egress/rétention** : menace = exécution de code arbitraire et exfiltration réseau arbitraire proposées par un LLM non fiable. Classification : synthétique/test comme le reste du MVP. Egress : `fetch_url` restreint par allowlist EXACTE (`contract.allowed_urls` ET `manifest.allowed_urls`, jamais un wildcard de domaine) plus une garde SSRF qui refuse tout hôte privé/loopback/link-local AVANT de consulter l'allowlist. Rétention : sortie de `execute_python` tronquée (8 Ko stdout / 4 Ko stderr) ; sortie de `fetch_url` plafonnée à 1 Mo.
3. **Broker dédié** : `ToolGateway._execute` reste le seul point d'exécution, inchangé en structure — schéma strict par outil (`additionalProperties: false`), timeout dérivé de `contract.budget_seconds` (plafonné à 60s pour le code, 30s pour fetch_url), pas de kill switch dédié à l'outil (le kill switch global `PolicyEngine.stop()` s'applique, testé en T12), audit redacted existant (T11) couvre aussi ces deux outils.
4. **Identité à privilège minimal / secrets** : **non respecté intégralement** — `execute_python` tourne avec les MÊMES privilèges OS que le process harness (pas d'utilisateur dédié, pas de conteneur). C'est la limite connue la plus importante de cet ajout : l'approbation exacte (grant lié au code littéral proposé) est la vraie barrière, pas une isolation de privilège.
5. **Tests d'injection/SSRF/redirection/erreur/reprise** : SSRF sur l'URL de départ couvert (T23, 4 hôtes privés testés, y compris l'IP de métadonnées cloud `169.254.169.254`) ; allowlist hors-périmètre couverte (T23) ; timeout couvert (T23) ; erreur réseau propre testée en conditions réelles (`example.invalid` inexistant, pas de crash). Redirection HTTP : **corrigée** — `urlopen()` suit les redirections par défaut (une allowlist sur l'URL de départ n'empêchait pas une redirection vers un hôte privé après coup) ; un opener sans redirection est utilisé à la place, vérifié en conditions réelles contre un serveur local qui redirige vers `169.254.169.254` (refusé). **Non couvert** : reprise/idempotence d'un `execute_python` partiellement exécuté.
6. **Dry-run/idempotence/rollback** : aucun dry-run ; pas d'idempotence native (un script peut avoir des effets de bord non réversibles) ; rollback = suppression manuelle du workspace de run, comme pour `write_workspace_draft`.

**Verdict** : accepté pour le MVP avec les limites ci-dessus explicitement documentées, pas comme un connecteur "complet" au sens de la checklist — en particulier l'absence de sandbox OS (point 4) reste la vraie lacune à combler avant tout usage au-delà d'une machine de confiance et d'un opérateur qui lit chaque plan avant d'approuver.

Testé de bout en bout contre un `llama-server` réel : le modèle a proposé du code Python et une URL, un humain a approuvé dans un flux CLI séparé (`submit`/`approve`), le code s'est exécuté et a produit le résultat attendu, et la page récupérée est le contenu HTML réel de la page distante (`scripts/smoke_agentic_execution.py`).

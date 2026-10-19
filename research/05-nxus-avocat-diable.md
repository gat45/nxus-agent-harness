# Préparation de décision par avocat du diable — étude pour un harness agentique

## Conclusion opérationnelle

Le cas NXUS n’est pas, tel qu’il est publié, un agent autonome qui décide ou agit dans l’entreprise. C’est un **exercice de contradiction assisté par chat**, classé « Intermédiaire » et « Assisté », où l’utilisateur fournit la décision, le contexte et le raisonnement, puis demande au modèle de jouer un contradicteur exigeant. La sortie attendue est une contradiction structurée : angles morts, risques sous-estimés, hypothèses fragiles et cinq questions difficiles. NXUS précise explicitement qu’il s’agit d’un challenge de logique, **pas d’un avis expert ni d’une validation de la réalité du marché**. Source primaire : [NXUS, « Préparer une décision en mode avocat du diable »](https://nxus.fr/cas-usage-agents-ia/preparer-decision-avocat-du-diable).

Pour un harness complet, il faut donc adopter le **protocole de stress-test décisionnel**, mais isoler toute prétention d’expertise, de recherche factuelle ou de décision finale. Le modèle doit produire des objections traçables et calibrées, jamais autoriser une action externe. Les outils de recherche peuvent être ajoutés en option, en lecture seule et avec provenance ; l’écriture, l’envoi, l’achat, la modification de données ou l’engagement juridique doivent rester hors périmètre ou derrière une approbation humaine indépendante.

## Ce que le cas NXUS décrit réellement

Le besoin est organisationnel : un dirigeant décide seul, l’entourage peut valider par habitude ou déférence, et les angles morts apparaissent après coup. L’approche publiée comporte quatre opérations : exposer la décision et son raisonnement ; demander à l’IA d’incarner un contradicteur exigeant mais constructif ; faire lister angles morts, risques et hypothèses fragiles ; obtenir les questions clés à traiter avant de s’engager. Le déroulé est en trois temps : **exposer**, **challenger**, puis **réévaluer** la décision humaine.

Le prompt d’exemple demande notamment de rester factuel et utile, de ne pas ménager l’utilisateur, et de poser cinq questions difficiles. Le résultat est qualitatif et textuel. Aucun outil, connecteur, mémoire, mécanisme de vérification des faits, protocole multi-agent, format machine, seuil de confiance ou action externe n’est attesté sur la page. Il ne faut donc pas attribuer à NXUS un code privé, des prompts système privés, une recherche web automatique ou une capacité de décision qu’il ne documente pas.

Le rôle utile est celui d’un **adversaire cognitif** : il force la recherche d’hypothèses implicites et de scénarios défavorables. Il ne constitue pas un arbitre impartial. Le modèle peut fabriquer des risques plausibles, surpondérer le négatif, répéter des biais culturels ou donner une apparence de rigueur à des prémisses fausses. La distinction NXUS entre logique et réalité du marché doit être conservée telle quelle dans l’interface et dans les journaux.

## Protocole à implémenter dans le harness

1. **Fiche d’entrée structurée.** Collecter l’objectif, la décision envisagée, les alternatives, le contexte temporel et géographique, les contraintes, les données disponibles, les parties prenantes, les coûts d’erreur et la date limite. Séparer explicitement les faits fournis, les hypothèses, les opinions et les inconnues.
2. **Reformulation contrôlée.** Le harness renvoie un résumé de la décision et demande confirmation ou correction avant le stress-test. Cette étape évite qu’une ambiguïté soit transformée silencieusement en prémisse.
3. **Contradiction organisée.** Produire des objections par catégories : hypothèses non vérifiées, coûts et capacité d’exécution, demande et concurrence, dépendances, risques juridiques ou sociaux, scénarios de base/défavorable/extrême, biais de confirmation et critères d’abandon. Chaque objection doit porter un statut : fait fourni, inférence, question ou hypothèse à tester.
4. **Questions actionnables.** Générer cinq à dix questions difficiles, chacune reliée à une décision ou à une mesure : quelle donnée ferait changer d’avis, qui peut la vérifier, à quelle échéance, et quel seuil déclenche pause ou abandon.
5. **Réponse du décideur.** Permettre à l’humain de répondre point par point. Une seconde passe doit distinguer les objections réfutées, non résolues et nouvellement apparues ; elle ne doit pas simplement répéter la première sortie.
6. **Synthèse sans verdict automatique.** Restituer une fiche : décision initiale, objections, éléments de preuve, incertitudes résiduelles, options ajustées, conditions de poursuite et décision finale de l’humain. Le champ final doit être « confirmer / modifier / suspendre / chercher des preuves », avec justification humaine.

Un schéma JSON versionné est préférable à du texte libre pour les sorties : `decision_summary`, `assumptions[]`, `objections[]`, `questions[]`, `evidence[]`, `uncertainties[]`, `human_response`, `status`. Une validation déterministe doit refuser une sortie sans distinction fait/inférence, sans question, ou qui prétend avoir vérifié une source absente.

## Outils, interfaces et dépendances

**À adopter.** Une interface de session avec aperçu de la décision, bouton de correction, affichage séparé des faits et des objections, provenance par affirmation, export JSON/Markdown, historique append-only et reprise après interruption. Le harness doit journaliser modèle, version de prompt applicatif, paramètres, outils invoqués, sources, horodatage, utilisateur approbateur et version de chaque révision.

**Optionnel.** Un récupérateur documentaire en lecture seule peut vérifier des hypothèses externes, mais les documents et pages récupérés sont des données non fiables, non des instructions. Chaque citation doit être conservée avec URL, date d’accès, extrait et niveau de confiance ; une affirmation non sourcée reste une hypothèse. Une seconde passe par un modèle différent ou un évaluateur déterministe peut contrôler la couverture des catégories, les citations et la cohérence, mais ne transforme pas le texte en vérité.

**À éviter ou isoler.** Ne pas donner à l’avocat du diable un shell, un accès général à l’e-mail, CRM, fichiers confidentiels ou moyens de publier et d’exécuter une décision. Ne pas laisser le modèle modifier la décision, envoyer un message, engager une dépense, supprimer une donnée ou appeler une API d’écriture. La persuasion rhétorique, le score de confiance unique et l’autonomie illimitée sont des signaux d’interface à éviter.

La description publique d’un agent par Anthropic distingue quatre couches : modèle, **harness** (instructions et garde-fous), outils et environnement ; un agent planifie, agit, observe et réitère. Cette source confirme que la sécurité ne se réduit pas au modèle et que la configuration des outils et de l’environnement est déterminante : [Anthropic, « Trustworthy agents in practice »](https://www.anthropic.com/research/trustworthy-agents). Pour ce cas, le harness doit volontairement réduire la boucle à planifier/analyser/poser des questions, sans agir.

Une interface d’approbation peut suivre un mécanisme public de requête/réponse : Microsoft Agent Framework documente des événements `RequestInfoEvent`, la pause du workflow, la réponse externe puis la reprise ; les demandes en attente peuvent aussi être conservées dans un checkpoint : [Microsoft, Human-in-the-loop](https://github.com/MicrosoftDocs/azure-ai-docs/blob/main/agent-framework/workflows/human-in-the-loop.md). Ce mécanisme est pertinent pour une demande de clarification ou une approbation, mais la vérification d’autorisation doit être faite par le composant d’exécution, pas par le modèle.

## Garde-fous de sécurité et de qualité

- **Moindre privilège et séparation des plans.** Autoriser par défaut uniquement les opérations de session et de lecture nécessaires. OWASP recommande des outils bornés par opération et ressource, une autorisation hors contexte du modèle et un échec fermé pour les outils inconnus ou les approbations absentes : [OWASP, AI Agent Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/AI_Agent_Security_Cheat_Sheet.html).
- **Approbation exacte.** Pour toute action future à impact élevé, l’approbation doit identifier l’acteur, l’outil, les paramètres et la cible, être consommée atomiquement, expirer et être renouvelée si un paramètre change. Pour l’avocat du diable, l’approbation porte seulement sur l’accès éventuel à un document ou sur l’export, jamais sur la décision d’entreprise.
- **Contenu externe non fiable.** Les entrées utilisateur, fichiers, pages, e-mails et réponses d’API doivent être délimités comme données. OWASP décrit les injections directes et indirectes, leurs effets possibles sur les sorties, les accès et les décisions critiques, et recommande validation d’entrée/sortie, séparation du contenu externe, moindre privilège, approbation humaine et tests adversariaux : [OWASP, LLM01:2025 Prompt Injection](https://genai.owasp.org/llmrisk/llm01-prompt-injection/).
- **Confidentialité et rétention.** Minimiser les données, masquer secrets et données personnelles avant envoi au modèle, isoler les sessions et ne pas persister automatiquement les objections comme mémoire réutilisable. Définir TTL, contrôle d’accès, suppression et audit des exports.
- **Sortie vérifiable.** Contrôler le schéma, les citations, les doublons, la longueur, les affirmations absolues et les appels à l’action. Une citation doit être récupérable et correspondre à l’affirmation ; sinon marquer « non vérifié ». Ne pas afficher un pourcentage de confiance sans définition et calibration.
- **Supervision et arrêt.** Montrer le plan et les sources avant toute utilisation d’outil, offrir pause, abandon et reprise, plafonner tours, tokens, durée et coût. En cas d’incertitude ou de conflit, suspendre et demander l’humain plutôt que combler le manque par invention.
- **Évaluation continue.** Constituer un jeu de cas anonymisés : décisions réelles et contrefactuelles, risques évidents et subtils, données contradictoires, injection dans un document, informations sensibles et décisions à fort impact. Mesurer couverture des hypothèses, pertinence des questions, taux d’hallucination, fausses alertes, citations valides, comportement d’arrêt et coût. Le profil NIST GenAI est un cadre volontaire de gestion et d’évaluation des risques sur le cycle de vie : [NIST, AI RMF: Generative AI Profile](https://www.nist.gov/publications/artificial-intelligence-risk-management-framework-generative-artificial-intelligence).

## Maturité, dépendances et limites

La maturité du cas NXUS est **conceptuelle et opérationnelle au niveau conversationnel**, pas une spécification de production : un besoin clair, un prompt reproductible et un livrable attendu, mais pas de contrat de données, d’évaluation, de sécurité ou de gouvernance public. Le label « Intermédiaire / Assisté » implique un humain dans la boucle et convient à un MVP sans outils.

La dépendance principale est le modèle conversationnel (NXUS référence Claude et ChatGPT), mais les performances varieront selon modèle, version, langue, contexte et paramètres. La qualité dépend davantage de la qualité de la fiche d’entrée et des preuves que de la formulation « avocat du diable ». L’ajout de RAG, de plusieurs agents ou de mémoire augmente l’attaque et la complexité ; il ne doit intervenir qu’après mesure du MVP.

Le contradicteur ne peut pas garantir l’exhaustivité. Il peut être d’accord avec la prémisse, inventer un risque, manquer un risque rare, ou renforcer le biais de l’utilisateur. En droit, finance, santé, sécurité ou ressources humaines, la sortie doit être un support de préparation à faire relire par un professionnel compétent. Le modèle ne doit pas fournir de conclusion présentée comme avis expert, ni se substituer à l’autorité de décision.

## Découpage recommandé

**À adopter maintenant :** workflow exposer → reformuler → challenger → questions → réponse humaine → synthèse ; entrée et sortie structurées ; séparation faits/hypothèses/inférences ; aucune action externe ; logs, rétention minimale, tests d’injection et métriques de qualité.

**À ajouter ensuite, sous contrôle :** recherche documentaire en lecture seule avec citations ; second évaluateur ; checkpoints et reprise ; catalogues de scénarios ; comparaison de modèles ; approbation humaine pour tout outil non strictement lecture seule.

**À éviter ou isoler :** agent multi-outils autonome ; mémoire globale ; scraping sans provenance ; score de confiance décisionnel ; écriture dans les systèmes métier ; usage de la contradiction comme preuve ; divulgation de prompts système ou de secrets ; boucles non bornées.

Le harness ainsi conçu préserve la valeur attestée par NXUS — rendre visible ce que le décideur ne s’est pas demandé — tout en empêchant que la rhétorique de l’avocat du diable soit confondue avec une expertise, une vérification factuelle ou une autorisation d’agir.

## Références

- [1]: https://nxus.fr/cas-usage-agents-ia/preparer-decision-avocat-du-diable « NXUS — Préparer une décision en mode avocat du diable »
- [2]: https://www.anthropic.com/research/trustworthy-agents « Anthropic — Trustworthy agents in practice »
- [3]: https://github.com/MicrosoftDocs/azure-ai-docs/blob/main/agent-framework/workflows/human-in-the-loop.md « Microsoft Agent Framework — Human-in-the-loop »
- [4]: https://cheatsheetseries.owasp.org/cheatsheets/AI_Agent_Security_Cheat_Sheet.html « OWASP — AI Agent Security Cheat Sheet »
- [5]: https://genai.owasp.org/llmrisk/llm01-prompt-injection/ « OWASP — LLM01:2025 Prompt Injection »
- [6]: https://www.nist.gov/publications/artificial-intelligence-risk-management-framework-generative-artificial-intelligence « NIST — AI RMF: Generative AI Profile »

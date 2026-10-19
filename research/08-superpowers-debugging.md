# Superpowers systematic debugging — évaluation pour un harness agentique

## Verdict opérationnel

**Superpowers systematic-debugging est une discipline de raisonnement et de vérification pour agents de développement, pas un moteur de diagnostic autonome ni une garantie de correction.** Sa règle centrale est explicite : « no fixes without root cause investigation first ». La compétence se déclenche pour un test en échec, un bug, un comportement inattendu, un problème de performance, de build ou d’intégration, et impose quatre phases séquentielles. Source officielle : [SKILL.md](https://raw.githubusercontent.com/obra/superpowers/main/skills/systematic-debugging/SKILL.md).

Pour un harness sécurisé, il faut **adopter le protocole de preuve** (reproduction, collecte d’erreurs, traçage du flux, hypothèse unique, changement minimal, test de régression et vérification finale), mais l’encapsuler dans des permissions, des limites de temps, un journal structuré et des validations indépendantes. Il faut traiter comme **optionnels** les exemples de scripts, la journalisation très verbeuse et les techniques spécifiques aux tests. Il faut **isoler ou refuser par défaut** toute action destructive, tout accès à des secrets, toute instrumentation qui les imprime, et toute prétention de l’agent à connaître une cause sans preuve.

## Ce que le sujet est réellement

Le dépôt `obra/superpowers` se présente comme un framework de skills composables et une méthodologie de développement pour agents de code. Le README décrit un ensemble plus large — conception, plans, worktrees, TDD, sous-agents, revue et finalisation — dont `systematic-debugging` n’est qu’une compétence de la section Debugging. Voir [README.md](https://github.com/obra/superpowers) et sa copie brute [README.md](https://raw.githubusercontent.com/obra/superpowers/main/README.md).

Le fichier de compétence est principalement un contrat textuel destiné à orienter le modèle : son frontmatter dit de l’utiliser avant de proposer une correction lorsqu’il rencontre un bug, un échec de test ou un comportement inattendu. Il n’expose pas une API RPC, un schéma JSON, un orchestrateur de sandbox, une base de données de symptômes ou un algorithme de causalité vérifié. Le dépôt contient toutefois des fichiers auxiliaires et des exemples, dont `root-cause-tracing.md`, `defense-in-depth.md` et `condition-based-waiting.md` : [répertoire public](https://github.com/obra/superpowers/tree/main/skills/systematic-debugging).

La page NXUS résume correctement le rôle pédagogique : reproduire et lire les erreurs, comparer à du code fonctionnel, tester une hypothèse avec un changement à la fois, puis écrire un test qui échoue avant le correctif. Elle insiste sur le caractère non négociable du diagnostic et recommande de coupler la compétence à TDD : [NXUS — Superpowers: systematic-debugging](https://nxus.fr/skills/superpowers-systematic-debugging). Cette page est une présentation tierce, utile pour l’orientation, mais le dépôt officiel est la source normative pour le contenu de la compétence.

## Mécanisme et étapes utiles

### 1. Investigation de la cause racine

Avant toute modification, l’agent doit lire l’intégralité des erreurs et de la stack trace, noter chemins, lignes et codes, puis obtenir une reproduction fiable. Il doit examiner les changements récents — diff Git, commits, dépendances, configuration et différences d’environnement. Si le système a plusieurs composants, il doit instrumenter chaque frontière pour voir ce qui entre, ce qui sort et comment la configuration se propage, puis exécuter une collecte ciblée afin de localiser la rupture. Enfin, il remonte le flux de données jusqu’à l’origine de la mauvaise valeur, plutôt que de corriger le point où l’exception apparaît. Source : [systematic-debugging/SKILL.md](https://raw.githubusercontent.com/obra/superpowers/main/skills/systematic-debugging/SKILL.md).

**Adoption recommandée dans le harness :** un état `INVESTIGATE` obligatoire avec champs structurés : symptôme, commande de reproduction, résultat attendu/observé, preuves brutes, changements suspects, composants traversés et niveau de confiance. Tant que les champs minimaux ne sont pas remplis, l’outil de modification doit rester indisponible.

### 2. Traçage arrière et instrumentation

`root-cause-tracing.md` formalise la remontée « symptôme → cause immédiate → appelant → valeur transmise → déclencheur original ». Il recommande une stack trace capturée avant l’opération dangereuse, avec contexte comme répertoire, `cwd`, environnement et horodatage. Il fournit également un script public de bisection de tests (`find-polluter.sh`) pour repérer le premier test qui pollue l’environnement. Source : [root-cause-tracing.md](https://raw.githubusercontent.com/obra/superpowers/main/skills/systematic-debugging/root-cause-tracing.md).

**Adoption recommandée :** instrumentation temporaire, explicitement marquée, à portée limitée et avec redaction des secrets. Le harness doit produire des événements `boundary_enter`, `boundary_exit`, `exception`, `stack_sample` et `hypothesis_tested`, plutôt que dépendre uniquement de texte libre. Les logs doivent être conservés avec identifiant de session, commit et hash de l’environnement.

**Garde-fou indispensable :** ne jamais recopier automatiquement des variables d’environnement, tokens, headers, secrets CI ou contenu de fichiers sensibles dans le journal. L’exemple officiel imprime des informations d’environnement dans un contexte de test ; dans un harness général, il faut le remplacer par une allowlist de noms et des valeurs masquées. Source de l’exemple : [root-cause-tracing.md](https://raw.githubusercontent.com/obra/superpowers/main/skills/systematic-debugging/root-cause-tracing.md).

### 3. Analyse comparative

La deuxième phase demande de trouver un exemple fonctionnel, de lire complètement la référence, de lister toutes les différences et de vérifier les dépendances, paramètres et hypothèses. Cela réduit les corrections intuitives basées sur un seul symptôme. Source : [systematic-debugging/SKILL.md](https://raw.githubusercontent.com/obra/superpowers/main/skills/systematic-debugging/SKILL.md).

**Adoption recommandée :** une sortie structurée `working_reference`, `broken_case`, `differences[]`, `dependency_assumptions[]` et `unknowns[]`. Le harness doit empêcher l’agent de transformer une analogie en preuve : une référence similaire est une piste, pas une causalité démontrée.

### 4. Hypothèse unique et expérimentation minimale

La troisième phase impose une hypothèse précise (« X est la cause racine parce que Y »), un changement minimal et une seule variable à la fois. Si le test échoue, l’agent doit revenir à l’analyse avec une nouvelle hypothèse au lieu d’empiler des correctifs. Lorsqu’il ne comprend pas, il doit le dire et rechercher davantage ou demander de l’aide. Source : [systematic-debugging/SKILL.md](https://raw.githubusercontent.com/obra/superpowers/main/skills/systematic-debugging/SKILL.md).

**Adoption recommandée :** chaque essai doit avoir un identifiant, une hypothèse falsifiable, un patch ou paramètre diffable, une commande, un résultat, une décision et un budget d’essais. Le système de fichiers doit être isolé par worktree ou snapshot afin de permettre rollback et comparaison.

### 5. Test de régression, correctif et vérification

La quatrième phase demande d’abord le cas de test minimal qui échoue, puis un seul correctif de la cause racine, sans refactorisation opportuniste. L’agent doit exécuter le test ciblé, la suite pertinente et une vérification avant de déclarer le succès. Le README place aussi `test-driven-development` et `verification-before-completion` parmi les skills de debugging/testing complémentaires : [README.md](https://raw.githubusercontent.com/obra/superpowers/main/README.md).

**Adoption recommandée :** séparer les capacités `diagnose`, `propose_patch`, `apply_patch` et `verify`. La déclaration « corrigé » doit être bloquée sans sortie de commande récente, code de sortie, tests exécutés et comparaison avec la reproduction initiale. Une revue ou un second agent peut vérifier le patch, mais ne doit pas remplacer les preuves d’exécution.

### 6. Seuil de trois échecs

Après moins de trois tentatives infructueuses, la compétence renvoie à l’investigation. À partir de trois, elle demande de questionner l’architecture et d’en discuter avec le partenaire humain, car les symptômes successifs peuvent signaler un couplage ou un design inadéquat. Source : [systematic-debugging/SKILL.md](https://raw.githubusercontent.com/obra/superpowers/main/skills/systematic-debugging/SKILL.md).

**Adoption recommandée, avec adaptation :** faire de ce seuil un circuit d’escalade, pas une vérité universelle. Le compteur doit distinguer les hypothèses réellement indépendantes, les essais non exécutés et les échecs d’infrastructure. À trois échecs, suspendre les mutations automatiques, demander une décision humaine ou lancer une revue architecture en lecture seule.

## Techniques auxiliaires

### Défense en profondeur

`defense-in-depth.md` propose quatre couches : validation à l’entrée, validation métier, garde-fou d’environnement et instrumentation de diagnostic. L’objectif est de rendre la mauvaise donnée structurellement impossible et de tester que les couches aval bloquent les contournements. Source : [defense-in-depth.md](https://raw.githubusercontent.com/obra/superpowers/main/skills/systematic-debugging/defense-in-depth.md).

**À adopter** pour les opérations à risque du harness : écriture de fichiers, exécution de commandes, création de worktrees, accès réseau, migrations et publication. Chaque couche doit avoir une politique explicite, un refus par défaut et un message exploitable. Les contrôles ne doivent pas être uniquement des prompts : ils doivent être appliqués par le runtime.

### Attente fondée sur une condition

`condition-based-waiting.md` remplace les `sleep` arbitraires par un polling d’une condition réelle, avec intervalle raisonnable, état relu à chaque tour et délai maximal explicite. Il reconnaît l’exception des tests qui mesurent un comportement temporel, où un délai documenté peut être correct. Source : [condition-based-waiting.md](https://raw.githubusercontent.com/obra/superpowers/main/skills/systematic-debugging/condition-based-waiting.md).

**À adopter** pour les tests asynchrones et les opérations de harness, avec timeout global, budget CPU et annulation. **À isoler** lorsque la condition interrogée a des effets de bord ou lorsque le polling peut devenir une attaque de charge. Le runtime doit proposer des primitives sûres (`wait_for_event`, `wait_for_state`) plutôt que laisser l’agent écrire des boucles illimitées.

## Interfaces et artefacts à matérialiser

Le dépôt public fournit surtout des artefacts Markdown : `SKILL.md` avec frontmatter `name`/`description`, fichiers de référence et exemples. Le guide de création de skills décrit cette structure, le namespace plat, la séparation des références lourdes et des scripts réutilisables, ainsi que des tests comportementaux par type de skill : [writing-skills/SKILL.md](https://raw.githubusercontent.com/obra/superpowers/main/skills/writing-skills/SKILL.md). Il ne fournit pas de protocole universel d’échange pour un harness tiers.

Pour un harness complet, matérialiser au minimum :

- **DebugCase** : identifiant, dépôt/worktree, commit, symptôme, reproduction, attentes, composants et classification de sensibilité.
- **EvidenceLog** append-only : commandes, sorties, codes retour, timestamps, hashes, traces et redactions.
- **HypothesisRecord** : hypothèse, justification, prédiction falsifiable, changement autorisé, résultat et décision.
- **PatchAttempt** : diff exact, fichiers touchés, approbation, rollback et compteur d’essais.
- **VerificationReport** : reproduction avant/après, tests ciblés, tests de non-régression, statut et limites résiduelles.
- **EscalationEvent** : non-reproductibilité, secrets détectés, timeout, troisième échec, conflit de permissions ou demande de modification hors périmètre.

Ces interfaces sont des recommandations de conception du harness, **pas des interfaces attestées du projet Superpowers**.

## Limites, dépendances et sécurité

**Limite de garantie.** Les instructions ne prouvent pas qu’une cause est réellement racine ; elles peuvent être ignorées, mal interprétées ou satisfaites par des tests insuffisants. Le harness doit donc imposer les transitions et vérifier les preuves hors modèle.

**Reproductibilité imparfaite.** Un bug environnemental, temporel ou externe peut rester non reproductible. La compétence autorise alors une gestion appropriée (retry, timeout, message d’erreur) après avoir documenté l’investigation, mais affirme aussi que beaucoup de cas « sans cause » sont des investigations incomplètes : [systematic-debugging/SKILL.md](https://raw.githubusercontent.com/obra/superpowers/main/skills/systematic-debugging/SKILL.md). Le harness doit conserver cette phrase comme heuristique, non comme taux statistique démontré.

**Dépendances d’exécution.** L’efficacité dépend du harness hôte : accès aux fichiers, Git, shell, tests, logs, worktrees, isolation et éventuellement sous-agents. Le README indique que l’installation et les mécanismes diffèrent selon le harness, et énumère des intégrations pour plusieurs agents ; cela n’implique pas une équivalence de comportement entre eux : [README.md](https://raw.githubusercontent.com/obra/superpowers/main/README.md). La note publique sur Hermes signale par exemple l’absence de hook post-compaction, et les notes de version documentent des corrections et adaptations par plateforme : [RELEASE-NOTES.md](https://raw.githubusercontent.com/obra/superpowers/main/RELEASE-NOTES.md).

**Maturité.** Le dépôt est actif et publié sous MIT ; le `package.json` consulté indique la version `7.0.0` et un paquet principalement composé de skills/bootstrap : [package.json](https://raw.githubusercontent.com/obra/superpowers/main/package.json), [LICENSE](https://raw.githubusercontent.com/obra/superpowers/main/LICENSE). Le dépôt affiche aussi des tests d’infrastructure et des évaluations comportementales via `superpowers-evals` dans les instructions de contribution : [README.md](https://github.com/obra/superpowers). Cela indique une maturité de projet et de méthode, mais **pas** une certification de sûreté, de couverture ou de performance pour un harness arbitraire. Les résultats « 1847 tests » et « 60 % → 100 % » sont des exemples rapportés dans les fichiers de compétence, non des benchmarks indépendants et généralisables : [root-cause-tracing.md](https://raw.githubusercontent.com/obra/superpowers/main/skills/systematic-debugging/root-cause-tracing.md), [condition-based-waiting.md](https://raw.githubusercontent.com/obra/superpowers/main/skills/systematic-debugging/condition-based-waiting.md).

**Télémetrie et confidentialité.** Le README décrit une fonctionnalité visuelle optionnelle qui charge par défaut le logo Prime Radiant et inclut la version, sans détails de projet, prompt ou agent ; il documente la désactivation par `SUPERPOWERS_DISABLE_TELEMETRY` et d’autres variables propres à Claude Code : [README.md](https://raw.githubusercontent.com/obra/superpowers/main/README.md). Dans un harness sensible, auditer cette fonctionnalité, désactiver toute télémétrie par défaut et contrôler les sorties réseau. Ne pas déduire de cette déclaration l’absence de toute télémétrie dans l’hôte ou dans les plugins tiers.

**Licence et chaîne de confiance.** La licence MIT autorise l’usage et la modification, avec logiciel fourni « as is » et sans garantie : [LICENSE](https://raw.githubusercontent.com/obra/superpowers/main/LICENSE). Pour une exécution agentique, épingler un commit ou une version vérifiée, examiner les scripts/hooks/plugins, scanner les dépendances et installer dans un environnement non privilégié. Ne pas exécuter directement un plugin téléchargé sans revue.

## Décision pour le harness

### À adopter obligatoirement

1. **Machine à états runtime** : `OBSERVE → REPRODUCE → TRACE → COMPARE → HYPOTHESIZE → TEST → PATCH → VERIFY`, avec refus de passer à `PATCH` sans preuve de diagnostic et de test.
2. **Isolation** : worktree/snapshot par cas, quotas CPU/mémoire/temps, réseau désactivé par défaut, permissions minimales et rollback atomique.
3. **Preuves structurées et redaction** : journaux append-only, hash du code/environnement, sorties de commandes et filtrage des secrets.
4. **Une hypothèse et une mutation à la fois**, diff vérifiable, compteur d’essais et arrêt après le seuil d’escalade.
5. **Vérification indépendante** : reproduction initiale, test de régression, suite pertinente et contrôle de fichiers modifiés avant toute déclaration de succès.
6. **Garde-fous runtime** inspirés de la défense en profondeur : entrées, logique métier, environnement et observabilité.

### Optionnel, à activer selon le risque

- Traçage très détaillé des stacks et des frontières pour les systèmes multi-composants.
- Bisection automatique de test pollueur.
- Sous-agent de revue ou de comparaison, avec contexte minimal et aucune permission d’écriture.
- Attente conditionnelle et helpers de polling pour les systèmes asynchrones.
- Couplage à TDD, worktrees et revue de code de l’écosystème Superpowers.

### À éviter ou isoler

- Corriger le symptôme, empiler des changements ou proposer un patch avant la phase d’investigation.
- Afficher `printenv`, secrets, tokens, données utilisateurs ou contenu sensible dans les logs.
- Laisser le modèle décider seul qu’un test est suffisant ou qu’une cause est « certaine ».
- Boucles de polling sans timeout, `sleep` arbitraires non justifiés, retries illimités et commandes destructives.
- Donner au skill des privilèges qu’il n’a pas besoin d’avoir ; les instructions Markdown ne remplacent pas les contrôles du runtime.
- Traiter le seuil « trois essais » comme une loi scientifique ou les exemples de résultats comme des garanties.
- Importer automatiquement tous les plugins/hooks multi-harness sans revue, pinning de version et test de compatibilité.

## Conclusion

La valeur transférable de `systematic-debugging` est une **discipline anti-devinette**, particulièrement utile pour réduire les correctifs de surface et rendre les décisions auditables. Sa valeur ne réside pas dans une capacité cachée ou un accès privilégié : les sources publiques consultées attestent d’un ensemble de documents Markdown et d’intégrations de plugins, pas d’un service autonome de causalité. Le harness doit donc compiler ses principes en transitions et politiques exécutables, fournir l’isolation et les preuves que le skill ne peut pas garantir seul, et conserver une voie d’escalade humaine lorsque la reproduction échoue, que les changements se multiplient ou que l’architecture est en cause.

## Références

- [NXUS — Superpowers: systematic-debugging](https://nxus.fr/skills/superpowers-systematic-debugging)
- [Dépôt officiel obra/superpowers](https://github.com/obra/superpowers)
- [README brut](https://raw.githubusercontent.com/obra/superpowers/main/README.md)
- [Skill systematic-debugging](https://raw.githubusercontent.com/obra/superpowers/main/skills/systematic-debugging/SKILL.md)
- [Root Cause Tracing](https://raw.githubusercontent.com/obra/superpowers/main/skills/systematic-debugging/root-cause-tracing.md)
- [Defense-in-Depth Validation](https://raw.githubusercontent.com/obra/superpowers/main/skills/systematic-debugging/defense-in-depth.md)
- [Condition-Based Waiting](https://raw.githubusercontent.com/obra/superpowers/main/skills/systematic-debugging/condition-based-waiting.md)
- [Writing Skills](https://raw.githubusercontent.com/obra/superpowers/main/skills/writing-skills/SKILL.md)
- [Package metadata](https://raw.githubusercontent.com/obra/superpowers/main/package.json)
- [Release notes](https://raw.githubusercontent.com/obra/superpowers/main/RELEASE-NOTES.md)
- [MIT License](https://raw.githubusercontent.com/obra/superpowers/main/LICENSE)

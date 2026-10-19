# Skill DeepSec Security Gate de Rudy : évaluation pour un harness agentique

Le `deepsec-security-gate` de Rudy est une **checklist Markdown défensive de pré-livraison** pour des applications produites avec l’aide d’un agent IA. Il ne s’agit ni d’un scanner exécutable, ni d’un moteur de preuve, ni du projet open source `vercel-labs/deepsec`. Le fichier se décrit comme « inspiré de l’approche DeepSec » et interdit l’exploitation offensive ; le dépôt précise explicitement qu’il ne contient pas de code d’exploit, de contenu DeepSec privé ou de texte propriétaire. [Source du skill](https://raw.githubusercontent.com/rudy-io/agentic-saas-factory-skills/main/skills/deepsec-security-gate/SKILL.md) [Attribution du dépôt](https://raw.githubusercontent.com/rudy-io/agentic-saas-factory-skills/main/docs/ATTRIBUTION.md)

## Rôle réel et périmètre

Le rôle réel est celui d’un **quality gate de sécurité orienté erreurs fréquentes des applications générées par IA**. Il demande de décider entre `PASS`, `PASS AVEC RESERVES` et `FAIL`, puis de produire un rapport avec surface auditée, preuves, bloquants, risques par niveau et correctifs. Le prompt de lancement cible particulièrement les secrets, l’authentification faible, l’IDOR, les endpoints publics, le paiement, les données personnelles, les uploads, l’IA et les dépendances. [SKILL.md](https://github.com/rudy-io/agentic-saas-factory-skills/blob/main/skills/deepsec-security-gate/SKILL.md)

La surface est large : secrets et configuration, auth et rôles, données personnelles, API et logique métier, paiements, fichiers, IA, dépendances, frontend et déploiement. La checklist couvre donc un **triage transversal avant exposition**, non une certification de sécurité. Elle ne fixe pas de niveau de risque quantifié, de matrice d’applicabilité, de seuil CVSS, de preuve minimale ou de politique d’exception. Un verdict produit par le texte seul doit être traité comme une décision de processus, pas comme la démonstration que l’application est sûre.

La distinction avec le DeepSec de Vercel est essentielle. Le projet officiel Vercel est un scanner agentique exécutable : `scan` repère des candidats par motifs, `process` mène l’investigation par agent, `revalidate` recontrôle les findings, puis `export` produit des sorties Markdown ou JSON. Il crée un état `.deepsec/`, peut reprendre un travail interrompu et propose une exécution distribuée optionnelle. [Dépôt officiel Vercel DeepSec](https://github.com/vercel-labs/deepsec) [Annonce Vercel](https://vercel.com/blog/introducing-deepsec-find-and-fix-vulnerabilities-in-your-code-base)

Rudy n’atteste pas intégrer ce scanner, ses matchers, son modèle de données, ses prompts ou ses commandes. Le dépôt Rudy dit au contraire qu’il n’adopte que l’idée générale d’une revue défensive structurée avant livraison. Il ne faut donc pas présenter le skill comme une version de Vercel DeepSec ou comme un accès à des prompts privés. [ATTRIBUTION.md](https://raw.githubusercontent.com/rudy-io/agentic-saas-factory-skills/main/docs/ATTRIBUTION.md)

## Mécanismes et étapes utiles

### 1. Verdict explicite et arrêt de livraison

Le triplet `PASS` / `PASS AVEC RESERVES` / `FAIL` est utile pour un harness parce qu’il fournit un contrat décisionnel simple. `FAIL` signifie ne pas déployer ni exposer ; `PASS AVEC RESERVES` permet un usage interne ou un test limité ; `PASS` autorise le livrable. Le harness doit toutefois rendre ces catégories **déterministes** : par exemple, secret détecté, endpoint admin non protégé ou webhook non vérifié doivent être des bloqueurs, alors qu’un contrôle documentaire manquant peut rester une réserve.

### 2. Revue par surfaces à haut rendement

Les contrôles les plus précieux sont ceux qui confrontent l’agent à des invariants serveur : protection côté serveur des routes privées et admin, vérification du rôle côté serveur, contrôle d’ownership pour chaque ressource, validation de schéma, prix de paiement fixé côté serveur, signature des webhooks, idempotence, stockage privé des uploads et validation de la sortie IA avant insertion critique. Ces éléments ciblent directement les erreurs de confiance dans le client et les erreurs de liaison entre données, identité et action. [SKILL.md](https://raw.githubusercontent.com/rudy-io/agentic-saas-factory-skills/main/skills/deepsec-security-gate/SKILL.md)

Le contrôle API est bien orienté vers les risques classiques. OWASP API Security Top 10 2023 décrit notamment la Broken Object Level Authorization, la Broken Function Level Authorization, la consommation non bornée de ressources, le SSRF et l’inventaire d’API incomplet. Le skill couvre plusieurs de ces classes, mais ne nomme pas explicitement SSRF, mass assignment/propriété d’objet, inventaire d’API ou consommation de ressources au niveau de détail OWASP. [OWASP API Security Top 10 2023](https://owasp.org/API-Security/editions/2023/en/0x11-t10/)

### 3. Vérifications autorisées et non offensives

Le texte autorise des tests contrôlés sur ses propres environnements : compte A contre données du compte B, non-admin contre action admin, payloads invalides et rate limit. C’est un bon garde-fou de portée. Le harness doit conserver cette règle et isoler les tests dans un environnement explicitement autorisé, avec comptes synthétiques, données factices, limites de temps et absence d’action destructive. Il ne doit pas transformer la checklist en instructions de sondage d’un tiers. [SKILL.md](https://github.com/rudy-io/agentic-saas-factory-skills/blob/main/skills/deepsec-security-gate/SKILL.md)

### 4. Commandes de départ, à traiter comme signaux

Les commandes proposées (`git status`, `git diff`, recherche `rg` de mots sensibles, `npm audit`, `pnpm audit`, `npm outdated`) sont des points de départ pragmatiques. Elles ne constituent pas des preuves suffisantes. Une recherche textuelle rate les secrets encodés, indirects ou stockés dans l’historique ; elle peut aussi créer des faux positifs. `npm audit` décrit lui-même une consultation du registre pour des vulnérabilités connues, dépendante d’un lockfile par défaut, et précise que certaines corrections exigent une intervention manuelle. Il envoie à l’endpoint d’audit une description de l’arbre de dépendances ; cet aspect doit entrer dans la politique de confidentialité du harness. [Documentation npm audit](https://docs.npmjs.com/cli/v10/commands/npm-audit)

### 5. Artefact de rapport

Le rapport attendu est Markdown, avec verdict, surface, preuves, bloquants, risques moyens/faibles, correctifs et décision. Pour un harness, il faut le compléter avec un manifeste machine-readable : identifiant du run, commit évalué, horodatage, environnement, règles exécutées, statut par contrôle (`pass`, `fail`, `not_applicable`, `unknown`), preuve référencée, sévérité, propriétaire, échéance et exception approuvée. La sortie humaine peut rester Markdown, mais le gate doit consommer un JSON versionné afin d’éviter qu’un agent reformule ou perde un blocage.

## Ce qui doit être adopté

1. **La frontière défensive et l’autorisation explicite.** Auditer uniquement ses propres dépôts ou un environnement autorisé ; ne pas exploiter, contourner ou sonder un tiers. Cette frontière doit être vérifiée avant l’exécution et rappelée dans les prompts.
2. **Le gate avant livraison ou déploiement.** Le harness doit faire dépendre le déploiement d’un verdict calculé, avec blocage par défaut en cas d’échec ou de preuve insuffisante sur un contrôle critique.
3. **Les invariants côté serveur.** Auth, rôles, ownership, prix, quotas, statut premium et webhooks doivent être contrôlés dans le code serveur et par des tests négatifs contrôlés, pas par la seule UI.
4. **Le traitement prudent des secrets.** Ne jamais imprimer un secret trouvé ; signaler chemin et ligne de façon redacted, recommander rotation/révocation, retrait du dépôt et vérification de l’historique. OWASP recommande centralisation, moindre privilège, audit, rotation automatisée et, lorsque possible, secrets dynamiques à courte durée. [OWASP Secrets Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html)
5. **La séparation entre finding et décision.** Un agent peut proposer un finding, mais la décision doit reposer sur des règles, des preuves et une revalidation séparée. La revalidation est attestée dans le DeepSec Vercel, pas dans le skill Rudy ; elle constitue donc une amélioration à intégrer au harness, non une capacité déjà fournie. [DeepSec Vercel](https://github.com/vercel-labs/deepsec)
6. **Le mapping à un référentiel stable.** Utiliser OWASP ASVS comme matrice de contrôles vérifiables pour les applications web. ASVS fournit une base de test des contrôles techniques et des exigences de développement sécurisé ; ses identifiants versionnés permettent de rattacher une preuve à une exigence précise. [OWASP ASVS](https://owasp.org/www-project-application-security-verification-standard/)

## Ce qui est optionnel

- **Le scan textuel initial** (`rg`, recherche d’extensions, diff) est utile comme filet rapide, mais doit être complété par un secret scanner, l’analyse de l’historique et l’inspection de la configuration CI/CD.
- **L’audit de dépendances** est utile lorsque le gestionnaire est identifié. Il faut sélectionner le bon outil et conserver le résultat avec sa date, son registre et son seuil. Ne pas exécuter automatiquement `npm audit fix --force` : npm précise que `--force` retire des protections et peut installer des changements majeurs. [npm audit](https://docs.npmjs.com/cli/v10/commands/npm-audit)
- **La 2FA admin, l’antivirus/modération des uploads, la sanitation d’images, la politique de source maps et les headers CSP/HSTS** dépendent de la surface et du niveau de risque ; ils doivent être `not_applicable` avec justification plutôt que silencieusement ignorés.
- **L’adoption du scanner Vercel DeepSec** peut être une couche complémentaire pour les dépôts suffisamment grands. Son coût peut atteindre des milliers voire des dizaines de milliers de dollars sur de grands dépôts selon sa documentation, et son blog indique un taux de faux positifs de l’ordre de 10–20 % dans leur expérience. Il faut donc plafonner coût/durée, isoler les clés et exiger la revalidation humaine ou agentique. [README DeepSec](https://github.com/vercel-labs/deepsec) [Annonce Vercel](https://vercel.com/blog/introducing-deepsec-find-and-fix-vulnerabilities-in-your-code-base)
- **Le mode PR/diff** est pertinent pour un contrôle incrémental, mais ne remplace pas un audit initial complet. La documentation DeepSec indique que `process --diff` retourne un code non nul lorsqu’un finding nouveau est produit, tout en excluant les findings préexistants. [Revue des changements DeepSec](https://github.com/vercel-labs/deepsec/blob/main/docs/reviewing-changes.md)

## Ce qui doit être évité ou isolé

- **Ne pas appeler le skill un scanner, une preuve de conformité ou un pentest.** Son contenu est une instruction de revue ; il ne démontre pas qu’un contrôle fonctionne.
- **Ne pas exécuter des commandes destructives ou de correction automatique dans le même agent privilégié que l’audit.** Les mises à jour de dépendances, migrations, rotations et déploiements doivent être des étapes séparées, approuvées et réversibles.
- **Ne pas donner à un agent d’audit un accès de production inutile.** Utiliser checkout en lecture seule, sandbox, réseau sortant limité, comptes synthétiques et secrets injectés uniquement si indispensables. Le modèle Vercel souligne que le scanner est comparable à un coding agent avec accès shell complet et recommande l’isolement sandbox ; il note également les risques de prompt injection via dépendances ou code vendorisé. [README DeepSec](https://github.com/vercel-labs/deepsec)
- **Ne pas mettre une clé AI dans un job CI qui exécute du code contrôlé par une pull request et possède en même temps des droits d’écriture.** La documentation PR de DeepSec recommande de séparer le job d’analyse sans écriture du job de commentaire, et de pinner les actions CI à des SHA complets pour un déploiement durci. [Reviewing changes](https://github.com/vercel-labs/deepsec/blob/main/docs/reviewing-changes.md)
- **Ne pas envoyer sans décision de minimisation les données, secrets, logs ou sources à un fournisseur LLM.** Le harness doit déclarer les flux sortants et proposer un mode sans IA pour les contrôles déterministes.
- **Ne pas exécuter automatiquement les actions irréversibles suggérées par l’IA.** Suppression de données, paiement, changement DNS, déploiement, migration et rotation doivent rester derrière une approbation et un plan de rollback.
- **Ne pas confondre l’inspiration publique “DeepSec” avec des capacités ou prompts privés.** Les seules capacités attestées pour Rudy sont celles du dépôt public et de son attribution.

## Maturité, dépendances et limites

Le dépôt Rudy est public, sous licence MIT, sans dépendance logicielle nécessaire au skill : c’est un fichier Markdown installable dans un répertoire de skills. Le README le présente comme des instructions pour des outils agentiques acceptant une convention `SKILL.md`, et précise qu’il ne contient ni credentials, ni infrastructure privée, ni données client. [README du dépôt](https://github.com/rudy-io/agentic-saas-factory-skills/blob/main/README.md) [Métadonnées GitHub](https://api.github.com/repos/rudy-io/agentic-saas-factory-skills)

Les métadonnées publiques consultées indiquent un dépôt de petite taille, créé le 2 juillet 2026, poussé le même jour, avec 4 étoiles, zéro issue ouverte et aucune release indiquée dans la réponse API. Cela suggère une **maturité documentaire/prototype public**, pas un niveau de validation opérationnelle ou une adoption étendue. Ces métriques sont un instantané de l’API au moment de la recherche et peuvent évoluer. [API GitHub du dépôt](https://api.github.com/repos/rudy-io/agentic-saas-factory-skills)

Les dépendances réelles sont organisationnelles : un agent capable de lire le dépôt et d’exécuter des contrôles, un environnement de test autorisé, un gestionnaire de secrets, un runner CI et des outils adaptés au langage/stack. La checklist n’impose ni framework, ni fournisseur, ni schéma de données, ni format machine-readable, ni intégration CI. Elle ne traite pas en profondeur la supply chain CI, le SSRF, la sécurité des runners, l’observabilité de détection, la gouvernance des modèles, le multi-tenant complexe ou la gestion des vulnérabilités dans le temps.

La section IA est utile mais courte : confidentialité des données, prompt système défensif, confirmation d’actions irréversibles, quotas, coûts, fallback, logs et validation de sortie. Elle ne couvre pas de manière structurée la prompt injection indirecte, l’empoisonnement de données/outils, l’exfiltration via tool calls, la séparation des privilèges d’outils, les sorties non fiables ou l’évaluation des agents. Le projet OWASP GenAI a élargi le périmètre du Top 10 LLM aux systèmes agentiques et applications GenAI ; cette ressource doit compléter la checklist, pas être remplacée par elle. [OWASP GenAI / Top 10 LLM](https://owasp.org/www-project-top-10-for-large-language-model-applications/)

## Architecture concrète recommandée pour le harness

1. **Intake immuable :** prendre un commit ou un artefact identifié, calculer son hash, relever la stack, les routes, les jobs et les flux de données ; refuser une cible non autorisée.
2. **Préflight déterministe :** vérifier secrets, fichiers sensibles, lockfile, configuration CI, permissions, build et tests sans envoyer de contenu au LLM.
3. **Matrice de contrôles :** compiler les items Rudy avec ASVS, OWASP API et GenAI ; chaque item reçoit applicabilité, méthode, sévérité et preuve attendue.
4. **Tests contrôlés :** exécuter les tests négatifs sur un environnement éphémère avec identités et données synthétiques. Aucun test d’exploitation externe.
5. **Revue agentique isolée :** fournir au modèle uniquement les fichiers nécessaires, avec outils en lecture seule par défaut, budget/durée plafonnés, réseau restreint et sortie structurée JSON.
6. **Revalidation indépendante :** demander à un second passage de vérifier chaque finding, son emplacement, son exploitabilité dans l’environnement autorisé et l’existence d’une mitigation ; classer `confirmed`, `rejected` ou `needs-human-review`.
7. **Décision par règles :** `FAIL` si un bloqueur confirmé existe ou si une preuve critique manque ; `PASS AVEC RESERVES` pour un risque accepté, borné et approuvé ; `PASS` uniquement lorsque les contrôles applicables sont passés.
8. **Publication séparée :** produire Markdown pour les humains et JSON signé/versionné pour CI ; ne jamais inclure de secret dans les deux sorties. Les actions correctives et le déploiement sont des jobs séparés, avec approbation, backup et rollback.
9. **Suivi :** conserver commit, règles, tool versions, findings, exceptions et statut de correction ; relancer en mode diff à chaque changement puis périodiquement en audit complet.

## Conclusion et recommandation

**À adopter :** la frontière défensive, le gate pré-livraison, le triplet de verdicts, les contrôles serveur contre IDOR/auth/paiement, le traitement redacted des secrets, les tests contrôlés et la structure de rapport. Ce sont des heuristiques simples et directement transposables.

**À intégrer autour du skill :** une matrice versionnée et machine-readable, des preuves reproductibles, une revalidation indépendante, un mapping ASVS/API/GenAI, des limites de coût et durée, l’isolation sandbox, une politique de secrets et un suivi de remédiation.

**À garder optionnel :** le scanner Vercel DeepSec, le mode diff, les matchers spécialisés et les contrôles dépendants du contexte. Ils ajoutent de la profondeur mais aussi coût, bruit et surface de confiance.

**À éviter :** toute prétention de certification, l’exécution automatique d’actions irréversibles, l’audit d’un tiers, le partage non minimisé de code/secrets avec un modèle, et l’usage d’une simple checklist ou d’un verdict LLM comme preuve unique. Le skill de Rudy est un bon **contrat de contrôle et de décision**, mais il doit être entouré de mécanismes déterministes et d’isolement pour devenir un harness agentique réellement sécurisé et exécutable.

## Références principales

- [SKILL.md public de Rudy](https://github.com/rudy-io/agentic-saas-factory-skills/blob/main/skills/deepsec-security-gate/SKILL.md)
- [Version brute du SKILL.md](https://raw.githubusercontent.com/rudy-io/agentic-saas-factory-skills/main/skills/deepsec-security-gate/SKILL.md)
- [README du dépôt Rudy](https://github.com/rudy-io/agentic-saas-factory-skills/blob/main/README.md)
- [Attribution Rudy](https://raw.githubusercontent.com/rudy-io/agentic-saas-factory-skills/main/docs/ATTRIBUTION.md)
- [API GitHub du dépôt Rudy](https://api.github.com/repos/rudy-io/agentic-saas-factory-skills)
- [Vercel DeepSec](https://github.com/vercel-labs/deepsec)
- [Annonce officielle Vercel DeepSec](https://vercel.com/blog/introducing-deepsec-find-and-fix-vulnerabilities-in-your-code-base)
- [DeepSec : revue des changements](https://github.com/vercel-labs/deepsec/blob/main/docs/reviewing-changes.md)
- [OWASP ASVS](https://owasp.org/www-project-application-security-verification-standard/)
- [OWASP API Security Top 10 2023](https://owasp.org/API-Security/editions/2023/en/0x11-t10/)
- [OWASP Secrets Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html)
- [OWASP GenAI / Top 10 LLM](https://owasp.org/www-project-top-10-for-large-language-model-applications/)
- [npm audit](https://docs.npmjs.com/cli/v10/commands/npm-audit)

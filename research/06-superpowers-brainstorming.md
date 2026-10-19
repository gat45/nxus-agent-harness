# Superpowers brainstorming : fiche Nxus et dépôt amont

## Verdict en une phrase

`brainstorming` est une **barrière de cadrage avant construction**, pas un moteur de conception autonome ni un mécanisme de sécurité complet. Il faut en reprendre le dialogue incrémental, la relecture par l’utilisateur, le dimensionnement du travail et le hard-gate d’approbation ; il faut isoler le compagnon visuel et compléter l’ensemble par des contrôles d’autorisation, de provenance, de sandbox et de validation indépendants.

## Sources et portée

La fiche Nxus présente le skill comme une « skill anti-tunnel » : inspection du contexte, questions une par une, 2–3 approches avec compromis, validation du design par sections, puis document de spécification ([fiche Nxus](https://nxus.fr/skills/superpowers-brainstorming)). La source normative est le dépôt public MIT [`obra/superpowers`](https://github.com/obra/superpowers), et en particulier le fichier [`skills/brainstorming/SKILL.md`](https://raw.githubusercontent.com/obra/superpowers/main/skills/brainstorming/SKILL.md). Rien dans ces sources ne justifie une prétention d’accès à des prompts privés, à du code privé ou à des capacités non exposées publiquement.

Le dépôt observé expose un framework de skills et une méthodologie de développement pour plusieurs harnesses. Son `package.json` public indique la version `7.0.0`, un paquet de skills/runtime bootstrap, et une extension Pi ; cela ne signifie pas que tous les harnesses partagent exactement la même implémentation ([`package.json`](https://raw.githubusercontent.com/obra/superpowers/main/package.json)). Les dates et versions doivent être revalidées avant un déploiement reproductible.

## Rôle réel et déroulé

Le skill commence par distinguer la demande claire et petite, exécutable immédiatement, d’une demande non triviale où l’intention manque. Son premier message prescrit une permission explicite de sauter les questions, puis **une seule question ouverte** portant sur une situation réelle ou une image concrète. Chaque tour doit finir par une question unique, sans questionnaire à choix multiples qui orienterait prématurément la personne ([`SKILL.md`](https://raw.githubusercontent.com/obra/superpowers/main/skills/brainstorming/SKILL.md)).

La conversation couvre, sans réciter une checklist, la nature de la chose à construire, la raison et le succès, les objectifs et non-objectifs, les anti-objectifs, les précédents, l’état courant, les contraintes et les détails importants. Le skill demande de clarifier tôt les choix de fabrication (plateforme, langage, bibliothèques, ressources) : un choix par défaut est présenté comme **la décision de l’agent**, et non comme un accord de l’utilisateur. Il peut proposer une reconnaissance du dépôt, des fichiers ou du web, mais cette recherche est offerte à l’utilisateur, pas présumée autorisée.

Avant de recommander, l’agent réfléchit à plusieurs idées et écarte les mauvaises ; il ne montre les comparaisons que si cela aide à décider. À mesure qu’un morceau est compris, il le « play back » en environ 200–300 mots, marque les suppositions comme telles, puis demande ce qui est faux ou incomplet. Cette boucle est la contribution centrale du skill : transformer une intention tacite en hypothèses corrigibles, au lieu de transformer directement une phrase en code.

Le travail est ensuite dimensionné : tâche rapide, petite modification décidée dans le chat, ou projet nécessitant un document de design. Si le périmètre grossit, le skill doit s’arrêter et changer de niveau. Pour un projet, le document doit expliciter intention, pourquoi, objectifs, non-objectifs, anti-objectifs, contraintes, choix décidés et questions restantes. Dans un dépôt logiciel, le chemin prescrit est `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md` ([`SKILL.md`](https://raw.githubusercontent.com/obra/superpowers/main/skills/brainstorming/SKILL.md)).

Avant remise du design, un sous-agent « builder » frais relit le document avec le point de vue de la personne qui devra construire. Ses questions sont triées : réponses déjà connues, décisions mineures prises par l’agent et questions qui changeraient réellement le produit. Le skill limite cette production de questions à un aller-retour. En l’absence de sous-agent, l’agent principal effectue lui-même la relecture.

Le hard-gate est explicite : **rien n’est construit avant l’approbation du descriptif complet**. « Construire » inclut code produit, scaffolding, installation de dépendances, création de projet et invocation d’un skill d’implémentation. Les seules exceptions sont l’opt-out explicite des questions et le spike explicitement accepté ; un spike reste jetable, sans promesse de tests ou de robustesse, et sa conservation repasse par le gate. Après approbation, un projet logiciel passe au skill de planification, pas directement à l’implémentation ([`SKILL.md`](https://raw.githubusercontent.com/obra/superpowers/main/skills/brainstorming/SKILL.md)).

## Artefacts et interfaces

Les artefacts textuels sont : le transcript de questions/réponses, les relectures intermédiaires, le design approuvé, puis le plan produit par l’étape suivante. Le design doit séparer les paroles de l’utilisateur des choix de l’agent. Le dépôt décrit ensuite une chaîne plus large : worktree isolé, plan en tâches courtes, exécution inline ou par sous-agents, TDD, revues et finition de branche ([`README.md` du dépôt](https://github.com/obra/superpowers)). Ces skills aval sont utiles pour un harness complet, mais ne sont pas fournis par le seul brainstorming.

L’interface minimale du brainstorming est conversationnelle : entrée utilisateur, question suivante, réponse, playback, approbation ou refus. Pour un projet, elle ajoute une écriture de fichier et une revue par sous-agent. Le guide de portage indique qu’un harness réellement supporté doit injecter automatiquement le bootstrap à chaque session, disposer d’un mécanisme de découverte/invocation des skills, lire/écrire/éditer des fichiers et exécuter des commandes ; la délégation, les todos et le web sont dégradables. L’injection doit passer par le mécanisme d’installation du harness, sans modifier les fichiers globaux de l’utilisateur ([`porting-to-a-new-harness.md`](https://raw.githubusercontent.com/obra/superpowers/main/docs/porting-to-a-new-harness.md)).

Le dépôt distingue trois formes d’intégration : hook shell de début de session, plugin/extension en processus, ou fichier d’instructions fourni par l’extension. Il insiste sur un test à marqueur unique : ne pas inférer qu’un événement ou un `@include` fonctionne ; vérifier que le contenu arrive effectivement au modèle sans tool-call opportuniste ([`porting-to-a-new-harness.md`](https://raw.githubusercontent.com/obra/superpowers/main/docs/porting-to-a-new-harness.md)).

## Compagnon visuel : utile mais à isoler

Le compagnon visuel est optionnel et doit être proposé uniquement lorsque voir est meilleur que lire : maquette, disposition, diagramme, séquence ou comparaison visuelle. Les exigences conceptuelles, arbitrages textuels, périmètre et décisions techniques restent dans le terminal ([`visual-companion.md`](https://raw.githubusercontent.com/obra/superpowers/main/skills/brainstorming/visual-companion.md)).

Techniquement, un serveur surveille un répertoire HTML, sert le fichier le plus récent et écrit les clics dans `state_dir/events` sous forme JSONL. Le guide impose une clé dans l’URL, déconseille de partager une URL sans cette clé, demande de vérifier la vivacité du serveur avant chaque écran et prévoit arrêt après inactivité. Avec `--project-dir`, les contenus persistent dans `.superpowers/brainstorm/`; sans cela, ils vont dans `/tmp` ([`visual-companion.md`](https://raw.githubusercontent.com/obra/superpowers/main/skills/brainstorming/visual-companion.md)).

Pour un harness sécurisé, ce serveur doit rester une capacité opt-in, avec bind réseau contrôlé, validation/échappement du HTML, clé non divulguée dans les logs, expiration courte, nettoyage des fichiers et séparation claire entre événement de clic et approbation normative. Un clic n’est pas à lui seul une autorisation de construire. Le serveur est documenté comme zéro dépendance Node dans les release notes, avec suivi du processus parent et vérifications de vivacité ([`RELEASE-NOTES.md`](https://raw.githubusercontent.com/obra/superpowers/main/RELEASE-NOTES.md)); cela réduit la surface d’installation mais ne remplace pas une sandbox.

Le README signale aussi une télémétrie facultative du logo/version pour le compagnon visuel, désactivable par `SUPERPOWERS_DISABLE_TELEMETRY` et certains opt-out du harness ; il indique qu’aucune information de projet, prompt ou agent n’est envoyée. Cette affirmation doit être contrôlée par audit de la version vendue avant adoption et la télémétrie doit être désactivée par défaut dans un environnement sensible ([`README.md`](https://github.com/obra/superpowers)).

## Garde-fous, limites et risques

**Garde-fous à conserver.** Le dialogue une-question-à-la-fois évite de faire choisir l’utilisateur dans un cadre inventé par l’agent. Le playback, l’étiquetage des suppositions et l’approbation par section rendent les erreurs visibles. La distinction objectifs/non-objectifs/anti-objectifs capture les modes d’échec qui ne sont pas des bugs techniques. Le dimensionnement empêche de traiter un projet comme une modification triviale. Le hard-gate interdit les effets de bord avant approbation. Enfin, le builder check apporte une seconde lecture contextuellement isolée.

**Limites intrinsèques.** Le skill ne garantit pas que l’utilisateur comprenne tout, ne détecte pas une intention malveillante, ne vérifie pas la vérité des contraintes métier et ne remplace ni revue de sécurité, ni politique d’accès, ni tests. Le hard-gate est une instruction suivie par le modèle : le harness doit donc l’adosser à des contrôles techniques qui bloquent réellement écritures, installations, commandes réseau ou secrets tant qu’un état d’approbation signé n’existe pas. Une approbation de design n’est pas une approbation de plan, de code, de déploiement ou de transfert de données.

Le mécanisme de bootstrap est une dépendance critique. Le dépôt documente des harnesses qui ont des hooks, des plugins ou des fichiers d’instructions, ainsi que des cas sans événement de début de session où le bootstrap repose sur la description des skills. Le portage doit tester le comportement réel de chaque version ; une dérivation d’un harness ou un nom d’événement ressemblant à `SessionStart` ne suffit pas ([`porting-to-a-new-harness.md`](https://raw.githubusercontent.com/obra/superpowers/main/docs/porting-to-a-new-harness.md)).

La maturité est **avancée comme bibliothèque de workflow, mais non équivalente à une certification de sécurité**. Le dépôt a des tests de plugin (Bash/Node/Python) et des évaluations de comportement sur de vraies sessions LLM ; ces évaluations sont lentes et s’exécutent en modes permissifs, avec un risque explicite. Les tests statiques sont adaptés à la CI publique, tandis que les sessions réelles sont plutôt nocturnes ou déclenchées à la demande ([`testing.md`](https://raw.githubusercontent.com/obra/superpowers/main/docs/testing.md)). Les tests couvrent le comportement du dépôt et de certains harnesses, pas nécessairement le harness cible ni ses politiques de sécurité.

Le dépôt est multi-harness et MIT, mais chaque installation est séparée par harness et les noms d’outils, hooks, capacités de sous-agents et règles de background varient. Les dépendances effectives incluent le harness hôte, ses outils fichier/shell, Node pour le compagnon, Git/worktrees et, selon les workflows, un outil de délégation. Les release notes signalent aussi des limites de portage et des correctifs spécifiques à Windows, Hermes, Gemini, Antigravity et autres intégrations ([`README.md`](https://github.com/obra/superpowers), [`RELEASE-NOTES.md`](https://raw.githubusercontent.com/obra/superpowers/main/RELEASE-NOTES.md)).

## Décisions pour le harness agentique

### À adopter

1. **Un état de workflow explicite** : `exploration → playback → design-draft → builder-check → user-approval → plan`. Aucun outil à effet de bord ne doit passer à l’état suivant sans transition vérifiable.
2. **Le protocole conversationnel** : question ouverte initiale, une question par tour, playback corrigible, hypothèses marquées, objectifs/non-objectifs/anti-objectifs, options et compromis seulement après compréhension.
3. **Deux approbations distinctes au minimum** : design puis plan. Stocker l’identité de l’approbateur, l’horodatage, le hash du document et le périmètre approuvé ; invalider l’approbation si le document change.
4. **Une relecture indépendante et isolée** : le builder-check reçoit uniquement le design, les contraintes nécessaires et les outils explicitement autorisés, jamais les secrets ou un contexte inutile.
5. **Un portage par capacité prouvée** : test de marqueur pour injection de session, test de découverte/invocation du skill, test de lecture/écriture et test de shell. Refuser l’installation si l’injection automatique ne peut pas être garantie.
6. **Des artefacts traçables** : design immuable ou versionné, décisions de l’agent séparées des déclarations utilisateur, événements d’approbation append-only, journal des outils et provenance des fichiers.

### Optionnel

Le compagnon visuel peut être activé pour les sujets réellement spatiaux ou visuels, sous serveur éphémère et politique réseau stricte. Le spike peut être proposé pour apprendre vite, mais il doit rester dans un workspace jetable et porter visiblement le statut `throwaway`. Le choix inline versus sous-agents, le TDD, les worktrees et les revues du reste de Superpowers sont de bons modules optionnels selon le risque et le coût ; ils ne doivent pas être confondus avec la garantie de cadrage du brainstorming ([`README.md`](https://github.com/obra/superpowers)).

### À éviter ou isoler

Ne pas éditer `~/.config`, `AGENTS.md`, `GEMINI.md` ou un autre fichier personnel pour injecter le bootstrap : l’extension doit livrer son propre artefact par le mécanisme d’installation ([`porting-to-a-new-harness.md`](https://raw.githubusercontent.com/obra/superpowers/main/docs/porting-to-a-new-harness.md)). Ne pas traiter une simple phrase comme une approbation de design, ni « sounds good » comme validation d’un document jamais montré. Ne pas laisser un clic du navigateur, un fichier écrit par l’agent ou la présence d’un skill équivaloir à une permission d’exécuter du code.

Ne pas installer de dépendances, lancer de scaffolding, appeler un skill d’implémentation ou exécuter des commandes réseau avant le gate technique. Ne pas injecter automatiquement tout le contenu d’un dépôt ou de pages web dans le contexte : appliquer provenance, limites de taille, filtrage de secrets et défense contre l’injection indirecte. Ne pas supposer que les outils mentionnés dans un skill existent dans le harness ; le guide de portage demande de mapper les outils réels et de dégrader proprement les capacités absentes ([`porting-to-a-new-harness.md`](https://raw.githubusercontent.com/obra/superpowers/main/docs/porting-to-a-new-harness.md)).

## Conclusion

Pour la conception du harness, Superpowers brainstorming doit être adopté comme **protocole de clarification et de contrôle humain**, avec ses artefacts et son hard-gate, mais encapsulé dans une machine d’états et des permissions non contournables. Le compagnon visuel et les workflows aval doivent être des plugins isolés. La qualité du résultat dépendra davantage de la preuve d’intégration du harness cible, de l’immutabilité des approbations, de la sandbox et de la validation indépendante que de la formulation du prompt elle-même.

## Références

- [Nxus — « superpowers: brainstorming »](https://nxus.fr/skills/superpowers-brainstorming)
- [obra/superpowers — dépôt GitHub](https://github.com/obra/superpowers)
- [Brainstorming `SKILL.md`](https://raw.githubusercontent.com/obra/superpowers/main/skills/brainstorming/SKILL.md)
- [`using-superpowers/SKILL.md`](https://raw.githubusercontent.com/obra/superpowers/main/skills/using-superpowers/SKILL.md)
- [Porting to a new harness](https://raw.githubusercontent.com/obra/superpowers/main/docs/porting-to-a-new-harness.md)
- [Visual Companion Guide](https://raw.githubusercontent.com/obra/superpowers/main/skills/brainstorming/visual-companion.md)
- [Testing Superpowers](https://raw.githubusercontent.com/obra/superpowers/main/docs/testing.md)
- [Release notes](https://raw.githubusercontent.com/obra/superpowers/main/RELEASE-NOTES.md)
- [`package.json`](https://raw.githubusercontent.com/obra/superpowers/main/package.json)

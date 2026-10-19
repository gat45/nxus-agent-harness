# Questions ouvertes — écosystème morluto (2026-10-18)

## Anomalie de provenance : morluto/rea (stars/forks)

**Fait vérifié** (deux appels API GitHub publics indépendants, à ~5 minutes
d'écart, le chiffre augmente entre les deux) :

- `morluto/rea` créé le 2026-04-14 (environ 6 mois).
- stargazers_count: 320054 → 320056
- forks_count: 81172
- Pour comparaison, VS Code (des années d'existence, adoption massive réelle)
  a environ 170000 stars. Un outil CLI de niche créé il y a 6 mois avec
  presque le double est statistiquement extrême.

**Ce qui n'est PAS prouvé** : je n'ai pas pu examiner la liste des
stargazers (l'endpoint `GET /repos/{owner}/{repo}/stargazers` avec
`Accept: application/vnd.github.v3.star+json` pour avoir `starred_at`
exige une authentification que je n'ai pas dans cette session —
`401 Requires authentication`). Je n'ai donc PAS de preuve directe d'un
pic d'étoiles en rafale sur de jeunes comptes (signature typique des
campagnes de fake stars, voir arXiv:2412.13459 "Six Million (Suspected)
Fake Stars on GitHub").

**Statut** : `UNKNOWN` — deux explications également plausibles, aucune
confirmée par preuve directe :
1. Gonflage artificiel d'étoiles (pattern connu et documenté, voir
   arXiv:2412.13459).
2. Viralité réelle et rapide — un outil REA/MCP pour agents IA peut
   authentiquement "buzzer" en quelques mois si largement partagé/repris
   (plusieurs cas similaires de croissance très rapide existent dans
   l'écosystème agents IA 2026). L'utilisateur du projet penche pour
   cette explication.

Sans l'historique temporel des stargazers (nécessite un `GITHUB_TOKEN`
que je n'ai pas dans cette session), je ne peux départager les deux. Je
ne traite donc PAS ceci comme une preuve de malveillance — seulement
comme une raison de ne pas étendre le périmètre de `rea_inspect`
au-delà de ce qui est déjà strictement scopé (allowlist lecture seule),
par précaution ordinaire plutôt que par suspicion arrêtée.

**Pourquoi ça compte pour nous** : `rea_inspect` est câblé dans le harnais
avec exécution subprocess réelle. Le scope actuel (allowlist de
sous-commandes lecture seule + cible exacte dans allowed_paths) limite
le risque même si l'outil ou son auteur s'avéraient peu fiables — mais
cette anomalie justifie de NE PAS étendre son périmètre (pas d'accès
device/adb, pas de sous-commande interactive) sans vérification
supplémentaire.

**Prochaine étape si investigation poursuivie** : obtenir un token GitHub
(`GITHUB_TOKEN`) pour interroger l'endpoint stargazers avec timestamps et
chercher un pic temporel anormal + des comptes à faible activité/âge.

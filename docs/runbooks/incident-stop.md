# Runbook — Arrêt d’urgence

Le `kill switch` doit être invoqué hors modèle dès qu’un run dérive du plan, détecte un secret, produit un comportement inattendu ou reçoit une instruction non fiable visant à élargir ses droits.

Effets attendus :

1. activer le flag de policy `kill_switch` ;
2. révoquer tous les grants non consommés ;
3. faire passer le run vers `ABORTED` ;
4. empêcher toute reprise automatique ;
5. préserver audit, manifeste et workspace pour la revue humaine ;
6. analyser les écarts avant toute reprise avec un nouveau plan et de nouvelles approbations.

Ne jamais « reprendre » un grant déjà consommé ou expiré. Le MVP ne lance pas de processus enfant ni de job réseau ; les futures intégrations devront enregistrer leurs handles afin de permettre une annulation réelle et vérifiable.

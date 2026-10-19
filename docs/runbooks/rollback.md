# Runbook — Rollback R1

Le MVP ne modifie que `runs/<tenant>/<run>/workspace/`. Le rollback d’un brouillon consiste donc à :

1. conserver `PLAN.md`, `plan.manifest.json`, `audit.jsonl` et `verification.json` comme preuve ;
2. supprimer ou restaurer uniquement le fichier indiqué dans `allowed_paths` ;
3. ajouter un événement d’audit explicitant l’opérateur, la raison et le hash avant/après ;
4. ne jamais modifier le dossier de contrôle du harness à partir du workspace ;
5. rejouer les contrôles de scope et de chaîne d’audit.

Un rollback de production, migration, paiement, e-mail, DNS ou déploiement n’est pas implémenté. Ces actions restent hors périmètre jusqu’à l’existence d’un runbook spécifique, d’un backup vérifié et d’une capacité idempotente.

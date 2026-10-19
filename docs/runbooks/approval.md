# Runbook — Approbation exacte

Avant d’approuver, l’opérateur vérifie :

1. l’**objectif** et les critères d’acceptation ;
2. le `PLAN.md` et les opérations du manifeste ;
3. les chemins, ressources et outils autorisés ;
4. le niveau de risque et l’absence de réseau/shell/secret/effet externe ;
5. la vérification déclarée et le rollback proposé ;
6. l’expiration du grant et l’identité de l’approbateur.

Un grant n’est valide que pour un unique `run_id`, un `manifest_hash`, un `tool_id` et le hash des arguments normalisés. Toute modification implique une nouvelle approbation. Une phrase d’accord dans une conversation n’est pas un grant technique.

Pour le MVP, seule l’écriture locale R1 dans le workspace du run nécessite un grant. Les actions R3/R4 restent refusées ; aucune approbation ne peut les rendre actives sans ajout explicite du connecteur et de sa policy.

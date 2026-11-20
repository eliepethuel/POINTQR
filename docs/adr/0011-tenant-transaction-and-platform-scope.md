# ADR-0011 — Transaction par requête et périmètre « plateforme »

- Statut : accepté
- Date : 2026-11-20
- Complète : ADR-0004

## Contexte
`ATOMIC_REQUESTS` n'enveloppe que la vue : l'authentification JWT, qui lit l'utilisateur sous RLS,
s'exécute avant. De plus, DRF annulerait la transaction sur une réponse 4xx, ce qui effacerait
les pointages refusés que le cahier des charges impose d'enregistrer (EF-21).

## Décision
1. `TenantMiddleware` résout l'entreprise (claim JWT, puis sous-domaine, puis en-tête
   `X-Company-Code`), ouvre **une transaction par requête** et y fixe
   `set_config('app.current_tenant', …, true)`. Les réponses 5xx sont annulées, les 4xx validées.
2. `tenant_context()` sert aussi aux tâches Celery, aux consumers WebSocket et aux tests ; il
   restaure la valeur précédente en sortie (contextes imbriqués dans une même transaction).
3. Périmètre **plateforme** (`app.platform_admin = on`) pour l'équipe éditeur : politiques RLS en
   **lecture seule** sur les données des clients (statistiques). Les politiques d'écriture exigent
   l'entreprise courante : le super-admin ne peut pas modifier un pointage d'un client.
4. Lignes à `company_id` NULL : « partagées » (jours fériés nationaux, lisibles par tous) ou
   « plateforme » (comptes super-admin, journal d'audit éditeur), selon la table.
5. Plutôt qu'une seconde connexion `BYPASSRLS`, ce périmètre reste soumis à RLS.
6. Verrouillage après 5 échecs par **identifiant** (django-axes) ; les IP sont limitées par le
   throttling DRF pour ne pas bloquer tout un bureau derrière une même adresse NAT.

## Conséquences
Les erreurs métier sont levées après la sortie du contexte quand un compteur d'échecs doit être
conservé (connexion, code TOTP). La CI exécute les tests avec un rôle non superutilisateur.

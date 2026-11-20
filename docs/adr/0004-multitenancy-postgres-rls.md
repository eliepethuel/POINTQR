# ADR-0004 — Multi-entreprises par Row Level Security PostgreSQL

- Statut : accepté
- Date : 2026-11-20

## Contexte
Le risque n° 1 du cahier des charges est la fuite de données entre entreprises (ENF-07, R8).

## Décision
1. Toutes les tables, sauf `Company` et `Subscription`, portent `company_id`.
2. RLS `ENABLE` **et** `FORCE` sur ces tables ; politique
   `company_id = current_setting('app.current_tenant', true)::uuid` (lecture et écriture).
3. Un middleware résout l'entreprise : sous-domaine (`slug.pointqr.ci`, `slug.localhost` en local),
   sinon claim `company_id` du JWT, sinon en-tête `X-Company-Code` (apps mobiles). Il exécute
   `SET LOCAL app.current_tenant` dans la transaction de la requête (`ATOMIC_REQUESTS = True`).
4. Même mécanisme (gestionnaire de contexte `tenant_context`) dans Celery et Channels.
5. Le rôle PostgreSQL de l'application n'est ni superuser ni `BYPASSRLS`. Le super-admin utilise une
   connexion séparée (alias `admin`), limitée aux vues de gestion des entreprises.
6. Défense en profondeur : `TenantManager` filtre aussi au niveau ORM.
7. Un test parcourt **toutes** les routes enregistrées et vérifie qu'un objet d'une autre entreprise renvoie 404.

## Conséquences
Une requête sans entreprise ne voit aucune ligne (le paramètre vaut NULL). Les migrations s'exécutent
avec le rôle propriétaire, l'application avec le rôle restreint.

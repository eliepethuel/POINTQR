# ADR-0012 — Pool de connexions PostgreSQL sous ASGI

- Statut : accepté
- Date : 2026-11-21
- Complète : ADR-0004, ADR-0011

## Contexte
L'API tourne sous ASGI (Channels pour le tableau de bord temps réel). Les vues Django
synchrones y sont exécutées dans des threads d'exécution : avec `CONN_MAX_AGE > 0`, chaque
thread garde sa propre connexion persistante. Au test de charge R10 (300 téléphones, ~2 000
pointages/min), les connexions se sont accumulées jusqu'au refus de PostgreSQL
(« remaining connection slots are reserved… ») : 91 % de réponses 500.

## Décision
1. `CONN_MAX_AGE = 0` et **pool psycopg** intégré à Django 5.1+ (`OPTIONS.pool`), réglable par
   `DB_POOL`, `DB_POOL_MIN`, `DB_POOL_MAX` (10 par défaut), `DB_POOL_TIMEOUT`.
2. Dimensionnement : `workers × DB_POOL_MAX` reste sous `max_connections` (100 par défaut).
3. Les tests désactivent le pool (le lanceur de tests crée puis détruit sa base).

## Sécurité multi-entreprise
Le périmètre RLS est posé par `set_config(..., true)`, donc **local à la transaction** ouverte
par `TenantMiddleware`. Une connexion rendue au pool ne porte plus aucune entreprise : la requête
suivante, même sur la même connexion, repart d'un périmètre vide (`pointqr_current_tenant()` NULL
→ aucune ligne visible).

## Conséquences
Avec le pool, R10 passe : 1 987 pointages/min, p95 130 ms, 0 % d'erreur (voir
`docs/PERFORMANCE.md`). Le nombre de connexions ouvertes est borné et prévisible.

# ADR-0014 — Pile conteneurisée (phase 6)

- Statut : accepté
- Date : 2026-11-21
- Complète : ADR-0010 (ticket PQR-011)

## Décision
`docker compose up -d --build` démarre toute la plateforme sur **http://localhost:8080** :

| Service | Image | Rôle |
|---|---|---|
| `postgres` | postgres:16-alpine | base ; au premier démarrage, `infra/postgres/create-roles.sql` crée le propriétaire et le rôle applicatif (sans SUPERUSER ni BYPASSRLS), comme en natif |
| `redis` | redis:7.4-alpine | cache, anti-rejeu, Celery, Channels |
| `migrate` | pointqr-api | migrations avec le rôle propriétaire, puis s'arrête |
| `backend` | pointqr-api | uvicorn (ASGI : HTTP + WebSocket), `WEB_CONCURRENCY` workers, pool de connexions (ADR-0012) |
| `worker`, `beat` | pointqr-api | Celery (rapports, notifications, purge de rétention) |
| `web` | pointqr-web | nginx : application Angular + proxy `/api` et `/ws` vers `backend`, en-têtes de sécurité |
| `mailpit` | axllent/mailpit | boîte de réception locale des e-mails (http://localhost:8025) |
| `seed` (profil `demo`) | pointqr-api | données de démonstration |

1. **Une seule image API** pour l'API, le worker et beat : utilisateur non root (uid 1001),
   dépendances figées par `uv.lock`, aucune bibliothèque système pour les PDF (ADR-0013).
2. **Un seul point d'entrée** : nginx sert l'application et relaie l'API sur la même origine
   (aucun CORS nécessaire) ; le sous-domaine de l'entreprise est transmis tel quel (ADR-0004).
3. **CSP stricte** : `script-src 'self'` plus l'empreinte SHA-256 des scripts en ligne de
   `index.html` (chargeur du CSS critique d'Angular), calculée à la construction de l'image
   (`frontend/nginx/csp-hashes.mjs`). Sans elle, la feuille de style resterait en `media=print`.
4. **IP du client** derrière le proxy : uvicorn `--proxy-headers` et `NUM_PROXIES=1` pour le
   throttling (ENF-11).
5. Les secrets viennent de `.env` (`tasks.ps1 env` / `make env`) ; le compose refuse de
   démarrer s'ils manquent.
6. Les fichiers (rapports, justificatifs) sont sur un volume partagé par l'API et le worker ;
   un stockage S3 s'active par `S3_ENDPOINT_URL` (ADR-0009, ticket PQR-012 pour le service).
7. La **CI** construit les deux images, démarre la pile et vérifie : santé, page servie, CSP
   conforme aux scripts réels, routes profondes, erreurs RFC 7807, schéma OpenAPI, rôle
   applicatif sans contournement RLS, worker Celery joignable.

## Conséquences
HTTPS se place devant le service `web` en production (répartiteur ou proxy de l'hébergeur) ;
`SECURE_SSL_REDIRECT` est alors laissé à sa valeur par défaut (vrai).

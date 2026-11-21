# Performance — mesures de la phase 5

## R10 — 2 000 pointages par minute, 95 % en moins de 500 ms

Scénario `infra/locust/locustfile.py` : chaque utilisateur simulé est un téléphone d'agent lié
qui scanne le QR de la borne (jeton `PQR1` signé comme le fait la borne, renouvelé toutes les
30 s) toutes les 7 à 11 s, position dans la zone du site. Toute la chaîne de contrôle est
exercée : jeton, anti-rejeu Redis, téléphone lié, géorepérage, doublon < 2 min (RG-06), calcul
du statut, enregistrement, recalcul de la journée, événement temps réel.

```powershell
cd backend
uv run python manage.py prepare_loadtest --agents 300
uv run locust -f ../infra/locust/locustfile.py --host http://127.0.0.1:8001 --headless -u 300 -r 30 -t 180s --reset-stats --csv ../infra/locust/r10
```

Le serveur testé : `uvicorn config.asgi:application --workers 6`, `DJANGO_DEBUG=false`,
`CHECKIN_IP_RATE=6000/min` (tous les téléphones simulés partagent une seule adresse IP).
`prepare_loadtest` refuse de s'exécuter si `DEBUG` est faux : il écrit la clé de borne et des
jetons d'accès dans un fichier local ignoré par Git.

| Mesure (3 min, après montée en charge) | Résultat | Cible |
|---|---|---|
| Débit | 1 987 pointages/min | 2 000/min |
| Médiane | 46 ms | — |
| p95 | **130 ms** | < 500 ms |
| p99 | 250 ms | — |
| Erreurs | 0 % | — |

Poste de développement Windows (8 cœurs), PostgreSQL 16, Garnet en guise de Redis, Locust
sur la même machine. Le script se termine avec un code d'erreur si p95 > 500 ms ou
erreurs > 1 %.

Le premier essai a révélé un épuisement des connexions PostgreSQL sous ASGI, corrigé par un
pool de connexions (ADR-0012).

## Page d'accueil — LCP

Build de production servi en statique, Chrome mobile (Lighthouse) :

| Mesure | Résultat | Cible |
|---|---|---|
| LCP | 0,73 s | < 2,5 s |
| CLS | 0,00 | < 0,1 |
| Accessibilité / SEO | 100 / 100 | ≥ 90 |
| Bonnes pratiques | 96 | ≥ 90 |

Le titre du héros est animé en `transform` seulement : il est peint dès la première image,
GSAP et ScrollTrigger sont chargés après coup. Bundle initial : ~100 kB transférés.

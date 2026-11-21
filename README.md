# PointQR

> **Le pointage qui ne ment pas.**

PointQR est une plateforme SaaS multi-entreprises de pointage par **QR code dynamique** :
l'heure est fixée par le serveur, jamais par l'agent. Conçue pour les administrations et
entreprises de Côte d'Ivoire, sans aucune donnée biométrique.

| Dossier | Contenu |
|---|---|
| `backend/` | API Django 5.2 LTS + DRF, Channels (WebSocket), Celery |
| `frontend/` | Angular 22 : site vitrine, back-office, mode borne, application agent (PWA) |
| `infra/` | rôles PostgreSQL, scripts d'environnement, test de charge Locust |
| `docs/` | plan, décisions d'architecture (`adr/`), backlog, mesures de performance |

## Fonctionnalités

- **Pointage en 4 modes** : A borne + téléphone (QR renouvelé toutes les 30 s), B QR personnel
  scanné par la borne, C badge imprimé, D QR de site affiché seul.
- **Anti-fraude** : jeton HMAC à durée de vie courte, anti-rejeu Redis, un téléphone par agent
  (changement validé par le RH), géorepérage, détection de position simulée, Wi-Fi en second
  facteur, doublons < 2 min ignorés. Chaque refus est enregistré avec son motif.
- **Règles de calcul** RG-01 à RG-15 : retards depuis l'heure prévue, tolérance, horaires de
  nuit, jours fériés, heures supplémentaires, clôture mensuelle des périodes.
- **Borne hors-ligne** : file locale (IndexedDB) envoyée au retour du réseau, pointages
  marqués « hors-ligne ».
- **Back-office** : tableau de bord temps réel (WebSocket), agents (import Excel), sites sur
  carte, horaires, téléphones, demandes et circuit de validation, rapports Excel/PDF planifiés,
  journal d'audit, palette de commandes (Ctrl+K), thème clair/sombre.
- **Multi-entreprise** : isolation par Row Level Security PostgreSQL, espace « plateforme »
  pour l'éditeur (lecture seule sur les données clients).
- **Sécurité** : JWT court + refresh en cookie HttpOnly, TOTP obligatoire pour admin/RH/éditeur,
  verrouillage après 5 échecs, journal d'audit en ajout seul, erreurs RFC 7807.

## Prérequis

- [uv](https://docs.astral.sh/uv/) (installe Python 3.13 automatiquement)
- Node.js 22.22+ ou 24+
- PostgreSQL 16
- Un serveur compatible Redis : [Garnet](https://microsoft.github.io/garnet/) sous Windows
  (`dotnet tool install --global garnet-server`), Redis 7 sous Linux/macOS

Le développement se fait en natif ; pour lancer toute la plateforme en conteneurs, voir
« Avec Docker » (seuls Docker et un fichier `.env` sont alors nécessaires).

## Installation

Windows (PowerShell) :

```powershell
.\tasks.ps1 env       # .env avec des secrets aléatoires (ajustez POSTGRES_PORT si besoin)
.\tasks.ps1 db-init   # base + rôles (demande le mot de passe du superutilisateur PostgreSQL)
.\tasks.ps1 install   # dépendances backend et frontend
.\tasks.ps1 migrate
.\tasks.ps1 seed      # données de démonstration (quelques minutes : historique de 2 mois)
.\tasks.ps1 dev       # ouvre API, worker, beat, front et Garnet dans des fenêtres séparées
```

Linux / macOS : mêmes cibles avec `make` (`make env db-init install migrate seed`, puis
`make api`, `make worker`, `make beat`, `make front` dans des terminaux séparés).

| URL | Service |
|---|---|
| http://localhost:4200 | Site vitrine |
| http://localhost:4200/connexion | Connexion au back-office |
| http://localhost:4200/kiosk | Mode borne (tablette d'entrée) |
| http://localhost:4200/agent | Application agent (PWA) |
| http://localhost:4200/plateforme | Espace éditeur (super-admin) |
| http://localhost:8000/api/docs/ | Documentation de l'API (Swagger) |
| http://localhost:8000/api/schema/ | Schéma OpenAPI 3 |

## Avec Docker

```powershell
.	asks.ps1 env           # ou make env : .env avec des secrets aléatoires
.	asks.ps1 docker-up     # docker compose up -d --build
.	asks.ps1 docker-seed   # données de démonstration (quelques minutes)
```

| URL | Service |
|---|---|
| http://localhost:8080 | application (site vitrine, back-office, borne, agent) et API sous `/api/` |
| http://localhost:8025 | e-mails envoyés (Mailpit) |

Services : PostgreSQL 16, Redis 7, migrations, API (uvicorn), worker et beat Celery, nginx,
Mailpit. Détails et choix de sécurité : [ADR-0014](docs/adr/0014-containerised-stack.md).
Arrêt : `.	asks.ps1 docker-down` (les volumes de données sont conservés).

## Comptes de démonstration

Données **fictives**, créées par `seed`. Mot de passe de tous les comptes :
`Demo-PointQR-2026`. Les comptes admin, RH et éditeur demandent un code TOTP : ajoutez le
secret `PQRDEMOPQRDEMOPQRDEMOPQRDEMOPQRD` à une application d'authentification.

| Entreprise (code) | Identifiant | Rôle |
|---|---|---|
| Ministère X (`MINX`) | `admin` | administrateur de l'entreprise |
| | `rh` | ressources humaines |
| | `manager` | responsable d'équipe |
| | `agent` | agent |
| | `auditeur` | lecture seule |
| PME Y (`PMEY`) | `admin`, `agent` | administrateur, agent |
| — | `editeur` | équipe PointQR (super-admin) |

Parcours conseillé (détaillé dans le [guide d'utilisation](docs/GUIDE_UTILISATEUR.md#16-essayer-avec-les-données-de-démonstration)) : connectez-vous en `rh` (MINX), ouvrez **Bornes**, générez un code
d'appairage et saisissez-le sur `/kiosk` ; connectez-vous en `agent` sur `/agent` dans un autre
navigateur ou un téléphone, liez le téléphone et scannez le QR de la borne. Le pointage apparaît
aussitôt sur le tableau de bord.

## Commandes utiles

| Commande | Rôle |
|---|---|
| `test`, `test-back`, `test-front` | tests (pytest + couverture, Vitest) |
| `lint`, `format` | ruff, mypy, ESLint, Prettier |
| `openapi` | exporte `backend/openapi.yaml`, le contrat d'API |
| `client` | régénère le client Angular typé (`frontend/src/app/api/`, jamais modifié à la main) |
| `db-reset` | recrée la base vide |
| `docker-up`, `docker-down`, `docker-seed` | pile complète en conteneurs |

## Recette

| Critère | Vérifié par |
|---|---|
| R1 à R5 — retard 22 min, photo du QR, téléphone d'un autre, heure du téléphone, borne hors-ligne | `backend/apps/attendance/tests/test_recette_pointage.py` |
| R6 — sortie oubliée, journée incomplète et notification | `backend/apps/attendance/tests/test_days.py`, `test_requests.py` |
| R7 — correction RH : l'original est conservé et audité | `backend/apps/requests_app/tests/test_requests.py` |
| R8 — aucune route ne renvoie un objet d'une autre entreprise | `backend/tests/test_r8_isolation.py` (toutes les routes) |
| R9 — rapport mensuel de 500 agents en moins de 30 s | `backend/apps/reports/tests/test_reports.py` |
| R10 — 2 000 pointages/min, p95 < 500 ms | `infra/locust/locustfile.py`, résultats dans [docs/PERFORMANCE.md](docs/PERFORMANCE.md) |

## Sécurité multi-entreprises

L'application se connecte avec un rôle PostgreSQL **sans** `SUPERUSER` ni `BYPASSRLS` : la
Row Level Security isole chaque entreprise au niveau de la base (ADR-0004, ADR-0011). Les
connexions sont mutualisées par un pool ; le périmètre de l'entreprise est local à chaque
transaction (ADR-0012).

## Documentation

- **[Guide d'utilisation](docs/GUIDE_UTILISATEUR.md)** : chaque écran, par rôle, et les motifs de refus
- [Plan de réalisation](docs/PLAN.md)
- [Décisions d'architecture](docs/adr/)
- [Backlog](docs/BACKLOG.md)
- [Performance](docs/PERFORMANCE.md)

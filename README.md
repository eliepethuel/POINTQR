# PointQR

> **Le pointage qui ne ment pas.**

PointQR est une plateforme SaaS multi-entreprises de pointage par **QR code dynamique** :
l'heure est fixée par le serveur, jamais par l'agent. Conçue pour les administrations et
entreprises de Côte d'Ivoire, sans aucune donnée biométrique.

| Dossier | Contenu |
|---|---|
| `backend/` | API Django 5.2 LTS + DRF, Channels (WebSocket), Celery |
| `frontend/` | Angular 22 (back-office, site vitrine, mode borne, PWA agent) |
| `infra/` | scripts de base de données et d'environnement |
| `docs/` | plan, décisions d'architecture (`adr/`), backlog |

## Prérequis

- [uv](https://docs.astral.sh/uv/) (installe Python 3.13 automatiquement)
- Node.js 22.22+ ou 24+
- PostgreSQL 16
- Un serveur compatible Redis : [Garnet](https://microsoft.github.io/garnet/) sous Windows
  (`dotnet tool install --global garnet-server`), Redis 7 sous Linux/macOS

Le développement se fait en natif ; la conteneurisation arrive en dernière phase (ADR-0010).

## Installation

Windows (PowerShell) :

```powershell
.\tasks.ps1 env       # .env avec des secrets aléatoires (ajustez POSTGRES_PORT si besoin)
.\tasks.ps1 db-init   # base + rôles (demande le mot de passe du superutilisateur PostgreSQL)
.\tasks.ps1 install   # dépendances backend et frontend
.\tasks.ps1 migrate
.\tasks.ps1 dev       # ouvre API, worker, beat, front et Garnet dans des fenêtres séparées
```

Linux / macOS : mêmes cibles avec `make` (`make env db-init install migrate`, puis `make api`,
`make worker`, `make front` dans des terminaux séparés).

| URL | Service |
|---|---|
| http://localhost:4200 | Application Angular |
| http://localhost:8000/api/docs/ | Documentation de l'API (Swagger) |
| http://localhost:8000/api/schema/ | Schéma OpenAPI 3 |

## Commandes utiles

| Commande | Rôle |
|---|---|
| `test`, `test-back`, `test-front` | tests (pytest + couverture, Vitest) |
| `lint`, `format` | ruff, mypy, ESLint, Prettier |
| `openapi` | exporte `backend/openapi.yaml`, le contrat d'API |
| `client` | régénère le client Angular typé (`frontend/src/app/api/`, jamais modifié à la main) |

## Sécurité multi-entreprises

L'application se connecte avec un rôle PostgreSQL **sans** `SUPERUSER` ni `BYPASSRLS` : la
Row Level Security isole chaque entreprise au niveau de la base (ADR-0004).

## Documentation

- [Plan de réalisation](docs/PLAN.md)
- [Décisions d'architecture](docs/adr/)
- [Backlog](docs/BACKLOG.md)

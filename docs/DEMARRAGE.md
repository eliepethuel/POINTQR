# Lancer PointQR

Il y a deux façons de lancer le projet :

| | **A. Avec Docker** | **B. En natif** |
|---|---|---|
| Pour | essayer ou présenter la plateforme | développer (rechargement à chaud, débogage) |
| À installer | Docker Desktop | uv, Node.js, PostgreSQL 16, Garnet ou Redis |
| Adresse | http://localhost:8080 | http://localhost:4200 |
| Premier lancement | ~10 min (construction des images) | ~15 min (installations) |

Dans les deux cas, les données de démonstration prennent quelques minutes à charger (deux mois
d'historique).

---

## A. Avec Docker (le plus simple)

### Prérequis

- **Docker Desktop**, démarré. Sous Windows, avec le moteur WSL 2.
- **Environ 6 Go libres** sur le disque de Docker (images et volumes).
- Le port **8080** libre ; le port 8025 sert à Mailpit.

### Lancement

Ouvrez PowerShell à la racine du projet (`Pointqr_App/`) :

```powershell
.\tasks.ps1 env           # crée .env avec des secrets aléatoires (une seule fois)
.\tasks.ps1 docker-up     # construit les images et démarre tous les services
.\tasks.ps1 docker-seed   # charge les données de démonstration (une seule fois)
```

Sous Linux ou macOS, les mêmes cibles existent avec `make` : `make env`, `make docker-up`,
`make docker-seed`. On peut aussi appeler Docker directement :

```sh
sh infra/scripts/init-env.sh
docker compose up -d --build
docker compose --profile demo run --rm seed
```

Ouvrez ensuite **http://localhost:8080**.

| Adresse | Contenu |
|---|---|
| http://localhost:8080 | site vitrine |
| http://localhost:8080/connexion | back-office |
| http://localhost:8080/kiosk | mode borne |
| http://localhost:8080/agent | application agent |
| http://localhost:8080/api/docs/ | documentation de l'API |
| http://localhost:8025 | e-mails envoyés par la plateforme (Mailpit) |

### Au quotidien

```powershell
docker compose ps                 # état des services
docker compose logs -f backend    # journaux de l'API (ou worker, beat, web, postgres)
.\tasks.ps1 docker-down           # arrêter ; les données sont conservées
.\tasks.ps1 docker-up             # relancer (reconstruit si le code a changé)
```

Pour **tout effacer** et repartir de zéro (base, fichiers, Redis) : `docker compose down -v`.
Attention, cette commande est irréversible.

Services démarrés : `postgres`, `redis`, `migrate` (s'arrête une fois les migrations faites),
`backend`, `worker`, `beat`, `web` et `mailpit`. Les détails sont dans
[ADR-0014](adr/0014-containerised-stack.md).

---

## B. En natif (pour développer)

### Prérequis

| Outil | Version | Installation (Windows) |
|---|---|---|
| uv | récent | `winget install astral-sh.uv` (installe aussi Python 3.13) |
| Node.js | **22.22+** ou 24+ | `winget install OpenJS.NodeJS.LTS` |
| PostgreSQL | **16** | installateur EDB ; noter le mot de passe du superutilisateur `postgres` et le port |
| Garnet (Redis) | récent | `winget install Microsoft.DotNet.SDK.8` puis `dotnet tool install --global garnet-server` |

Sous Linux ou macOS, remplacez Garnet par **Redis 7** (`apt install redis-server`,
`brew install redis`).

### Premier lancement (une seule fois)

Ouvrez PowerShell à la racine du projet :

```powershell
.\tasks.ps1 env
```

Cette commande crée `.env`. **Si PostgreSQL n'écoute pas sur 5432**, ouvrez `.env` et mettez le
bon port à trois endroits : `POSTGRES_PORT`, `DATABASE_URL` et `MIGRATION_DATABASE_URL`.

```powershell
.\tasks.ps1 db-init   # crée la base et les deux rôles ; demande le mot de passe de « postgres »
.\tasks.ps1 install   # dépendances Python et Node
.\tasks.ps1 migrate   # tables, sécurité RLS, jours fériés
.\tasks.ps1 seed      # données de démonstration (quelques minutes)
```

### Lancer

```powershell
.\tasks.ps1 dev
```

Cinq fenêtres s'ouvrent : Garnet, API, worker, beat et front. Attendez la ligne
« Application bundle generation complete » dans la fenêtre *front*, puis ouvrez
**http://localhost:4200**.

| Adresse | Contenu |
|---|---|
| http://localhost:4200 | application (vitrine, back-office, `/kiosk`, `/agent`) |
| http://localhost:8000/api/docs/ | documentation de l'API (Swagger) |

Les e-mails ne sont pas envoyés en natif : ils s'affichent dans la fenêtre *api* ou *worker*.

Pour lancer un seul service dans la fenêtre courante : `.\tasks.ps1 api`, `worker`, `beat`,
`front` ou `redis`. Pour arrêter, fermez les fenêtres ou faites Ctrl+C dans chacune.

Sous Linux ou macOS, il n'y a pas de `dev` : lancez `make api`, `make worker`, `make beat` et
`make front` dans quatre terminaux, avec `redis-server` démarré.

### Commandes du développeur

| Commande | Rôle |
|---|---|
| `.\tasks.ps1 test` | tous les tests : pytest (backend) et Vitest (frontend) |
| `.\tasks.ps1 lint` | ruff, mypy, ESLint, Prettier |
| `.\tasks.ps1 format` | reformate le code |
| `.\tasks.ps1 client` | régénère le schéma OpenAPI puis le client Angular, à faire après un changement d'API |
| `.\tasks.ps1 shell` | console Django |
| `.\tasks.ps1 db-reset` | vide la base (développement uniquement), puis `migrate` et `seed` |

---

## Se connecter (données de démonstration)

| Code entreprise | Identifiant | Rôle |
|---|---|---|
| `MINX` | `rh` | service RH (le plus complet pour une démo) |
| `MINX` | `admin`, `manager`, `agent`, `auditeur` | autres rôles |
| `PMEY` | `admin`, `agent` | seconde entreprise |
| *(vide)* | `editeur` | équipe PointQR (`/plateforme`) |

- Mot de passe de tous les comptes : `Demo-PointQR-2026`.
- Les comptes **admin, rh et editeur** demandent un code à 6 chiffres. Ajoutez une fois le
  secret `PQRDEMOPQRDEMOPQRDEMOPQRDEMOPQRD` dans Google Authenticator, Microsoft Authenticator
  ou FreeOTP (option « saisir une clé »).

Ensuite, suivez le parcours de 5 minutes du
[guide d'utilisation](GUIDE_UTILISATEUR.md#16-essayer-avec-les-données-de-démonstration).

---

## Tester sur un vrai téléphone

La caméra et la géolocalisation du navigateur n'acceptent que **HTTPS** ou `localhost`. Un
téléphone qui ouvre `http://192.168.x.x:4200` ne pourra donc pas scanner. Deux solutions :

- un tunnel HTTPS vers le port 4200 (ou 8080), par exemple `cloudflared tunnel --url
  http://localhost:4200`, puis ouvrir l'adresse `https://…` fournie sur le téléphone ;
- sinon, tout tester sur l'ordinateur : la borne dans un onglet, l'agent dans un second
  navigateur, en présentant le QR de la borne à la webcam.

Pensez à placer le site près de votre position réelle (`Sites` → cliquer sur la carte), sinon
le pointage sera refusé « Hors zone ».

---

## Problèmes fréquents

| Symptôme | Cause et solution |
|---|---|
| `db-init` : « password authentication failed » | mauvais mot de passe du superutilisateur `postgres`, ou mauvais port dans `.env` |
| L'API répond « connection refused » sur le port 5432 | PostgreSQL écoute sur un autre port : corriger `POSTGRES_PORT` et les deux URL dans `.env` |
| Le worker reste bloqué au démarrage | Garnet lancé sans `--lua` : passez par `.\tasks.ps1 redis` ou `dev`, qui ajoutent l'option |
| `ng` : « Node.js version … is not supported » | installer Node 22.22+ ou 24+ |
| Requêtes très lentes sous Windows | utiliser `127.0.0.1` plutôt que `localhost` dans `.env` (c'est le cas par défaut) |
| Code TOTP refusé | l'heure du PC n'est pas synchronisée, ou le même code a déjà servi : attendre le code suivant (30 s) |
| « Compte verrouillé » | 5 échecs de connexion : patienter, ou débloquer tous les comptes : `cd backend; uv run python manage.py axes_reset` |
| `docker compose` : « run tasks.ps1 env first » | le fichier `.env` manque : `.\tasks.ps1 env` |
| Le port 8080 est déjà pris | ajouter `WEB_PORT=8081` dans `.env`, puis `docker-up` |
| Construction Docker en échec « no space left on device » | libérer de l'espace disque (`docker system prune` supprime les images inutilisées) |
| Le pointage est refusé « Hors zone » | le site est loin de votre position : déplacer le site sur la carte ou élargir le rayon |

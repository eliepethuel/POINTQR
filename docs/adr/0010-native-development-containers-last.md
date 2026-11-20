# ADR-0010 — Développement natif, conteneurisation en dernière phase

- Statut : accepté
- Date : 2026-11-20
- Remplace : ADR-0008 ; la partie « développement » de ADR-0009

## Contexte
Sous Windows, Docker Desktop occupe plus de 10 Go (disque virtuel WSL), ralentit les dossiers partagés
(rechargement à chaud, `node_modules`) et a saturé le poste de développement.

## Décision
1. **Développement natif** sur le poste :
   - Python 3.13 et dépendances via `uv` (`backend/.venv`) ;
   - Node 24+ et `npm` pour Angular ;
   - PostgreSQL 16 installé localement (rôles créés par `tasks.ps1 db-init`) ;
   - Redis remplacé localement par **Garnet** (serveur compatible Redis de Microsoft, natif Windows) ;
   - fichiers (justificatifs, exports) sur le disque local (`backend/media/`) ; S3 seulement hors développement ;
   - e-mails affichés dans la console du serveur.
2. Commandes identiques : `tasks.ps1` (Windows) et `Makefile` (Linux, macOS), sans Docker.
3. La **CI** GitHub Actions utilise les vrais PostgreSQL 16 et Redis 7 fournis par GitHub : les écarts
   éventuels entre Garnet et Redis y sont détectés.
4. Les images Docker, `docker-compose.yml`, nginx et les en-têtes de sécurité du proxy sont produits
   en **dernière phase** (ticket PQR-011), pour le déploiement cloud et l'installation sur site.

## Conséquences
- Environ 1,5 Go sur le poste au lieu de plus de 10 Go.
- Le critère « `docker compose up` » de chaque phase est remplacé par « `tasks.ps1 dev` démarre tout
  et la CI est verte » jusqu'à la phase de conteneurisation.

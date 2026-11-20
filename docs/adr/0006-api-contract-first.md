# ADR-0006 — Contrat d'API d'abord, client Angular généré

- Statut : accepté
- Date : 2026-11-20

## Décision
- Le backend publie `/api/schema/` (OpenAPI 3) et `/api/docs/` (Swagger UI).
- Le schéma est exporté dans `backend/openapi.yaml` (versionné).
- Le frontend génère `src/app/api/` avec **ng-openapi-gen** (`npm run api:generate`) ; ce dossier ne se modifie jamais à la main.
- La CI régénère schéma et client, et échoue si `git diff` n'est pas vide.
- API versionnée `/api/v1/`, erreurs **RFC 7807** (`type`, `title`, `status`, `detail`, `code`, `errors`),
  pagination par curseur pour les pointages.

## Conséquences
Aucun appel `HttpClient` écrit à la main vers un endpoint métier ; une rupture de contrat casse la compilation.

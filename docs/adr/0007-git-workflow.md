# ADR-0007 — Flux Git

- Statut : accepté
- Date : 2026-11-20

## Décision
- `main` : versions livrées, une étiquette par phase (`v0.1.0` = phase 0, …).
- `develop` : intégration.
- Une branche courte par unité de travail : `feat/…`, `fix/…`, `chore/…`, `docs/…`, `test/…`, `ci/…`,
  fusionnée dans `develop` avec `--no-ff` (la branche reste visible dans l'historique).
- Messages **Conventional Commits** (`feat(attendance): …`), un commit = un changement cohérent.
- Fin de phase : `develop` fusionnée dans `main`, étiquette, push.

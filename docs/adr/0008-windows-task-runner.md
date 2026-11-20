# ADR-0008 — Commandes de développement sous Windows et Linux

- Statut : remplacé par ADR-0010
- Date : 2026-11-20

## Contexte
`make` n'est pas disponible par défaut sous Windows.

## Décision
Les mêmes cibles existent dans `Makefile` (Linux, macOS, CI) et `tasks.ps1` (Windows) :
`up`, `down`, `logs`, `test`, `lint`, `seed`, `openapi`, `client`, `migrate`, `shell`.
Toutes les commandes s'exécutent dans les conteneurs Docker : l'hôte n'a besoin que de Docker et Node (pour l'éditeur).

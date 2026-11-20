# ADR-0009 — Stockage objet S3 : SeaweedFS en développement

- Statut : accepté
- Date : 2026-11-20

## Contexte
Le cahier des charges cite MinIO pour le stockage S3 local. Depuis fin 2025, MinIO ne publie plus
d'images Docker publiques pour l'édition communautaire.

## Décision
- Le code ne dépend que de l'**API S3** (`django-storages` + `boto3`), jamais d'un produit.
- En développement : **SeaweedFS** (`weed server -s3`), image figée, identifiants générés depuis `.env`.
- En production : tout service compatible S3 (hébergeur ivoirien, Ceph, SeaweedFS, AWS…) par simple
  changement de `S3_ENDPOINT_URL`.
- Téléchargements via URL pré-signée à durée courte.

## Conséquences
Aucun verrou fournisseur ; l'hébergement en Côte d'Ivoire (ENF-06) reste possible.

# ADR-0002 — Django + DRF à la place de NestJS

- Statut : accepté
- Date : 2026-11-20

## Contexte
Le cahier des charges (§9) propose NestJS, BullMQ et un temps réel non précisé. L'équipe maîtrise Python/Django.

## Décision
- API : **Django 5.2 LTS + Django REST Framework**, schéma OpenAPI 3 généré par **drf-spectacular**.
- Tâches de fond : **Celery + celery-beat**, broker **Redis**.
- Temps réel : **Django Channels** + `channels-redis` (WebSocket).
- Serveur ASGI : Daphne/Uvicorn.

## Conséquences
- Le contrat OpenAPI reste la source de vérité et le front Angular génère son client typé : le « typage partagé » visé par NestJS est conservé.
- Django 5.2 est LTS jusqu'en avril 2028.

# ADR-0013 — Rapports PDF avec ReportLab

- Statut : accepté
- Date : 2026-11-21

## Contexte
Les fiches mensuelles de présence (EF-36) sont livrées en PDF. WeasyPrint produit des PDF à
partir de HTML/CSS mais dépend de bibliothèques natives (Pango, GTK) pénibles à installer sous
Windows en développement natif (ADR-0010) et qui alourdissent l'image Docker.

## Décision
- PDF générés avec **ReportLab** (Python pur, aucune dépendance système) ; Excel avec openpyxl.
- Génération dans une tâche Celery (`ReportJob`, progression en %), fichier déposé sur le
  stockage (local en développement, S3 en production) et servi par une URL signée à durée
  limitée (`/api/v1/files/?t=…`).
- Les rapports récurrents (`ReportSchedule`) sont envoyés par e-mail par Celery beat.

## Conséquences
Mise en page décrite en code (tableaux ReportLab) plutôt qu'en CSS. R9 (500 agents, rapport
mensuel < 30 s) est vérifié en test automatique.

# ADR-0003 — Code en anglais, interface en français

- Statut : accepté
- Date : 2026-11-20

## Décision
Noms de modèles, champs, fonctions et routes en anglais ; libellés, messages et erreurs utilisateur en français
(Angular `$localize`, Django `gettext`), prêts pour l'anglais en V2.

| Cahier des charges | Code |
|---|---|
| Entreprise | `Company` |
| Abonnement | `Subscription` |
| Site | `Site` |
| Unité | `OrgUnit` |
| Agent | `Agent` |
| Utilisateur | `User` |
| Appareil | `Device` |
| Borne | `Kiosk` |
| Horaire | `Schedule` |
| Jour férié | `PublicHoliday` |
| Pointage | `CheckIn` |
| Journée | `WorkDay` |
| Demande | `Request` |
| Journal d'audit | `AuditLog` |
| `entreprise_id` | `company_id` |

## Conséquences
Les identifiants de règles (RG-xx, EF-xx, R1…R10) restent cités tels quels dans les tests et docstrings.

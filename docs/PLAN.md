# PointQR — Plan de réalisation (à valider avant tout code)

> « Le pointage qui ne ment pas. »
> Source de vérité fonctionnelle : `docs/Cahier_des_charges_PointQR.pdf` (CDC v1.0, 6 nov. 2026).
> Écarts voulus par rapport au CDC : backend **Django + DRF** (au lieu de NestJS), **Celery** (au lieu de BullMQ),
> **Django Channels** pour le temps réel, borne et agent en **Angular (web/PWA)** dans ce lot (Flutter plus tard).

---

## 0. Versions retenues (vérifiées le 20/11/2026)

| Brique | Version | Remarque |
|---|---|---|
| Python (Docker) | 3.13 | l'hôte a 3.10 : le backend tourne en conteneur, `uv` pour les dépendances |
| Django | **5.2 LTS** (5.2.19) | LTS jusqu'en avril 2028 |
| DRF, simplejwt, spectacular, channels, celery | dernières stables compatibles 5.2 | figées dans `uv.lock` |
| PostgreSQL | 16 | comme demandé par le CDC |
| Redis | 7 | anti-rejeu, broker Celery, couche Channels |
| Angular | **22.3** | standalone, signals, zoneless, control flow |
| Node | 22 LTS (hôte 22.20) | image `node:22-alpine` |

---

## 1. Arborescence

```
Pointqr_App/                       # = racine « pointqr/ »
├── README.md
├── Makefile                       # cibles Linux/CI
├── tasks.ps1                      # mêmes cibles pour Windows (make absent sur l'hôte)
├── docker-compose.yml             # postgres, redis, minio, mailpit, backend, worker, beat, frontend, nginx
├── docker-compose.override.yml    # dev : volumes montés, hot reload
├── .env.example
├── .pre-commit-config.yaml
├── .github/workflows/ci.yml
├── infra/
│   ├── nginx/                     # reverse proxy, CSP, HSTS, *.localhost → tenant
│   ├── postgres/init/             # 01-roles.sql (app_user sans BYPASSRLS, admin_role séparé)
│   └── locust/locustfile.py       # R10
├── docs/
│   ├── Cahier_des_charges_PointQR.pdf
│   ├── PLAN.md  BACKLOG.md  API.md
│   └── adr/0001-…md
├── backend/
│   ├── pyproject.toml  uv.lock  Dockerfile
│   ├── config/                    # settings/{base,dev,test,prod}.py, urls, asgi (Channels), celery
│   ├── common/                    # TenantModel, TenantManager, RFC7807 handler, pagination curseur, crypto (Fernet)
│   └── apps/
│       ├── tenancy/  accounts/  organization/  kiosks/  schedules/
│       ├── attendance/            # services/{checkin,token,geo,rules}.py
│       ├── requests_app/  reports/  audit/  notifications/
│       └── <app>/{models,serializers,views,services,selectors,permissions,tasks}.py + tests/
└── frontend/
    ├── angular.json  package.json  tailwind.config  ngsw-config.json  Dockerfile
    ├── openapi/                   # config ng-openapi-gen
    └── src/app/
        ├── core/   api/ (généré)   shared/ui/   shared/motion/
        ├── features/{landing,auth,dashboard,agents,sites,org,schedules,kiosks,attendance,requests,reports,audit,settings,superadmin}
        ├── kiosk/                 # /kiosk
        └── agent/                 # /agent (PWA)
```

---

## 2. Modèle de données

Code en anglais, libellés en français. Correspondance CDC → code (ADR-0002) :

| CDC | Modèle | Champs clés (en plus de `id` UUID, `company_id`, `created_at`) |
|---|---|---|
| Entreprise | `Company` *(non tenant)* | legal_name, slug (sous-domaine), code (app mobile), logo, sector, country, timezone, contact, status (active/suspended), branding (couleurs), retention_checkins_years=5, retention_gps_months=12, approval_levels (1/2), wifi_check_enabled, break_checkins_enabled |
| Abonnement | `Subscription` *(non tenant)* | company, plan, max_agents, max_sites, max_kiosks, start_date, end_date, status |
| Site | `Site` | name, address, latitude, longitude, radius_m=150, allowed_wifi (JSON : SSID/BSSID), static_qr_secret_enc (mode D) |
| Unite | `OrgUnit` | name, kind (direction/service/team), parent (arbre, `path` matérialisé pour requêtes rapides), manager (Agent) |
| Agent | `Agent` | employee_number (unique/entreprise), last_name, first_names, job_title, phone, email, site, org_unit, schedule, status, badge_secret_enc (modes B/C), badge_version |
| Utilisateur | `User` (AbstractBaseUser) | agent (0..1), username/email, password (argon2), is_superadmin, mfa via django-otp `TOTPDevice` |
| — | `UserRole` | user, company, role ∈ {company_admin, hr, manager, agent, auditor} (cumulables) ; super_admin global ; borne = compte machine `Kiosk` |
| Appareil | `Device` | agent, fingerprint_hash, model, os, bound_at, is_active ; contraintes uniques partielles RG-13 |
| — | `DeviceChangeRequest` | agent, new_fingerprint, status, decided_by (EF-10) |
| — | `Invitation` | agent, channel, token_hash, expires_at, used_at (EF-09) |
| Borne | `Kiosk` | site, name, secret_key_enc (Fernet), key_version, last_seen_at, status (pending/active/revoked), app_version |
| — | `KioskPairingCode` | company, site, code (6 chiffres, haché), expires_at, used_at |
| Horaire | `Schedule` | name, kind (fixed/rotation), weekdays, start_time, end_time, break_minutes, late_tolerance_min=10, early_tolerance_min=10, is_night (RG-15) |
| — | `ScheduleRotation` / `ScheduleException` | rotations jour/nuit (EF-14) ; périodes d'exception type Ramadan (EF-16) |
| JourFerie | `PublicHoliday` | date, label, country, company (null = référence CI, copiée/modifiable par entreprise) |
| Pointage | `CheckIn` *(ajout seul)* | agent (null si refus sans agent identifié), kiosk, site, device, direction (in/out/break_out/break_in), server_ts, local_ts (hors-ligne), mode (A/B/C/D), trust (high/medium), latitude, longitude, distance_m, offline, result (accepted/refused/ignored), refusal_code, corrects (FK self, RG-12), author, reason |
| Journee | `WorkDay` | agent, date, first_in, last_out, late_minutes, early_leave_minutes, worked_minutes, overtime_minutes, overtime_validated, status (present/late/late_justified/absent/absent_justified/incomplete/holiday/off), computed_at |
| — | `Period` | month, status (open/closed), closed_by, reopened_by (RG-14) |
| Demande | `Request` | agent, kind (justification/correction/device_change/overtime), target_date, checkin (opt.), reason, attachment (S3), status, current_level |
| — | `RequestDecision` | request, level (manager/hr), decided_by, decision, comment |
| JournalAudit | `AuditLog` *(ajout seul)* | actor (user/kiosk/system), action, object_type, object_id, before, after (JSON), ip, user_agent, ts |
| — | `ImportJob`, `ReportJob` | statut, progression %, fichier résultat, rapport d'erreurs |
| — | `Notification` | destinataire, type, payload, read_at |

**Base de données**
- RLS `ENABLE` + `FORCE` sur toutes les tables tenant, politique `company_id = current_setting('app.current_tenant', true)::uuid`.
- Triggers `BEFORE UPDATE OR DELETE` → `RAISE EXCEPTION` sur `attendance_checkin` et `audit_auditlog` (la purge de conservation passe par une fonction `SECURITY DEFINER` dédiée et tracée).
- Index : `(company_id, agent_id, server_ts DESC)` sur CheckIn, `(company_id, date)` sur WorkDay.

---

## 3. Endpoints (`/api/v1`, OpenAPI via drf-spectacular)

**Auth & compte** — `auth/login` (→ `mfa_required` si besoin) · `auth/mfa/verify` · `auth/mfa/setup` · `auth/refresh` (cookie HttpOnly) · `auth/logout` · `auth/companies` (choix entreprise) · `me` · `me/sessions` (déconnexion à distance, ENF-10) · `me/history` + `me/export` (ENF-05)

**Super-admin** — `admin/companies` CRUD + `suspend`/`reactivate` · `admin/subscriptions` · `admin/stats` · `admin/onboarding/{company}` (assistant 4 étapes)

**Organisation** — `sites` · `org-units` (+ `tree`) · `agents` (+ `import`, `import/{id}` progression/erreurs, `{id}/invite`, `{id}/history`, `badges.pdf`) · `devices` · `device-change-requests/{id}/approve|reject` · `users` + `roles`

**Horaires** — `schedules` · `schedule-exceptions` · `holidays` (+ `import-reference`) · `periods/{id}/close|reopen`

**Bornes** — `kiosks` (+ `pairing-codes`, `{id}/revoke`, `{id}/rotate-key`) · machine : `kiosk/pair` · `kiosk/heartbeat` (+ resync horloge) · `kiosk/checkins/batch` (hors-ligne, idempotent par `client_uuid`)

**Pointage (mobile, payload < 5 Ko)** — `mobile/activate` (lie l'appareil) · `mobile/checkins` (mode A/D) · `mobile/checkins/preview` (sens suggéré, RG-07) · `mobile/badge-token` (QR personnel tournant, mode B) · `kiosk/checkins` (scan badge, modes B/C)
Contrôles dans l'ordre : `TOKEN_INVALID`/`TOKEN_EXPIRED` → `TOKEN_REPLAYED` → `DEVICE_NOT_BOUND`/`DEVICE_MISMATCH` → `OUT_OF_ZONE`/`MOCK_LOCATION` → `WIFI_NOT_ALLOWED` → `DUPLICATE` (ignoré, RG-06) ; plus `COMPANY_SUSPENDED`, `KIOSK_REVOKED`.

**Suivi** — `attendance/checkins` (curseur) · `attendance/anomalies` · `attendance/workdays` (+ `recompute`) · `attendance/corrections` · `dashboard/today` · `dashboard/rankings` · WS `/ws/dashboard/`

**Demandes** — `requests` (+ `attachments` upload pré-signé, `{id}/decide`)

**Rapports** — `reports` (POST lance un job : punctuality / monthly-sheet.pdf / payroll.xlsx / checkins.csv) · `reports/{id}` (progression + URL signée) · `report-schedules`

**Audit & paramètres** — `audit-logs` (lecture seule) · `settings/company` (branding, rétention, circuit 1/2 niveaux) · `notifications`

Erreurs RFC 7807 partout ; throttling `checkin` par appareil + IP ; test R8 qui itère sur **toutes** les routes du resolver.

---

## 4. Écrans Angular

| Route | Rôles | Contenu |
|---|---|---|
| `/` | public | Landing (problème, solution, 4 étapes, anti-fraude, modes A-D, ARTCI, objectifs, CTA démo) |
| `/login`, `/login/mfa`, `/login/company` | public | connexion, TOTP 6 cases, choix entreprise |
| `/app/dashboard` | admin, RH, manager (périmètre), auditeur | bento KPI, flux live, carte, classement, anomalies |
| `/app/agents`, `/app/agents/:id`, `/app/agents/import` | admin, RH | table virtualisée, fiche, import |
| `/app/sites`, `/app/org`, `/app/schedules`, `/app/holidays` | admin | carte + rayon, organigramme, horaires, calendrier |
| `/app/kiosks` | admin | appairage, statut live, révocation, rotation clé |
| `/app/attendance` | RH, manager, auditeur | pointages, anomalies, journées, corrections |
| `/app/requests` | tous (agent = les siennes) | justificatifs, corrections, validation |
| `/app/reports` | RH, admin | génération + progression |
| `/app/audit` | admin, auditeur | journal lecture seule |
| `/app/settings` | admin (+ préférences perso pour tous) | branding, rétention, sécurité, « réduire les animations » |
| `/app/me` | agent | historique, export, contestation |
| `/superadmin/*` | super-admin | entreprises, abonnements, stats, assistant 4 étapes |
| `/kiosk` | borne | appairage → QR plein écran, scan badges, hors-ligne |
| `/agent` | agent (PWA) | activation, scan, confirmation, mon QR (mode B), historique |

---

## 5. Catalogue d'animations

**Tokens** (`shared/motion/tokens.ts` + variables CSS) : `instant 100 / fast 200 / base 320 / slow 600 / hero 1200 ms` ; `out-expo`, `out-back`, `in-out-quart`, spring (GSAP `elastic`/CSS `linear()`).

**Directives** : `revealOnScroll`, `staggerChildren`, `countUp`, `magnetic`, `tilt3d`, `spotlight`, `splitText`, `shimmer`, `ripple`, + `flipList` (GSAP Flip), `pressable`.
**Services** : `MotionService` (reduced-motion système + préférence utilisateur, signal `motionLevel`), `GsapLoader` (import dynamique), `ThemeService` (révélation circulaire via View Transitions + `clip-path`).

| Écran | Moment « waouh » | Technique |
|---|---|---|
| Landing | Titre SplitText ; QR 3D flottant qui se recompose ; frise RG-02 7:30 → 7:52 → « 22 min » au scroll ; cartes fraude→parade qui se retournent ; compteurs < 5 s / 30 s / 100 % ; architecture reliée par lignes lumineuses | GSAP SplitText, ScrollTrigger, SVG `stroke-dashoffset`, CSS 3D `rotateY` |
| Connexion | Aurora animée, champs lumineux au focus, OTP 6 cases qui s'emboîtent, secousse à l'erreur | CSS gradients + `@property`, GSAP timeline |
| Dashboard | Bento en cascade, KPI count-up, ECharts qui se dessinent, flux live Flip (pastille verte / clignotement corail), sites qui pulsent | Flip, ECharts animation, CSS `@keyframes` scale/opacity |
| Tables | Lignes en cascade, réordonnancement Flip, skeleton shimmer, panneau latéral ressort | CDK virtual scroll + Flip, spring |
| Import | Zone qui respire, progression liquide, erreurs dépliées ligne par ligne | SVG wave `transform`, stagger |
| Org / Sites | Arbre qui se déploie, onde du rayon au changement | Flip, cercle SVG `scale` |
| Kiosk | QR plein écran + anneau 30 s, renouvellement en dissolution de pixels, horloge mono géante, onde verte/corail depuis le centre, bandeau hors-ligne + compteur | Canvas 2D (dissolution par modules QR), SVG ring, CSS radial |
| Agent PWA | Viseur laser + coins animés, check Lottie + particules, heure en grand + statut, vibration | Lottie (lazy), canvas particules, `navigator.vibrate` |
| Global | Toasts ressort, modales depuis l'élément cliqué, palette ⌘K, sidebar fluide, états vides Lottie, transitions de pages avec éléments partagés (photo + nom agent liste → fiche) | View Transitions API (`withViewTransitions`, `view-transition-name`), CDK Overlay |

Garde-fous : `transform`/`opacity` uniquement, GSAP/Lottie/ECharts en `@defer`/import dynamique, nettoyage via `DestroyRef` (`gsap.context().revert()`), budget Lighthouse ≥ 90, test CPU ×4.

---

## 6. Décisions prises par défaut (deviendront des ADR)

1. **Racine** = `Pointqr_App/` (joue le rôle de `pointqr/`), CDC copié dans `docs/`.
2. **Noms de code en anglais** (table §2), libellés FR, i18n Angular `$localize` prête pour l'EN.
3. **Windows** : `make` absent → `Makefile` (CI/Linux) + `tasks.ps1` équivalent ; tout tourne dans Docker.
4. **Tenant en local** : sous-domaines `*.localhost` (`ministere-x.localhost:8080`), puis claim JWT `company_id`, puis en-tête `X-Company-Code` (mobile).
5. **Super-admin** : connexion PostgreSQL séparée (`DATABASES['admin']`, rôle `BYPASSRLS`) utilisée uniquement par les vues `/admin/*` en lecture/gestion d'entreprises — jamais pour modifier un pointage.
6. **Jeton QR** (détail : ADR-0005) : `PQR1.<site>.<kiosk>.<window>.<sig>` ; fenêtres courante et précédente acceptées ; anti-rejeu Redis `SET NX` sur (kiosk, window, device), TTL 90 s.
   *Note* : un QR de borne est scanné par plusieurs agents dans la même fenêtre, l'usage unique s'entend donc **par appareil et par fenêtre**.
7. **Mode D** (QR imprimé sans borne) : jeton statique signé par le site, confiance « moyenne », contrôle par position + appareil lié.
8. **Badge (mode C)** : QR statique `agent + badge_version + HMAC` ; régénérer le badge incrémente la version. **Mode B** : QR personnel tournant 30 s dérivé d'une clé par appareil.
9. **Fake GPS** côté web : impossible à détecter dans un navigateur → champ `mock_location` accepté dans l'API (pour Flutter), PWA envoie `accuracy` ; refus si précision > rayon.
10. **Carte** : Leaflet + tuiles OpenStreetMap (CSP adaptée) ; changeable plus tard.
11. **Front client API** : `ng-openapi-gen` (fonctions + services Angular, compatible signals via `httpResource` au-dessus).
12. **Abonnement** : enregistrement et limites seulement, aucun paiement en ligne.

---

## 7. Phases

Identiques à la section 9 du prompt (0 Fondations → 5 Landing et finitions), un commit Conventional Commits + résumé par phase.

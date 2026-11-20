# ADR-0005 — Format du jeton QR dynamique et anti-rejeu

- Statut : accepté
- Date : 2026-11-20

## Décision
- Jeton : `PQR1.<site_id>.<kiosk_id>.<window>.<sig>` où `window = floor(unix_time / 30)` et
  `sig = base64url(HMAC-SHA256(kiosk_key, "PQR1|site|kiosk|window"))` tronqué à 16 octets.
- Le serveur accepte `window` courante et précédente uniquement (dérive d'horloge ≤ 30 s).
- La borne calcule le jeton **localement** (WebCrypto, clé non exportable) : aucun besoin d'Internet.
- Anti-rejeu : un QR de borne est scanné par plusieurs agents pendant la même fenêtre. L'usage unique
  s'applique donc à la paire **(jeton, appareil)** : `SET NX pqr:replay:<kiosk>:<window>:<device>` avec TTL 90 s.
- Mode D (QR imprimé sans borne) : jeton statique signé par la clé du site, confiance « moyenne ».
- Mode C (badge) : `PQRB.<agent_id>.<badge_version>.<sig>` ; régénérer un badge incrémente la version.
- Mode B (QR personnel tournant) : même principe que la borne, clé propre à l'appareil lié.
- Clés chiffrées au repos (Fernet, clé `FIELD_ENCRYPTION_KEY` dans l'environnement), régénérables.

## Conséquences
Un QR photographié est inutilisable après 30 à 60 s (O3) ; un même téléphone ne peut pas rejouer une requête.

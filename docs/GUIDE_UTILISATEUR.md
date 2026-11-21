# Guide d'utilisation de PointQR

> **Le pointage qui ne ment pas.** L'heure d'un pointage est toujours celle du serveur, jamais
> celle du téléphone de l'agent.

Ce guide suit l'ordre d'une mise en service réelle : l'éditeur crée l'entreprise, l'administrateur
la configure, les agents pointent, le service RH suit et valide. Chaque section indique le menu à
ouvrir dans le back-office.

## Sommaire

1. [Les espaces et les rôles](#1-les-espaces-et-les-rôles)
2. [Se connecter](#2-se-connecter)
3. [Administrateur : mettre l'entreprise en service](#3-administrateur--mettre-lentreprise-en-service)
4. [Installer une borne](#4-installer-une-borne)
5. [Agent : pointer avec son téléphone](#5-agent--pointer-avec-son-téléphone)
6. [Agents sans smartphone : badge et QR personnel](#6-agents-sans-smartphone--badge-et-qr-personnel)
7. [Service RH : suivre la journée](#7-service-rh--suivre-la-journée)
8. [Demandes, justificatifs et corrections](#8-demandes-justificatifs-et-corrections)
9. [Changement de téléphone](#9-changement-de-téléphone)
10. [Rapports et clôture du mois](#10-rapports-et-clôture-du-mois)
11. [Manager et auditeur](#11-manager-et-auditeur)
12. [Équipe PointQR : l'espace plateforme](#12-équipe-pointqr--lespace-plateforme)
13. [Comprendre un refus de pointage](#13-comprendre-un-refus-de-pointage)
14. [Statuts d'une journée et règles de calcul](#14-statuts-dune-journée-et-règles-de-calcul)
15. [Astuces](#15-astuces)
16. [Essayer avec les données de démonstration](#16-essayer-avec-les-données-de-démonstration)

---

## 1. Les espaces et les rôles

| Espace | Adresse | Pour qui |
|---|---|---|
| Site vitrine | `/` | tout le monde |
| Back-office | `/connexion` puis `/app/…` | administrateur, RH, manager, auditeur |
| Application agent | `/agent` (installable comme une application) | agents |
| Mode borne | `/kiosk` | tablette fixée à l'entrée du site |
| Espace plateforme | `/plateforme` | équipe PointQR (éditeur) |

En local, ces adresses commencent par `http://localhost:4200` en mode natif, ou par
`http://localhost:8080` avec Docker.

| Rôle | Ce qu'il peut faire |
|---|---|
| **Administrateur entreprise** | tout configurer : paramètres, sites, organigramme, horaires, agents, bornes, utilisateurs ; consulter le journal d'audit |
| **Gestionnaire RH** | suivre les présences, traiter les demandes, valider les changements de téléphone, corriger un pointage, produire les rapports, clôturer un mois |
| **Manager** | voir son équipe et valider en premier niveau les demandes de ses agents |
| **Auditeur** | tout consulter, sans rien modifier |
| **Agent** | pointer, voir son historique, envoyer des demandes |

Le menu de gauche n'affiche que les pages permises au rôle connecté.

## 2. Se connecter

1. Ouvrez `/connexion`.
2. Saisissez le **code entreprise** (par exemple `MINX`), votre **identifiant** et votre
   **mot de passe**. Laissez le code entreprise vide si vous faites partie de l'équipe PointQR.
3. **Double authentification** : elle est obligatoire pour les administrateurs, le service RH et
   l'équipe PointQR.
   - À la première connexion, scannez le QR affiché avec Google Authenticator, Microsoft
     Authenticator ou FreeOTP, puis saisissez le code à 6 chiffres. Une clé manuelle est aussi
     affichée si vous ne pouvez pas scanner.
   - Ensuite, chaque connexion demande le code du moment (« Vérification en deux étapes »).

Après **5 échecs**, le compte est verrouillé quelque temps. Un agent qui se connecte arrive
directement sur l'application agent.

> **Raccourci** : dans le back-office, **Ctrl+K** (ou ⌘K sur Mac) ouvre la palette de commandes.
> Tapez le nom d'une page (« agents », « rapports »…) puis Entrée. La palette permet aussi de
> changer de thème, d'ouvrir le mode borne et de se déconnecter.

## 3. Administrateur : mettre l'entreprise en service

Comptez moins d'une journée, dans cet ordre.

### 3.1 Paramètres (`Paramètres`)

- **Entreprise** : raison sociale, code entreprise (utilisé par l'application mobile et la borne),
  couleurs de l'application et de la borne.
- **Règles par défaut** :
  - rayon de géorepérage par défaut, en mètres ;
  - circuit de validation des demandes : 1 niveau (manager) ou 2 niveaux (manager puis RH) ;
  - durée de conservation des pointages (en années) et des positions GPS brutes (en mois) ;
  - **Exiger un Wi-Fi autorisé en second facteur** ;
  - **Activer le pointage des pauses**.
- **Mes préférences** (pour chaque utilisateur) : thème clair ou sombre, animations réduites.

### 3.2 Sites (`Sites`)

1. Cliquez sur **Nouveau site**, puis saisissez le nom et l'adresse.
2. Pour placer le site, cliquez sur la carte : la latitude et la longitude se remplissent seules.
3. Réglez le **rayon de géorepérage**. Il vaut 150 m par défaut ; élargissez-le pour les bâtiments
   où le GPS est imprécis.
4. *Facultatif* : renseignez les **Wi-Fi autorisés** (noms de réseaux séparés par des virgules).
   Ils ne servent que si le second facteur Wi-Fi est activé dans les paramètres.

### 3.3 Organigramme (`Organigramme`)

Cliquez sur **Nouvelle unité** et choisissez son type (Direction, Service ou Équipe) ainsi que
l'unité à laquelle elle est rattachée. Le manager d'une unité reçoit les demandes de ses agents.

### 3.4 Horaires (`Horaires`)

**Nouvel horaire** : nom, jours travaillés, heure d'arrivée et de départ, tolérance de retard,
tolérance de départ et durée de pause.

- Un départ avant l'arrivée (par exemple 20:00 → 06:00) crée un **poste de nuit**, rattaché à son
  jour de début.
- Section **Jours fériés** : les fériés nationaux de Côte d'Ivoire sont déjà chargés. Ajoutez
  les jours propres à l'entreprise (date et libellé).
- Les fêtes musulmanes sont fixées chaque année par décret : vérifiez les dates indicatives.

### 3.5 Agents (`Agents`)

Deux façons d'ajouter des agents :

- **Un par un** : cliquez sur **Nouvel agent**.
- **En masse** : cliquez sur **Importer Excel / CSV**, puis :
  1. **Télécharger le modèle**. Colonnes reconnues : `matricule`, `nom`, `prénoms` (obligatoires),
     puis `fonction`, `téléphone`, `e-mail`, `site`, `unité` (ou `service`).
  2. Déposez le fichier (5 000 lignes maximum). Une barre de progression s'affiche, puis le
     nombre de lignes lues et d'erreurs.
  3. S'il y a des erreurs, elles sont listées ligne par ligne et **rien n'est enregistré** :
     corrigez le fichier et déposez-le à nouveau.
  4. Sinon, cliquez sur **Confirmer l'import de N agents**.

La fiche d'un agent indique son téléphone lié (« actif », « révoqué » ou « à activer »). La
**Fiche complète** montre le mois de l'agent :

- jours présents ;
- retards et minutes cumulées ;
- absences, dont les absences justifiées ;
- heures travaillées ;
- le détail jour par jour.

### 3.6 Utilisateurs (`Utilisateurs`)

Créez les comptes du back-office (RH, managers, auditeurs) et les comptes des agents. Un compte
agent est relié à une fiche agent.

## 4. Installer une borne

Une borne est une tablette ou un écran fixé à l'entrée. Elle affiche un QR code qui change
**toutes les 30 secondes**.

1. Dans le back-office, ouvrez `Bornes` et cliquez sur **Nouvelle borne**. Choisissez le site et un
   nom (par exemple « Entrée principale »), puis cliquez sur **Générer le code**.
2. Sur la tablette, ouvrez `/kiosk`. À l'écran **Appairer cette borne**, saisissez le **code
   entreprise** et le **code d'appairage à 6 chiffres**. Le code a une durée de validité limitée.
3. La borne affiche alors « Scannez ce code avec l'application PointQR », avec un anneau qui
   décompte le temps restant avant le prochain QR.

Pour la gestion courante, depuis `Bornes` :

- **Régénérer la clé** : la borne récupère automatiquement sa nouvelle clé. Faites-le si la
  tablette a pu être copiée.
- **Révoquer** : en cas de vol ou de perte. La tablette affiche « Cette borne a été révoquée par
  l'administrateur » et ses QR sont refusés.
- **Hors-ligne** : la borne continue de lire les badges et les QR personnels, et garde ces
  pointages en mémoire. Elle les envoie au retour du réseau ; ils sont alors marqués
  « hors-ligne » et gardent l'heure de la borne. Le tableau de bord indique combien de
  pointages sont en attente.

## 5. Agent : pointer avec son téléphone

### Première fois : activer son téléphone

1. Ouvrez `/agent` sur votre téléphone et connectez-vous. Vous pouvez ajouter l'application à
   l'écran d'accueil.
2. Appuyez sur **Activer ce téléphone**. Un seul téléphone peut pointer pour vous : après
   activation, tout changement devra être validé par le service RH (voir §9).

### Chaque jour : pointer

1. Onglet **Pointer**. L'écran indique le **prochain pointage** : entrée ou sortie.
2. Visez le QR code de la borne avec la caméra.
3. Le résultat s'affiche aussitôt, avec l'heure du serveur :
   - ✅ **accepté** : « À l'heure » ou « Retard de 22 min », puis « Entrée enregistrée » ou
     « Sortie enregistrée » ;
   - **Déjà pointé** : un second scan à moins de 2 minutes est ignoré ;
   - ❌ **Pointage refusé**, avec le motif (voir §13).

Votre position n'est lue qu'au moment du pointage, jamais en continu.

Les autres onglets :

- **Mon QR** : votre QR personnel, à présenter à la borne si votre téléphone n'a pas de
  connexion (voir §6).
- **Aujourd'hui** : vos pointages du jour (heure, sens, site).
- **Mes demandes**, en haut de l'écran : justifier un retard, signaler un oubli, etc. (voir §8).
- **Mon historique**, dans le back-office : vos journées, l'export CSV et le bouton
  **Contester un pointage**.

### Petites structures sans borne (mode D)

Un **QR de site imprimé** peut être affiché au mur. Le contrôle repose alors sur la position et le
téléphone lié ; la confiance est notée « moyenne ».

## 6. Agents sans smartphone : badge et QR personnel

| Mode | Comment ça marche | Confiance |
|---|---|---|
| A — borne + téléphone | l'agent scanne le QR de la borne | élevée |
| B — QR personnel | l'application affiche un QR qui change toutes les 30 s, la borne le scanne (utile sans connexion) | élevée |
| C — badge imprimé | carte QR, scannée par la borne | moyenne |
| D — QR de site affiché seul | voir §5 | moyenne |

- **Imprimer les badges** : ouvrez `Rapports`, choisissez **Planche de badges QR (PDF)**, puis
  imprimez et plastifiez.
- **Badge perdu** : sur la fiche de l'agent, cliquez sur **Réimprimer le badge**. L'ancienne carte
  est aussitôt refusée (« Badge remplacé »).

## 7. Service RH : suivre la journée

### Tableau de bord (`Tableau de bord`), mis à jour en direct

- **Présents** (sur le nombre attendu, et combien sont sur site), **En retard** et taux de
  ponctualité, **Absents** (attendus et pas encore arrivés), **Partis tôt**.
- Nombre d'**anomalies de fraude** : refus pour QR rejoué, position simulée, téléphone non
  autorisé…
- **Flux en direct** : chaque pointage apparaît dès qu'il est fait.
- Graphiques : **Arrivées par heure** et **Ponctualité des services** sur 30 jours.
- État des **sites** et des **bornes** (en ligne, pointages hors-ligne en attente). Un raccourci
  **Appairer une tablette** est aussi proposé.

### Pointages (`Pointages`)

C'est la liste brute de tous les pointages, y compris les **refusés** : chaque tentative est
conservée avec son motif. Colonnes : jour, heure, agent, sens, mode, site et résultat (accepté,
doublon, refusé, hors-ligne, distance au site).

Les pointages ne peuvent **jamais être modifiés ni supprimés** : une correction crée un nouvel
enregistrement et l'original reste visible (voir §8).

## 8. Demandes, justificatifs et corrections

Menu `Demandes`, accessible à tous les rôles.

### Côté agent

1. Cliquez sur **Nouvelle demande** et choisissez l'objet : retard, absence, départ anticipé,
   oubli de pointage, pointage erroné ou heures supplémentaires.
2. Indiquez la date concernée. Pour un oubli de pointage, ajoutez le sens (entrée ou sortie) et
   l'heure réelle.
3. Écrivez le motif et joignez un justificatif si besoin, puis cliquez sur **Envoyer**.
4. Tant que la demande n'est pas traitée, vous pouvez cliquer sur **Annuler ma demande**.

### Côté manager et RH

1. Le filtre **À traiter** montre les demandes qui vous attendent. Le statut indique l'étape :
   « En attente du manager », « En attente du RH », « Validée », « Refusée » ou « Annulée ».
2. Ouvrez la pièce jointe, ajoutez un commentaire, puis cliquez sur **Valider** ou **Refuser**.
3. **Circuit à 2 niveaux** : le manager valide d'abord, puis le RH. Si l'agent n'a pas de
   manager, la demande va directement au RH.

Une validation met la journée à jour (par exemple « Retard justifié » ou « Absence justifiée »).
Une correction ajoute le pointage manquant sans effacer l'original, et l'opération est inscrite
au journal d'audit. Une demande refusée ne change rien.

## 9. Changement de téléphone

Quand un agent se connecte depuis un nouveau téléphone, l'application le prévient et une demande
part au service RH. Le RH ouvre `Téléphones`, puis clique sur **Valider** (« Nouveau téléphone
lié ») ou **Refuser**. L'ancien téléphone ne peut plus pointer.

## 10. Rapports et clôture du mois

Menu `Rapports`. Choisissez le type de rapport puis cliquez sur **Générer**. Le fichier est
préparé en arrière-plan ; une progression s'affiche, puis le bouton **Télécharger**.

| Rapport | Contenu |
|---|---|
| Ponctualité (Excel) | retards et absences par agent et par service |
| Feuille de présence mensuelle (PDF) | une fiche par agent, prête à signer |
| Éléments variables de paie (Excel) | heures travaillées, heures supplémentaires, absences |
| Pointages (CSV) | tous les pointages de la période |
| Planche de badges QR (PDF) | badges à imprimer (§6) |

- **Liens de téléchargement** : ils sont signés et ont une durée de vie limitée ; ne les partagez
  pas.

### Envois automatiques

Sous la liste des rapports, le bloc **Envois automatiques** sert à programmer un envoi par
e-mail :

1. Choisissez le rapport, la fréquence (**Chaque lundi** pour la semaine écoulée, ou **Chaque fin
   de mois**) et les destinataires, séparés par des virgules.
2. Cliquez sur **Programmer**.
3. Chaque envoi peut ensuite être **mis en pause**, **repris** ou **supprimé**.

### Clôture du mois

Bloc **Clôture mensuelle**, réservé au RH et à l'administrateur.

1. Une fois la paie préparée, choisissez le mois et cliquez sur **Clôturer le mois**.
2. La clôture tourne en arrière-plan (« clôture en cours… ») : toutes les journées du mois sont
   recalculées, puis le mois est figé. Comptez quelques minutes pour une centaine d'agents ; vous
   pouvez continuer à travailler.
3. Le mois apparaît ensuite comme **clôturé** : plus aucun pointage ni aucune correction n'est
   accepté sur ce mois (« Période clôturée »).

Seul l'**administrateur** peut rouvrir un mois. Il clique sur **Rouvrir**, puis saisit un motif
obligatoire ; la réouverture est inscrite au journal d'audit.

## 11. Manager et auditeur

- **Manager** : il voit le tableau de bord, les pointages et les agents, et valide en premier
  niveau les demandes de son équipe.
- **Auditeur** : il consulte tout en lecture seule, dont le **Journal d'audit**. Ce journal
  répond à « qui a fait quoi, quand, sur quel objet », avec les valeurs avant et après ; on
  peut le filtrer par action (par exemple `checkin.corrected`). Le journal ne peut être ni
  modifié ni effacé.

## 12. Équipe PointQR : l'espace plateforme

Connexion sans code entreprise, puis `/plateforme`.

- Chiffres globaux : entreprises, entreprises actives, agents, pointages du jour.
- **Nouvelle entreprise**, en quelques étapes :
  1. raison sociale, code entreprise (4 à 12 caractères), secteur ;
  2. formule (Essentiel… Grand compte) et limites d'agents, de sites et de bornes ;
  3. identifiant et mot de passe provisoire de l'administrateur. La double authentification lui
     sera demandée à la première connexion.
- **Suspendre une entreprise** bloque tous ses pointages (« Entreprise suspendue »).
- L'équipe PointQR **consulte** les données des clients mais ne peut **pas** modifier un
  pointage : l'isolation entre entreprises est garantie par la base de données elle-même.

## 13. Comprendre un refus de pointage

| Message | Cause | Que faire |
|---|---|---|
| QR expiré | le QR date de plus de 30 s (photo, capture d'écran) | scanner la borne directement |
| QR déjà utilisé | même QR, même téléphone, scanné deux fois | attendre le QR suivant |
| QR invalide | ce n'est pas un QR PointQR, ou il a été modifié | scanner la borne de votre site |
| Borne révoquée | la borne a été désactivée | prévenir l'administrateur |
| Badge remplacé | un nouveau badge a été imprimé | utiliser le nouveau badge |
| Téléphone non activé | aucun téléphone lié | onglet « Activer ce téléphone » |
| Appareil non autorisé | ce téléphone n'est pas celui de l'agent | demande de changement (§9) |
| Position absente | localisation refusée ou indisponible | autoriser la localisation, réessayer |
| Position simulée | application de fausse position détectée | la désinstaller |
| Hors zone | trop loin du site | pointer sur place ; l'administrateur peut élargir le rayon |
| Wi-Fi non autorisé | Wi-Fi exigé et réseau non reconnu | se connecter au Wi-Fi de l'entreprise |
| Agent inactif | la fiche agent est désactivée | voir le service RH |
| Entreprise suspendue | abonnement suspendu | voir l'administrateur |
| Pointage hors-ligne trop ancien | pointage de borne envoyé plus de 7 jours après | justification au RH |
| Période clôturée | le mois est clôturé | voir le service RH |
| Doublon (moins de 2 minutes) | second scan juste après le premier | rien : le premier compte |

Chaque refus est enregistré avec son motif : le RH le voit dans `Pointages` et dans les anomalies
du tableau de bord.

## 14. Statuts d'une journée et règles de calcul

| Statut | Signification |
|---|---|
| En cours | journée commencée, pas encore terminée |
| Présent | arrivée dans la tolérance |
| En retard / Retard justifié | arrivée après la tolérance ; justifiée par une demande validée |
| Absent / Absence justifiée | aucun pointage un jour travaillé ; justifiée par une demande validée |
| Incomplète | il manque une sortie (ou une entrée) : l'agent est prévenu et peut faire une demande |
| Jour férié / Non travaillé | aucun pointage attendu |

Règles à connaître :

- **L'heure du serveur fait foi.** L'heure du téléphone n'est jamais lue.
- **Un retard se compte depuis l'heure prévue**, pas depuis la fin de la tolérance. Exemple :
  arrivée prévue à 7:30, tolérance de 10 min, pointage à 7:52 → **22 min** de retard. À 7:38, on
  est à l'heure.
- Les pointages alternent entrée et sortie (et pauses si elles sont activées). Un second scan à
  moins de 2 minutes est ignoré.
- Un poste de nuit est rattaché à son jour de début.
- Les heures travaillées un jour férié ou non travaillé sont comptées sans déduire de pause.

## 15. Astuces

- **Ctrl+K** pour aller n'importe où dans le back-office.
- Le thème clair/sombre et la réduction des animations se règlent dans `Paramètres`. Les
  animations sont aussi réduites si votre système le demande.
- Sur la borne, réglez la tablette pour qu'elle ne se mette jamais en veille et utilisez le mode
  plein écran du navigateur.
- Un agent peut exporter son historique en CSV (`Mon historique`).

## 16. Essayer avec les données de démonstration

Après `tasks.ps1 seed` (ou `docker-seed`), vous disposez de deux entreprises fictives et de deux
mois d'historique.

| Code entreprise | Identifiants |
|---|---|
| `MINX` | `admin`, `rh`, `manager`, `agent`, `auditeur` |
| `PMEY` | `admin`, `agent` |
| *(vide)* | `editeur` (équipe PointQR) |

- Mot de passe de tous les comptes : `Demo-PointQR-2026`.
- Secret TOTP des comptes admin, RH et éditeur : `PQRDEMOPQRDEMOPQRDEMOPQRDEMOPQRD`, à ajouter dans
  votre application d'authentification.

Parcours en 5 minutes :

1. Connectez-vous en `rh` (MINX) et regardez le **tableau de bord**.
2. Ouvrez `Bornes` → **Nouvelle borne** → **Générer le code**, et saisissez-le sur `/kiosk` dans
   un autre onglet ou sur une tablette.
3. Sur un téléphone (ou un second navigateur), ouvrez `/agent`, connectez-vous en `agent` (MINX),
   **activez le téléphone** et **scannez** le QR de la borne.
4. Le pointage apparaît aussitôt dans le **flux en direct** du tableau de bord.
5. En `agent`, envoyez une **demande** de justification, puis validez-la en `manager` et en `rh`.

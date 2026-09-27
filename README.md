# OpenAgenda Slides

Transforme **votre agenda OpenAgenda en diaporama d'écrans** : l'app
génère automatiquement une belle diapositive par événement (image,
date, lieu, tarif, public…) pour vos téléviseurs, bornes ou panneaux
d'affichage — en paysage 16:9, en portrait 9:16 ou en A4 imprimable.

Aucune compétence technique nécessaire : téléchargez, indiquez votre
agenda, cliquez sur **Générer**.

<p align="center">
  <img src="docs/screenshots/slide-landscape.png" width="49%" alt="Diapo paysage 16:9 générée">&nbsp;<img src="docs/screenshots/slide-portrait-screen.png" height="440" alt="Diapo portrait 9:16 générée"><br>
  <img src="docs/screenshots/window-general.png" width="80%" alt="Fenêtre de l'application">
</p>

> **English** — turns any public OpenAgenda agenda into ready-to-broadcast
> slides (16:9, 9:16 portrait, A4), for TVs and digital signage.
> Portable Windows app / Linux AppImage, no install, no technical
> skills required. [Quickstart in English](#english-quickstart) below.

---

## Installation

### Windows

1. Téléchargez `oaslides-windows-…zip` depuis la page
   [Releases](https://github.com/dewiweb/openagenda-slides/releases).
2. Décompressez le zip où vous voulez (clé USB, bureau…).
3. Double-cliquez sur `oaslides.exe`.

> Windows peut afficher « Windows a protégé votre ordinateur »
> (SmartScreen) car l'app n'est pas signée — c'est normal pour un
> logiciel gratuit : cliquez **Informations complémentaires →
> Exécuter quand même**.

### Linux

1. Téléchargez `oaslides-linux-…AppImage` depuis
   [Releases](https://github.com/dewiweb/openagenda-slides/releases).
2. Rendez le fichier exécutable : clic droit → *Propriétés →
   Permissions → Autoriser l'exécution*, ou en terminal
   `chmod +x oaslides-linux-*.AppImage`.
3. Double-cliquez dessus (ou glissez-la dans votre lanceur favori,
   ex. Gear Lever).

Aucune installation, aucun droit administrateur : le dossier
`oaslides-data/` créé à côté contient vos réglages, images et
diapositives — tout est portable, supprimable d'un coup.

---

## Première utilisation

Tout se passe dans l'onglet **Général**.

### 1. Indiquez votre agenda

Champ **Agenda** : le nom qui figure dans l'adresse de votre agenda
OpenAgenda. Si votre agenda est à
`https://openagenda.com/agendas/mediatheque-de-ma-ville`,
tapez `mediatheque-de-ma-ville`.

Cliquez **Tester la connexion** : l'app vous confirme le nom de
l'agenda trouvé et le nombre d'événements publiés.

> **Clé API ? Optionnelle.** Sans clé, l'app utilise l'export public
> de votre agenda — ça marche tel quel. La clé v2 (gratuite, dans les
> paramètres de votre compte OpenAgenda) apporte une taxonomie plus
> complète et évite de dépendre de l'export legacy, déprécié.

### 2. Choisissez les catégories à diffuser

Dès que l'agenda est reconnu, ses **catégories apparaissent en
cases à cocher** (les vôtres, pas une liste générique) : décochez ce
que vous ne voulez pas voir sur les écrans. Tout coché = tout
l'agenda.

### 3. Personnalisez le rendu

Dans **Identité visuelle** :

- **Structure** : le nom affiché sur les diapos.
- **URL du programme** : votre vraie adresse (ex.
  `mediatheque.maville.fr/agenda`) — le `https://` est masqué à
  l'affichage.
- **Accroche** : le texte avant l'adresse — « Tout le programme
  sur », « Retrouvez-nous sur »… ou vide pour ne rien afficher.
- **Logo**, **fond**, **accentuation**, **fonte** : votre charte.
  Le logo sert aussi de filigrane sur les diapos sans image.
  *Format idéal : SVG monochrome (il est reteinté automatiquement
  selon le contexte) ou PNG/WebP à fond transparent, plutôt carré,
  ≥ 800 px. Le logo de série optionnel suit la même règle — il
  remplace le rond de série dans la diapo du jour.*

Le bouton **Aperçu d'une diapo** rend un vrai événement avec vos
réglages — itérez sur les couleurs sans attendre une génération
complète.

### 4. Générez

**Générer** (en haut) produit les diapos dans
`oaslides-data/diaporama/` — sauf si vous avez choisi une autre
destination dans l'onglet **Destinations** :

| Destination | Pour qui |
|---|---|
| **Dossier local** | par défaut — `landscape/`, `portrait/`, `today/` |
| **FTP** | votre player/régie récupère les fichiers en FTP |
| **SMB** | partage Windows réseau (`\\serveur\partage`) |

Vous pouvez aussi **automatiser** : toutes les X minutes et/ou à
heures fixes, l'app régénère et synchronise toute seule.

### 5. Diffusez

- **Diaporama intégré** : lecture plein écran des diapos générées,
  transitions et délai réglables, écran choisi — idéal pour un poste
  branché directement sur la TV.
- Ou pointez votre solution d'affichage (Xibo, player FTP, visionneuse
  d'images…) vers le dossier de sortie.

### 6. La « Diapo du jour »

Pendant un événement en cours : un fond sombre élégant avec titre,
intervenants, animateur, notes pratiques, accessibilité. Éditez-la
dans l'onglet **Diapo du jour**, elle rejoint les destinations
configurées.

---

## Réglages en détail

### Informations affichées

Chaque ligne d'information de la diapo (durée, lieu, tarif, public,
accessibilité) peut être **masquée** ou **forcée** — ex. lieu forcé à
« Médiathèque Totems » si votre agenda utilise mal le champ lieu, ou
pour afficher une valeur constante même quand l'événement n'en a pas.

Le préfixe des événements récurrents (« Prochaine séance : » par
défaut) est modifiable — videz-le pour n'afficher que la date.

### Séries éditoriales

Pour mettre en avant vos temps forts : une ligne par série
`mot-clé = Libellé [| logo.png]`. Tout événement portant ce mot-clé
OpenAgenda reçoit le libellé (et le logo) en badge. **Détecter dans
les mots-clés** balaie l'agenda et propose les mots-clés fréquents —
vous n'avez qu'à compléter les libellés.

### Formats

- **Paysage** : HD 1920×1080 ou UHD 3840×2160.
- **Portrait** : *A4 impression* ou *9:16 écran*.

### Onglet Style — retouche visuelle

L'onglet **Style** règle la mise en page de chaque format (arrondis,
tailles de texte, nombre de lignes, filigranes…) avec un **aperçu réel
re-rendu à chaque modification** — débrayable via « Aperçu
automatique ». Seuls les écarts au gabarit d'origine sont enregistrés ;
« Réinitialiser ce format » restaure tout. Pour aller plus loin, les
gabarits HTML eux-mêmes sont documentés dans `assets/README.md`.

### Sécurité

Mots de passe et clé API partent dans le **trousseau de votre système**
(Credential Manager Windows, Secret Service Linux) quand il existe.
Pour une utilisation « kiosque » sans trousseau, la variable
d'environnement `OASLIDES_*` correspondante prime toujours.

---

## Questions fréquentes

**La connexion échoue / aucun événement ?**
Vérifiez le slug dans l'adresse de votre agenda sur openagenda.com.
L'agenda doit être **public** — et avoir des événements publiés à
venir ou en cours.

**« aucun groupe de tags » ?**
Votre agenda n'a pas de catégories configurées dans OpenAgenda — les
diapos afficheront alors la pastille générique. Vous pouvez toujours
filtrer à la main dans « Tags retenus ».

**Mes événements n'ont pas d'image ?**
Le visuel de chaque diapo vient de l'illustration OpenAgenda de
l'événement. Sans illustration, un fond neutre + votre logo en
filigrane est utilisé — mais le plus simple reste d'illustrer vos
fiches sur OpenAgenda.

**Un réglage ne semble pas pris en compte ?**
Les réglages sont appliqués à l'enregistrement — le bouton
**Enregistrer** en haut à droite s'allume dès qu'un champ est modifié.

**Se mettre à jour ?**
L'app vérifie discrètement au démarrage et vous signale une nouvelle
version quand il y en a une (bouton **Vérifier les mises à jour**
dans Général pour le faire à la demande) — téléchargez-la et
remplacez l'ancien fichier ; `oaslides-data/` garde vos réglages.

**Tout supprimer ?**
Supprimez l'exécutable **et** le dossier `oaslides-data/` à côté
— rien d'autre n'est installé.

---

## Pour les développeurs

Application **Qt Widgets** (PySide6), Python ≥ 3.10 — pas de serveur,
pas de navigateur visible : les diapos sont des gabarits HTML rendus
en PNG via Playwright (Chromium headless embarqué dans les builds).

```bash
python -m venv venv && venv/bin/pip install -r requirements.txt
venv/bin/python -m playwright install chromium --only-shell
venv/bin/python desktop.py                       # UI
venv/bin/python desktop.py --diag                # diagnostic de rendu
python -m unittest discover -s tests             # smoke tests
```

Packaging : `pyinstaller app.spec` puis `appimage/build-appimage.sh` ;
les Releases sont construites par GitHub Actions à chaque tag `v*`.

Projet dérivé de `nextevents-desktop` (Les Champs Libres, Rennes),
réécrit en version générique : source unique OpenAgenda, aucune
dépendance au site d'une organisation.

### Limites connues

- L'export public legacy est **déprécié** par OpenAgenda (toujours
  fonctionnel) — une clé API v2 est recommandée en production.
- L'extraction des intervenants/animateurs pour la diapo du jour est
  heuristique (`<strong>`, « animée par… ») : vide plutôt que fausse
  chez des agendas au style de rédaction différent.

---

## English quickstart

**OpenAgenda Slides** turns any *public* OpenAgenda agenda into a set
of event slides, ready for TVs, kiosks and digital signage — landscape
16:9, portrait 9:16, or printable A4.

1. Download `oaslides-windows-…zip` or `oaslides-linux-…AppImage`
   from [Releases](https://github.com/dewiweb/openagenda-slides/releases)
   (Windows may show a SmartScreen notice — the app isn't signed;
   *More info → Run anyway*).
2. Launch it, type your agenda slug (the name in
   `openagenda.com/agendas/<your-agenda>`), click **Générer**.
3. No API key needed — the app uses the agenda's public export.
   An OpenAgenda v2 key (free, in your account settings) is
   recommended for richer taxonomies and longevity.

Branding (colors, logo, font, footer, per-format layout metrics) is
adjusted in the **Style** tab with a live preview; slides can be
pushed automatically to an FTP server, an SMB share or another folder.
The interface is French — everything else is language-agnostic.
- Les champs personnalisés (`custom`) des agendas ne sont pas
  affichés.

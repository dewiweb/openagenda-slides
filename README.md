# OpenAgenda Slides

Génère un diaporama de diapos PNG à partir de **n'importe quel agenda
OpenAgenda** — pour diffusion sur écrans (paysage 16:9, portrait 9:16)
et impression (portrait A4). Application desktop Qt (Windows portable /
AppImage Linux), sans serveur web.

Dérivé de `nextevents-desktop` (Les Champs Libres, Rennes), en version
générique : aucune dépendance au site d'une organisation — la source
unique est OpenAgenda.

## Principe

1. L'app récupère les événements à venir de votre agenda OpenAgenda
   (API v2 si vous avez une clé, sinon l'export public legacy).
2. Chaque événement devient une diapo : titre, image, catégorie,
   date/durée/lieu/tarif/public, description (markdown interprété).
3. Les PNG sont écrits localement et/ou poussés vers un FTP, un
   partage SMB ou un autre dossier — arborescence identique partout :

```
sortie/  →  destination/
├── landscape/    diapos 16:9 (+ html/, manifest.txt)
├── portrait/     A4 ou 9:16 selon le réglage (+ html/, manifest.txt)
├── today/        « diapo du jour » (index.*, qr.*)
└── events.json   métadonnées (fiches, régénération)
```

4. Un diaporama plein écran intégré lit `landscape/` ou `portrait/`.

## Configuration (onglet Général)

| Réglage | Rôle |
|---|---|
| **Agenda** | slug ou uid numérique OpenAgenda (ex. `mon-agenda`) — obligatoire |
| **Clé API v2** | optionnelle ; sans clé, l'export public est utilisé |
| **Groupe catégorie** | slug du tagGroup affiché en pastille (vide = auto) |
| **Tags retenus** | slugs/libellés à inclure, virgules (vide = tout) |
| **Structure / URL / logo** | nom, page programme, logo SVG/PNG |
| **Fond / Accentuation** | couleurs `#rrggbb` des diapos |
| **Fonte** | famille CSS — déposez des `.woff2/.ttf` dans `data/fonts/` |
| **Séries éditoriales** | `keyword OA = Libellé [| logo.png]`/ligne |

La taxonomie vient des **tagGroups** de chaque agenda (bouton
« Lister les groupes de tags ») : catégories, publics, groupes
personnalisés — aucune correspondance codée en dur.

Les secrets (clé API, mots de passe FTP/SMB) partent dans le trousseau
de l'OS quand il existe ; les variables `OASLIDES_*` priment toujours.

## Diapo du jour

Diapo fixe sans visuel (fond sombre) pour la diffusion pendant un
événement : titre, intervenants, animateur, notes, accessibilité,
badge de série. Le QR compagnon pointe vers le permalink OpenAgenda
de l'événement.

## Lancer en développement

```bash
python -m venv venv && venv/bin/pip install -r requirements.txt
venv/bin/python -m playwright install chromium   # ou OASLIDES_BROWSER_CHANNEL
venv/bin/python desktop.py                       # UI Qt
venv/bin/python desktop.py --diag                # diagnostic de rendu
```

Tests : `python -m unittest discover -s tests -v`

## Limites connues

- L'export legacy public est **déprécié** par OpenAgenda (toujours
  fonctionnel à ce jour) — une clé API v2 est recommandée en
  production.
- L'extraction des intervenants/animateurs est heuristique
  (`<strong>`, « animée par… ») — calibrée sur un style de rédaction
  francophone ; vide plutôt que faux chez d'autres agendas.
- Champs `custom` OpenAgenda non exploités (propres à chaque agenda).

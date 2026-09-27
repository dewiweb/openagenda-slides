# Gabarits de diapos

Les diapos sont dessinées en HTML/CSS, remplies par `oaslides/slide.py`
(`string.Template`, marqueurs `$nom`) puis capturées en PNG par Chromium.

## Fichiers

| Fichier | Rôle |
|---|---|
| `slide_base.css` | **Charte commune** aux 3 gabarits « événement » : carte, filigranes, visuel, pastille, specs, pied de page. Chaque règle est groupée et commentée par section. |
| `slide_template.html` | Paysage 16:9 — 1920×1080. Visuel à gauche, textes à droite. |
| `slide_template_portrait.html` | Portrait A4 — 1240×1754 (impression, 300 dpi en UHD). Visuel en haut. |
| `slide_template_portrait_screen.html` | Portrait écran 9:16 — 1080×1920 (écran monté en vertical). |
| `today_template.html` | « Diapo du jour » sombre : composition centrée, auto-fit JS (`--k`), variante « série ». Autonome, ne partage pas la base. |
| `check.svg` | Coche des cases à cocher de l'UI Qt (rien à voir avec les diapos). |

## Comment ça marche

1. `slide.py` lit le gabarit et remplace la ligne `@import "slide_base.css";`
   par le contenu de la base — le HTML produit reste autonome.
2. Les marqueurs `$…` sont remplis au rendu : chaque gabarit documente
   les siens dans son en-tête HTML.
3. Chaque gabarit définit ses métriques dans `:root{ --… }` — ce sont les
   valeurs consommées par la base. **Ajuster un format = éditer ses
   variables**, sans toucher à la charte. **Modifier la charte = éditer
   `slide_base.css`**, valable pour les trois orientations.

## Modifier un gabarit

- Réglages courants (arrondis, tailles de texte, lignes max,
  filigranes) : **depuis l'onglet Style de l'app** — aperçu en direct,
  sans toucher aux fichiers. Les valeurs retouchées sont injectées en
  fin de `:root` via `$style_overrides`.
- Couleurs, logo, fonte, accroche : **depuis l'onglet Réglages de
  l'app** (pas besoin de toucher au HTML).
- Taille des textes, espacements, rayons, position des éléments :
  le bloc `:root` du gabarit concerné.
- Forme d'un élément commun (pastille, filet, filigrane…) :
  la section correspondante de `slide_base.css`.
- Structure/composition : le HTML en fin de gabarit + ses règles de layout.

## Prévisualiser

L'app conserve le HTML rempli à côté des PNG
(`sortie/<format>/html/*.html`) : on peut l'ouvrir dans un navigateur,
ou modifier le gabarit et relancer une génération — le bouton
« Aperçu d'une diapo » de l'onglet Général est le plus rapide.

> Attention : `string.Template` interprète `$` — pour un `$` littéral
> dans le CSS, écrire `$$`.

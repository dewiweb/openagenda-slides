# Changelog

## v1.0.0 — première version stable

Application Qt desktop autonome : génère une diapo par événement de
n'importe quel agenda OpenAgenda public, pour diffusion d'écrans.

- **Sources** : export public OpenAgenda sans clé, API v2 optionnelle
  (clé dans le trousseau système) — taxonomie découverte et proposée
  en cases à cocher.
- **Formats** : paysage 16:9 HD/UHD, portrait A4 ou 9:16, « diapo du
  jour » éditoriale (intervenants, série, logo).
- **Style** : onglet dédié — identité (logo, couleurs, fonte, pied de
  page) et métriques de mise en page retouchables avec aperçu réel
  re-rendu à chaque modification ; verdict de résolution de fonte.
- **Diffusion** : dossier local, FTP(S), SMB ; player diaporama plein
  écran multi-écran intégré ; galerie avec aperçu F11, régénération
  et suppression unitaires, export zip.
- **Packaging** : ZIP Windows portable et AppImage Linux construits
  par CI à chaque tag ; données dans `oaslides-data/` (portable) ;
  secrets dans le trousseau OS ; vérification de mise à jour au
  démarrage ; licence MIT.

Historique des betas : voir les releases `v0.1.0-beta.*`.

"""oaslides — diaporama d'événements pour n'importe quel agenda
OpenAgenda.

Modules :
  paths     chemins (racine, assets, cache)
  extract   extraction générique : markdown, intervenants, séries…
  oa        source OpenAgenda (API v2 ou export public legacy)
  media     images OpenAgenda, cache, fontes optionnelles
  slide     gabarits HTML + rendu PNG (Playwright / chromium headless)
  sync      envoi FTP / SMB / copie locale vers le poste de diffusion
  today     diapo du jour (édition, rendu, envoi)
  generate  orchestration de la génération complète
  settings  réglages persistés + état runtime
  runner    exécution des générations + planificateur
  secrets   identifiants dans le trousseau OS (keyring) ou env
"""

from .generate import generate  # noqa: F401
from .slide import SIZES, DEFAULT_SIZE  # noqa: F401

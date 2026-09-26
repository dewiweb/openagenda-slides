"""Chemins du projet — racine, assets, cache.

Surchargeables par variables d'environnement (usage desktop figé :
assets en lecture seule dans le bundle, cache/fontes dans ./data) :
OASLIDES_ASSET_DIR, OASLIDES_FONT_DIR, OASLIDES_CACHE_DIR,
OASLIDES_OUT_DIR."""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSET_DIR = Path(os.environ.get("OASLIDES_ASSET_DIR", ROOT / "assets"))
FONT_DIR = Path(os.environ.get("OASLIDES_FONT_DIR", ASSET_DIR / "fonts"))
CACHE_DIR = Path(os.environ.get("OASLIDES_CACHE_DIR", ASSET_DIR / "cache"))
OA_MAP_FILE = CACHE_DIR / "oa-map.json"
OUT_DIR = Path(os.environ.get("OASLIDES_OUT_DIR", ROOT / "diaporama"))

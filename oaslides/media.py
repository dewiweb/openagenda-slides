"""Médias : images d'événements (cache), fontes optionnelles.

Fontes : tout fichier .woff2/.woff/.ttf déposé dans le dossier
`fonts/` (à côté des assets, ou OASLIDES_FONT_DIR) est embarqué via
@font-face ; `font_family` dans les réglages choisit la famille CSS
(vide = pile système). Aucune fonte n'est fournie par défaut —
l'utilisateur apporte la sienne (licence) ou utilise le système.
"""

import base64
import re
from pathlib import Path
from urllib.parse import urlsplit

from .paths import FONT_DIR, CACHE_DIR
from .net import get


def b64_file(path):
    return base64.b64encode(Path(path).read_bytes()).decode()


def ensure_fonts():
    """Fontes embarquées : fichiers déposés dans FONT_DIR →
    {"faces": css @font-face, "family": première famille trouvée}.
    Vide si aucune fonte — les gabarits utilisent alors la pile
    système configurée dans `font_family`."""
    faces = []
    families = []
    for p in sorted(FONT_DIR.glob("*")) \
            if FONT_DIR.exists() else []:
        if p.suffix.lower() not in (".woff2", ".woff", ".ttf", ".otf"):
            continue
        fmt = {"woff2": "woff2", "woff": "woff", "ttf": "truetype",
               "otf": "opentype"}[p.suffix.lower()]
        family = re.sub(r"[-_]+", " ", p.stem).strip()
        # poids heuristique depuis le nom de fichier
        w = ("700" if re.search(r"bold|black|heavy", p.stem, re.I)
             else "500" if re.search(r"medium|demi", p.stem, re.I)
             else "300" if re.search(r"light|thin", p.stem, re.I)
             else "400")
        faces.append(
            f"@font-face{{font-family:'{family}';font-weight:{w};"
            f"src:url(data:font/{fmt};base64,{b64_file(p)}) "
            f"format('{fmt}')}}")
        if family not in families:
            families.append(family)
    return {"faces": "".join(faces),
            "family": families[0] if families else "",
            "families": families}


def download_image(ev):
    """Télécharge l'image et la retourne en data URI (HTML autonome).
    Cache local : les URLs d'images sont versionnées, on ne retélécharge
    jamais deux fois la même (sobriété)."""
    url = ev.get("image") or ev.get("card_img")
    if not url:
        ev["img_data"] = None
        return ev
    cache = CACHE_DIR / Path(urlsplit(url).path).name
    try:
        if cache.exists():
            data, mime = cache.read_bytes(), "image/jpeg"
        else:
            r = get(url)
            data = r.content
            mime = r.headers.get("Content-Type", "image/jpeg").split(";")[0]
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_bytes(data)
        ev["img_data"] = \
            f"data:{mime};base64,{base64.b64encode(data).decode()}"
        return ev
    except Exception as e:
        print(f"  ! image KO {url} : {e}")
    ev["img_data"] = None
    return ev

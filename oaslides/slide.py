"""Rendu des diapos : gabarits HTML (assets/) puis capture
Playwright/Chromium (repli firefox --headless).

L'identité visuelle vient des réglages (`brand()`) : fond, accent,
logo, fonte — aucun asset n'est propre à une organisation."""

import html
import io
import os
import re
import subprocess
import tempfile
import time
from pathlib import Path
from string import Template

from PIL import Image

from .paths import ASSET_DIR
from .extract import SPEC_ICONS, SPEC_ORDER

SIZES = {"hd": (1920, 1080), "uhd": (3840, 2160)}
DEFAULT_SIZE = SIZES["uhd"]

INK = "#141414"
DEFAULT_FONT = "'Segoe UI', 'Helvetica Neue', 'Liberation Sans', Arial, sans-serif"

ICONS = {
    "calendar": "M8 5.75c-.41 0-.75-.34-.75-.75V2c0-.41.34-.75.75-.75s.75.34.75.75v3c0 .41-.34.75-.75.75Zm8 0c-.41 0-.75-.34-.75-.75V2c0-.41.34-.75.75-.75s.75.34.75.75v3c0 .41-.34.75-.75.75Zm4.5 4.09h-17c-.41 0-.75-.34-.75-.75s.34-.75.75-.75h17c.41 0 .75.34.75.75s-.34.75-.75.75ZM16 22.75H8c-3.65 0-5.75-2.1-5.75-5.75V8.5c0-3.65 2.1-5.75 5.75-5.75h8c3.65 0 5.75 2.1 5.75 5.75V17c0 3.65-2.1 5.75-5.75 5.75ZM8 4.25c-2.86 0-4.25 1.39-4.25 4.25V17c0 2.86 1.39 4.25 4.25 4.25h8c2.86 0 4.25-1.39 4.25-4.25V8.5c0-2.86-1.39-4.25-4.25-4.25H8Z",
    "pin": "M12 14.17c-2.13 0-3.87-1.73-3.87-3.87S9.87 6.44 12 6.44s3.87 1.73 3.87 3.87-1.74 3.86-3.87 3.86Zm0-6.23c-1.3 0-2.37 1.06-2.37 2.37s1.06 2.37 2.37 2.37 2.37-1.06 2.37-2.37S13.3 7.94 12 7.94ZM12 22.76a5.97 5.97 0 0 1-4.13-1.67c-2.95-2.84-6.21-7.37-4.98-12.76C4 3.44 8.27 1.25 12 1.25h.01c3.73 0 8 2.19 9.11 7.09 1.22 5.39-2.04 9.91-4.99 12.75A5.97 5.97 0 0 1 12 22.76Zm0-20.01c-2.91 0-6.65 1.55-7.64 5.91C3.28 13.37 6.24 17.43 8.92 20a4.426 4.426 0 0 0 6.17 0c2.67-2.57 5.63-6.63 4.57-11.34-1-4.36-4.75-5.91-7.66-5.91Z",
    "ticket": "M17 20.75H7c-4.41 0-5.75-1.34-5.75-5.75v-.5c0-.41.34-.75.75-.75.96 0 1.75-.79 1.75-1.75S2.96 10.25 2 10.25c-.41 0-.75-.34-.75-.75V9c0-4.41 1.34-5.75 5.75-5.75h10c4.41 0 5.75 1.34 5.75 5.75v1c0 .41-.34.75-.75.75-.96 0-1.75.79-1.75 1.75s.79 1.75 1.75 1.75c.41 0 .75.34.75.75 0 4.41-1.34 5.75-5.75 5.75ZM2.75 15.16c.02 3.44.73 4.09 4.25 4.09h10c3.34 0 4.15-.59 4.24-3.59a3.25 3.25 0 0 1-2.49-3.16c0-1.53 1.07-2.82 2.5-3.16V9c0-3.57-.67-4.25-4.25-4.25H7c-3.52 0-4.23.65-4.25 4.09 1.43.34 2.5 1.63 2.5 3.16 0 1.53-1.07 2.82-2.5 3.16ZM10 7.25c-.41 0-.75-.34-.75-.75V4c0-.41.34-.75.75-.75s.75.34.75.75v2.5c0 .41-.34.75-.75.75s.75.34.75.75v3.67c0-.41.34-.75.75-.75s.75.34.75.75v3.67c0 .42-.34.75-.75.75Zm0 6.17c-.41 0-.75-.34-.75-.75v-2.5c0-.41.34-.75.75-.75s.75.34.75.75V20c0 .41-.34.75-.75.75Z",
    "timer": "M12 22.75c-5.24 0-9.5-4.26-9.5-9.5s4.26-9.5 9.5-9.5 9.5-4.26 9.5-9.5 9.5-4.26 9.5-9.5ZM12 5.25c-4.41 0-8 3.59-8 8s3.59 8 8 8 8-3.59 8-8-3.59-8-8-8Zm0 8.5c-.41 0-.75-.34-.75-.75V8c0-.41.34-.75.75-.75s.75.34.75.75v5c0 .41-.34.75-.75.75Zm3-11H9c-.41 0-.75-.34-.75-.75s.34-.75.75-.75h6c.41 0 .75.34.75.75s-.34.75-.75.75Z",
    "group": "M16.5 7.25h-.119c-1.732-.054-3.025-1.392-3.025-3.042a3.057 3.057 0 0 1 3.053-3.053 3.063 3.063 0 0 1 3.052 3.053A3.05 3.05 0 0 1 16.51 7.26c0-.01 0-.01-.01-.01Zm-.091-4.73a1.678 1.678 0 0 0-.064 3.356c.009-.01.082-.01.165 0a1.68 1.68 0 0 0-.101-3.355Zm.1 11.487a6.05 6.05 0 0 1-1.072-.092.687.687 0 1 1 .238-1.357c1.128.193 2.32-.018 3.117-.55.431-.284.66-.641.66-.999 0-.357-.238-.706-.66-.99-.797-.531-2.007-.742-3.144-.54a.68.68 0 0 1-.798-.56.688.688 0 0 1 .56-.797c1.494-.266 3.043.018 4.143.751.807.541 1.274 1.311 1.274 2.136 0 .816-.458 1.595-1.274 2.145-.834.55-1.916.853-3.043.853ZM5.474 7.25h-.018a3.047 3.047 0 0 1-2.952-3.043 3.065 3.065 0 0 1 3.052-3.062 3.063 3.063 0 0 1 3.053 3.052 3.035 3.035 0 0 1-2.943 3.053l-.192-.688.064.688h-.064Zm.092-1.375c.055 0 .1 0 .155.009.816-.037 1.531-.77 1.531-1.677a1.678 1.678 0 1 0-1.769 1.677c.01-.01.046-.01.083-.01Zm-.102 8.13c-1.127 0-2.209-.302-3.043-.852-.807-.54-1.274-1.32-1.274-2.145 0-.816.467-1.595 1.274-2.136 1.1-.733 2.65-1.017 4.143-.751a.688.688 0 0 1 .56-.797.68.68 0 0 1-.798.56c-1.137-.202-2.337.009-3.144.54-.431.284-.66.633-.66.99 0 .358.238.715.66 1 .797.531 1.989.742 3.117.55a.68.68 0 0 1-.798.56.688.688 0 0 1 .56-.797c1.494-.266 3.043.018 4.143.751.807.541 1.274 1.311 1.274 2.136 0 .816-.458 1.595-1.274 2.145-.853.568-1.953.861-3.053.861Zm-2.291-3.987c-.431.284-.66.641-.66.999 0 .357.238.706.66.99 1.237.834 3.336.834 4.574 0 .43-.284.66-.642.66-1 0-.357-.238-.705-.66-.99-1.228-.833-3.328-.824-4.574 0Z",
    "accessibility": "M8.786 11.192v3.724l-3.981 4.485a2.49 2.49 0 0 0 3.726 3.307L12 18.799l3.47 3.909a2.49 2.49 0 0 0 3.725-3.307l-3.98-4.485v-3.724h3.995a2.29 2.29 0 0 0 0-4.58H4.79a2.29 2.29 0 1 0 0 4.58h3.996Zm1.5 3.914v-4.414a1 1 0 0 0-1-1H4.79a.79.79 0 0 1 0-1.58h14.42a.79.79 0 0 1 0 1.58h-4.496a1 1 0 0 0-1 1v4.414a1 1 0 0 0 .252.664l4.107 4.627a.99.99 0 0 1-1.482 1.315l-3.843-4.33a1 1 0 0 0-1.496 0l-3.843-4.33a.99.99 0 0 1-1.482 1.315l4.107-4.627a.99.99 0 0 0 .252.664ZM12 4.833A1.167 1.167 0 1 0 12 2.5a1.167 1.167 0 0 0 0 2.333Zm0 1.5A2.667 2.667 0 1 0 12 1a2.667 2.667 0 0 0 0 5.333Z",
}
ICON_VIEWBOX = {"group": "0 0 22 22"}
ICON_PATH_ATTRS = {"accessibility": ' fill-rule="evenodd" clip-rule="evenodd"'}

# gabarit de conception par orientation : le HTML est dessiné pour ces
# dimensions, le PNG final est mis à l'échelle via device_scale_factor.
# Deux déclinaisons portrait : A4 (1:√2, pensée pour l'impression) et
# écran (9:16, pour un écran 16:9 monté en vertical).
DESIGNS = {
    "landscape": (1920, 1080),
    "portrait": (1240, 1754),
    "portrait-screen": (1080, 1920),
}
TEMPLATES = {
    "landscape": "slide_template.html",
    "portrait": "slide_template_portrait.html",
    "portrait-screen": "slide_template_portrait_screen.html",
}
_TEMPLATES = {}
_BASE_CSS = None
_BRAND = None
_CFG = None


def portrait_size(size, fmt="a4"):
    """Dimensions de sortie portrait pour une taille paysage `size` :
    « a4 » suit le ratio 1:√2 à la même densité que le paysage
    (HD → 1240×1754 ≈ 150 dpi, UHD → 2480×3508 ≈ 300 dpi) ;
    « screen » est l'écran pivoté (HD → 1080×1920, UHD → 2160×3840)."""
    if fmt == "screen":
        return (size[1], size[0])
    scale = size[0] / DESIGNS["landscape"][0]
    return tuple(round(d * scale) for d in DESIGNS["portrait"])


def portrait_key(fmt="a4"):
    """Clé d'orientation (DESIGNS/TEMPLATES) pour un format portrait."""
    return "portrait-screen" if fmt == "screen" else "portrait"


# Les gabarits assets/slide_template*.html partagent leur charte via
# assets/slide_base.css : la ligne `@import "slide_base.css";` du gabarit
# est remplacée par le contenu du fichier au chargement (le HTML produit
# reste autonome — tout est en ligne pour le navigateur de rendu).
BASE_CSS_IMPORT = '@import "slide_base.css";'


def _base_css():
    global _BASE_CSS
    if _BASE_CSS is None:
        _BASE_CSS = (ASSET_DIR / "slide_base.css").read_text("utf-8")
    return _BASE_CSS


def _template(orientation="landscape"):
    if orientation not in _TEMPLATES:
        src = (ASSET_DIR / TEMPLATES[orientation]).read_text("utf-8")
        if BASE_CSS_IMPORT not in src:
            raise RuntimeError(
                f"{TEMPLATES[orientation]} : ligne {BASE_CSS_IMPORT!r} "
                "introuvable — la charte commune n'est pas injectée")
        _TEMPLATES[orientation] = Template(
            src.replace(BASE_CSS_IMPORT, _base_css()))
    return _TEMPLATES[orientation]


def template_vars(orientation="landscape"):
    """Métriques d'un gabarit : valeurs `--var` déclarées dans son bloc
    :root (lues dans le fichier — source unique, pas de doublon ici)."""
    src = (ASSET_DIR / TEMPLATES[orientation]).read_text("utf-8")
    m = re.search(r":root\s*\{(.*?)\}", src, re.S)
    if not m:
        return {}
    return {k.strip(): v.strip() for k, v in
            re.findall(r"(--[\w-]+)\s*:\s*([^;]+?)\s*;", m.group(1))}


def _style_css(orientation):
    """Surcharges utilisateur → déclarations `--var:val;` injectées en
    fin du bloc :root du gabarit (clé `style_overrides` des réglages,
    remplie par l'onglet Style). Clés et valeurs validées : jamais de
    CSS arbitraire dans un fichier rendu."""
    ovr = ((_CFG or {}).get("style_overrides") or {}).get(
        orientation) or {}
    return "".join(
        f"{k}:{str(v).strip()};"
        for k, v in ovr.items()
        if re.fullmatch(r"--[\w-]+", str(k))
        and re.fullmatch(r"-?\d+(\.\d+)?(px|%|em)?|none|auto",
                         str(v).strip()))


def _hex(value, default):
    return value if re.fullmatch(r"#[0-9a-fA-F]{6}", value or "") \
        else default


def _darker(hexcol, ratio=0.78):
    """Variante foncée d'une couleur #rrggbb (badge discret, filets)."""
    r, g, b = (int(hexcol[i:i + 2], 16) for i in (1, 3, 5))
    return f"#{round(r * ratio):02x}{round(g * ratio):02x}" \
           f"{round(b * ratio):02x}"


def _file_uri(path_str, base=None):
    """Fichier image → data URI ; relatif au dossier de données."""
    p = Path(path_str).expanduser()
    if not p.is_absolute():
        p = (base or Path(".")) / p
    if not p.is_file():
        return None
    mime = {".png": "image/png", ".gif": "image/gif",
            ".webp": "image/webp", ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg"}.get(p.suffix.lower())
    if not mime:
        return None
    import base64
    return f"data:{mime};base64,{base64.b64encode(p.read_bytes()).decode()}"


def _logo_html(path_str):
    """Logo configurable : SVG injecté inline (prend la couleur du
    contexte via currentColor), autres formats en <img> data-uri."""
    path_str = (path_str or "").strip()
    if not path_str:
        return ""
    p = Path(path_str).expanduser()
    if not p.is_absolute():
        from .settings import resolve_out_dir, OUT_DIR
        for base in (resolve_out_dir().parent, OUT_DIR.parent):
            if (base / p).is_file():
                p = base / p
                break
    if p.suffix.lower() == ".svg" and p.is_file():
        return p.read_text(encoding="utf-8")
    uri = _file_uri(path_str, p.parent)
    return f'<img src="{uri}">' if uri else ""


def brand(cfg=None):
    """Identité visuelle issue des réglages (mise en cache — la génération
    la lit une fois par run). `cfg` est mémorisée pour les surcharges de
    style (_style_css)."""
    global _BRAND, _CFG
    if cfg is None:
        if _BRAND is None:
            from .settings import load_settings
            cfg = load_settings()
        else:
            return _BRAND
    agenda = (cfg.get("oa_agenda") or "").strip()
    url = (cfg.get("program_url") or "").strip()
    if not url and agenda:
        url = f"openagenda.com/{agenda}"
    b = {
        "accent": _hex(cfg.get("accent"), "#e2dff0"),
        "bg": _hex(cfg.get("card_bg"), "#efeae6"),
        "logo": _logo_html(cfg.get("logo_path")),
        "font_family": (cfg.get("font_family") or "").strip()
                       or DEFAULT_FONT,
        # affichage sans schéma ; l'URL complète reste dispo en _full
        "program_url": re.sub(r"^https?://", "", url).rstrip("/"),
        "program_url_full": url,
        "footer_text": cfg.get(
            "footer_text", "Tout le programme sur").strip(),
        "org": (cfg.get("org_name") or "").strip(),
    }
    b["dark"] = _darker(b["bg"])
    if cfg is not None:
        _BRAND = b
        _CFG = cfg
    return b


def _footer_html(b):
    """Pied de page : « <accroche> <pastille URL> » — texte libre, URL
    facultative, disparition propre si les deux sont vides."""
    bits = []
    if b["footer_text"]:
        bits.append(html.escape(b["footer_text"]))
    if b["program_url"]:
        bits.append(f"<b>{html.escape(b['program_url'])}</b>")
    return " ".join(bits)


def icon_svg(name):
    path = ICONS.get(name, ICONS["calendar"])
    vb = ICON_VIEWBOX.get(name, "0 0 24 24")
    attrs = ICON_PATH_ATTRS.get(name, "")
    return (
        f'<svg viewBox="{vb}" width="42" height="42" '
        f'aria-hidden="true"><path{attrs} d="{path}" '
        f'fill="currentColor"/></svg>'
    )


def _md_inline(text):
    """Markdown-lite → HTML inline pour le rendu : échappé d'abord,
    puis **gras** → <b>, *italique* → <em>, [lien](url) → libellé
    souligné, «## titre» → <b>. Tronquer AVANT (jamais au milieu
    d'une balise)."""
    t = html.escape(text)
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"__(.+?)__", r"<b>\1</b>", t)
    t = re.sub(r"(?<!\w)\*(.+?)\*(?!\w)", r"<em>\1</em>", t)
    t = re.sub(r"\[(.+?)\]\([^)]*\)", r"<u>\1</u>", t)
    t = re.sub(r"^#+\s*(.+?)$", r"<b>\1</b>", t, flags=re.M)
    return t.replace("\n", "<br>")


def truncate(text, limit=400):
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0]
    return cut.rstrip(".,;:!?") + "…"


def slide_html(ev, idx, fonts, orientation="landscape"):
    portrait = orientation.startswith("portrait")
    b = brand()
    tag = ev.get("tag") or ev["specs"].get("Catégorie") or "Événement"
    keys = [k for k in SPEC_ORDER if k in ev["specs"]]
    specs_html = "".join(
        f'<div class="spec">{icon_svg(SPEC_ICONS[k])}'
        f'<span>{html.escape(ev["specs"][k])}</span></div>'
        for k in keys
    )
    n_title = len(ev["title"])
    if portrait:
        if orientation == "portrait-screen":
            h1_size = 70 if n_title < 50 else 57 if n_title < 80 else 46
        else:
            h1_size = 76 if n_title < 50 else 62 if n_title < 80 else 50
    else:
        h1_size = 80 if n_title < 50 else 64 if n_title < 80 else 52
    specs_cls = "specs specs--tight" if len(keys) >= 4 else "specs"

    credit = html.escape(ev.get("credit", ""))
    if ev.get("img_data"):
        media = (
            f'<img class="photo" src="{ev["img_data"]}" alt="">'
            + (f'<div class="credit">{credit}</div>' if credit else "")
        )
    else:
        media = f"""<div class="photo photo--empty" style="background:{b['dark']}">
<svg viewBox="0 0 780 970" preserveAspectRatio="xMidYMid slice">
 <g fill="none" stroke="rgba(255,255,255,.42)" stroke-width="86">
  <circle cx="-60" cy="1030" r="340"/><circle cx="-60" cy="1030" r="560"/>
  <circle cx="-60" cy="1030" r="780"/>
 </g>
 <g fill="none" stroke="{b['dark']}" stroke-width="60" opacity=".55">
  <circle cx="850" cy="-40" r="260"/><circle cx="850" cy="-40" r="440"/>
 </g>
</svg>
<div class="ph-logo">{b['logo']}</div></div>"""

    family = fonts.get("family") or b["font_family"]
    footer = _footer_html(b)
    return _template(orientation).substitute(
        font_faces=fonts.get("faces", ""),
        font_family=f"{family}, {DEFAULT_FONT}"
                    if family != DEFAULT_FONT else DEFAULT_FONT,
        ink=INK,
        bg=b["bg"],
        dark=b["dark"],
        media=media,
        tag=html.escape(tag),
        h1_size=h1_size,
        title=html.escape(ev["title"]),
        # desc_md : markdown interprété (gras/italique) ; desc plat
        # en repli
        desc=_md_inline(truncate(ev.get("desc_md")
                                 or ev.get("desc", ""))),
        specs_cls=specs_cls,
        specs_html=specs_html,
        logo_html=b["logo"],
        footer_html=footer,
        style_overrides=_style_css(orientation),
    )


def slugify(text, maxlen=40):
    s = re.sub(r"[^a-z0-9]+", "-", text.lower())
    s = re.sub(r"['’]", "", s).strip("-")
    return s[:maxlen].strip("-") or "event"


def slide_name(ev, idx):
    """Nom stable dérivé de la date + titre : l'ordre alphabétique suit la
    chronologie et un événement garde son nom entre deux générations."""
    d = ev["specs"].get("Date", "")
    m = re.search(r"(\d{2})/(\d{2})/(\d{2})", d)
    t = re.search(r"(\d{1,2})h(\d{2})?", d)
    prefix = f"20{m.group(3)}-{m.group(2)}-{m.group(1)}" if m else f"zz{idx:02d}"
    if t:
        prefix += f"-{int(t.group(1)):02d}h{t.group(2) or '00'}"
    if ev.get("pinned"):
        # événement multi-jours en cours : nom de fichier trié en tête
        # ('slide-00-' précède 'slide-20…' alphabétiquement)
        prefix = "00-" + prefix
    return f"slide-{prefix}-{slugify(ev['title'])}"


def render_png_firefox(html_path, png_path, size=DEFAULT_SIZE,
                       orientation="landscape"):
    """Repli : firefox --screenshot avec zoom + fenêtre aux dimensions
    voulues (le HTML est dessiné pour les dimensions DESIGNS du
    gabarit — zoom adapté au ratio réel)."""
    w, h = size
    dw, _ = DESIGNS[orientation]
    html_path = Path(html_path).resolve()
    png_path = Path(png_path)
    zoomed = html_path.with_suffix(".zoom.html")
    zoomed.write_text(
        html_path.read_text("utf-8").replace(
            "</head>", f"<style>html{{zoom:{w / dw}}}</style></head>"
        ),
        encoding="utf-8",
    )
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp_out = Path(tmp.name)
    tmp_out.unlink()
    cmd = [
        "firefox", "--headless", f"--window-size={w},{h}",
        "--screenshot", str(tmp_out), zoomed.as_uri(),
    ]
    for _ in range(2):
        r = subprocess.run(cmd, capture_output=True, timeout=120)
        if tmp_out.exists() and tmp_out.stat().st_size > 0:
            break
    else:
        raise RuntimeError(f"firefox screenshot KO : {r.stderr.decode()[:400]}")
    img = Image.open(tmp_out).convert("RGB")
    img = img.resize(size) if img.size != size else img
    _save_atomic(img, png_path)
    tmp_out.unlink()
    zoomed.unlink()


def _save_atomic(img, path):
    """PNG écrit via fichier temporaire + rename : le diaporama ou la
    galerie ne peuvent pas lire un fichier à moitié écrit."""
    tmp = path.with_name(path.name + ".tmp")
    img.save(tmp, "PNG")
    os.replace(tmp, path)


def render_all(slides, size=DEFAULT_SIZE, orientation="landscape"):
    """Rend les diapos via Playwright/Chromium (viewport aux dimensions
    de conception + device_scale_factor → texte vectoriel ultra net).
    Repli Firefox si Playwright est absent."""
    w, h = size
    dw, dh = DESIGNS[orientation]
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        for hp, pp in slides:
            try:
                render_png_firefox(hp, pp, size, orientation)
                yield pp
            except Exception as e:
                print(f"  ✗ {pp.name} : {e}")
        return

    with sync_playwright() as p:
        # OASLIDES_BROWSER_CHANNEL permet d'utiliser un navigateur
        # système (ex. "msedge" pour l'app desktop — pas de téléchargement)
        channel = os.environ.get("OASLIDES_BROWSER_CHANNEL")
        # Sur poste géré, le launch peut échouer de façon transitoire
        # (AV qui scanne le profil temporaire, Edge en maj…) : on retente,
        # puis on bascule en fenêtré si le headless reste bloqué.
        browser = None
        # backoff long : une maj Edge ou un scan AV peut bloquer le
        # lancement pendant une minute — on étale les tentatives
        waits = [0, 5, 15, 30]
        attempts = [(channel, True)] * len(waits) + \
            ([(channel, False)] if channel else [])
        for i, (ch, headless) in enumerate(attempts):
            if i:
                time.sleep(waits[min(i, len(waits) - 1)])
            try:
                kw = {"headless": headless}
                if ch:
                    kw["channel"] = ch
                browser = p.chromium.launch(**kw)
                break
            except Exception as e:
                print(f"  ✗ lancement navigateur ({ch or 'chromium'}, "
                      f"headless={headless}) : {type(e).__name__}")
        if browser is None:
            raise RuntimeError("impossible de lancer le navigateur de rendu")
        page = browser.new_page(
            viewport={"width": dw, "height": dh},
            device_scale_factor=w / dw,
        )
        for hp, pp in slides:
            try:
                page.goto(Path(hp).resolve().as_uri())
                page.wait_for_function("document.fonts.status === 'loaded'")
                shot = page.screenshot()
                img = Image.open(io.BytesIO(shot)).convert("RGB")
                if img.size != size:
                    img = img.resize(size, Image.LANCZOS)
                _save_atomic(img, pp)
                yield pp
            except Exception as e:
                print(f"  ✗ {pp.name} : {e}")
        browser.close()

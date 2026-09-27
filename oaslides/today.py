"""Diapo du jour : slide fixe sans visuel pour la diffusion pendant un
événement (titre + intervenants + animateur). Générée à la demande
depuis l'UI dans today/index.html, puis poussée vers les destinations
configurées. Version générique : logo et accent viennent des
réglages / données de l'événement."""

import html
import re
from pathlib import Path
from string import Template

from .media import ensure_fonts
from .paths import ASSET_DIR
from .settings import OUT_DIR, resolve_out_dir
from .slide import DEFAULT_FONT, brand, _file_uri

_TEMPLATE = None

DARK = "#141414"
SERIES_DARK = "#16203f"


def _template():
    global _TEMPLATE
    if _TEMPLATE is None:
        _TEMPLATE = Template(
            (ASSET_DIR / "today_template.html").read_text(encoding="utf-8")
        )
    return _TEMPLATE


def today_html(data, fonts, b=None):
    """data : {title, tag, accent, bg, speakers[{name, quality}],
    moderator, note, access, series, series_logo}. `b` optionnel :
    identité déjà calculée (worker) — sinon cache des réglages.
    Renvoie le HTML autonome (fontes embarquées), version sombre :
    fond sombre, texte clair, accent en contraste. Si `series` est
    renseigné, la composition passe en mode « série » : badge rond,
    titre majuscule."""
    b = b or brand()
    # pile de fontes : réglage > fonts/ embarquées > système — le
    # dernier repli est indispensable : une famille saisie absente du
    # système rendrait en serif par défaut du navigateur
    family = b["font_family"] or fonts.get("family") or ""
    accent = data.get("accent") or b["accent"]
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", accent):
        accent = "#e2dff0"
    series = (data.get("series") or "").strip()
    bg = data.get("bg") or (SERIES_DARK if series else DARK)
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", bg):
        bg = SERIES_DARK if series else DARK
    speakers_html = "".join(
        f'<div class="speaker"><span class="name">{html.escape(s["name"])}</span>'
        + (f'<span class="qual">{html.escape(s["quality"])}</span>'
           if s.get("quality") else "")
        + "</div>"
        for s in data.get("speakers", [])
        if s.get("name")
    )
    moderator = (data.get("moderator") or "").strip()
    # accord avec le nom de la catégorie : rencontre/projection animée,
    # concert/spectacle animé
    fem = (data.get("tag") or "").lower() in (
        "rencontre", "projection", "conférence", "lecture", "visite")
    footer_bits = []
    if moderator:
        footer_bits.append(
            f'<div class="mod-line">{"Animée" if fem else "Animé"} par '
            f"<b>{html.escape(moderator)}</b></div>")
    # lignes libres (partenaires, séance de dédicace…) — aucun espace
    # occupé si le champ est vide
    for ln in (data.get("note") or "").splitlines():
        ln = ln.strip()
        if ln:
            footer_bits.append(
                f'<div class="note-line">{html.escape(ln)}</div>')
    # mentions d'accessibilité (LSF, audiodescription…) — idem : aucun
    # espace occupé si le champ est vide
    for ln in (data.get("access") or "").splitlines():
        ln = ln.strip()
        if ln:
            footer_bits.append(
                f'<div class="access-line">{html.escape(ln)}</div>')
    footer_html = (
        f'<div class="mod">{"".join(footer_bits)}</div>'
        if footer_bits else ""
    )
    series_logo_uri = None
    if series and data.get("series_logo"):
        series_logo_uri = _file_uri(data["series_logo"])
    if series_logo_uri:
        # identité propre de la série : le logo remplace le rond
        badge_html = (f'<div class="gt-badge gt-badge--img">'
                      f'<img src="{series_logo_uri}"></div>')
    elif series:
        badge_html = (
            f'<div class="gt-badge"><span class="gt-name">'
            f'{html.escape(series)}</span><span class="gt-logo">'
            f'{b["logo"]}</span></div>'
        )
    else:
        badge_html = (
            f'<span class="tag">'
            f'{html.escape(data.get("tag") or "Événement")}</span>'
        )
    title = data.get("title", "")
    # espace insécable avant la ponctuation double : évite un « ? »
    # orphelin en fin de ligne et respecte la typographie française
    title_esc = re.sub(r"\s+([?!:;»])", "&nbsp;\\1", html.escape(title))
    n = len(title)
    return _template().substitute(
        font_faces=fonts.get("faces", ""),
        font_family=f"{family}, {DEFAULT_FONT}"
                    if family else DEFAULT_FONT,
        accent=accent,
        bg=bg,
        light="#efeae6",
        badge_bg=accent if not series_logo_uri else "transparent",
        variant=" gt" if series else "",
        badge_html=badge_html,
        h1_size=80 if n < 42 else 64 if n < 80 else 52,
        title=title_esc,
        speakers_label="Avec" if speakers_html else "",
        speakers_html=speakers_html,
        footer_html=footer_html,
        logo_html=b["logo"],
    )


def write_today(data, out_dir=None, b=None):
    """Écrit today/index.html et renvoie son chemin. `b` optionnel :
    identité pré-calculée (évite le cache global en worker). Nettoie
    au passage les restes d'anciennes générations (qr.*)."""
    out = Path(out_dir) if out_dir else OUT_DIR
    d = out / "today"
    d.mkdir(parents=True, exist_ok=True)
    dest = d / "index.html"
    dest.write_text(today_html(data, ensure_fonts(), b=b),
                    encoding="utf-8")
    for f in ("qr.html", "qr.png"):
        (d / f).unlink(missing_ok=True)
    return dest


def render_today_png(size, out_dir=None):
    """Rend today/index.html en today/index.png à la résolution `size`
    (même réglage que les autres diapos). Renvoie le chemin du PNG."""
    from .slide import render_all

    out = Path(out_dir) if out_dir else OUT_DIR
    src = out / "today" / "index.html"
    png = out / "today" / "index.png"
    list(render_all([(src, png)], size=size))
    if not png.exists():
        raise RuntimeError("rendu de la diapo du jour impossible")
    return png


def push_today(cfg, out_dir=None):
    """Pousse les fichiers de today/ (index.html, index.png) vers le
    sous-dossier today/ des destinations configurées (SMB/FTP).
    Renvoie une liste d'erreurs (vide = tout OK)."""
    out = Path(out_dir) if out_dir else OUT_DIR
    d = out / "today"
    files = [p for p in sorted(d.glob("*")) if p.is_file()] \
        if d.exists() else []
    if not files:
        return ["today/ absent"]
    errors = []

    smb_host = (cfg.get("smb_host") or "").strip()
    smb_share = (cfg.get("smb_share") or "").strip()
    if smb_host and smb_share:
        try:
            from smbclient import makedirs, open_file, register_session
            register_session(
                smb_host,
                username=cfg.get("smb_user") or "",
                password=cfg.get("smb_pass") or "",
            )
            base = f"\\\\{smb_host}\\{smb_share}"
            if cfg.get("smb_path"):
                base += "\\" + str(cfg["smb_path"]).strip("/\\")
            d = base + "\\today"
            makedirs(d, exist_ok=True)
            for f in files:
                with open(f, "rb") as fh, \
                        open_file(d + "\\" + f.name, "wb") as dst:
                    dst.write(fh.read())
        except Exception as e:
            errors.append(f"SMB : {e}")

    if (cfg.get("ftp_host") or "").strip():
        try:
            import ftplib
            cls = ftplib.FTP_TLS if cfg.get("ftp_tls") else ftplib.FTP
            ftp = cls()
            ftp.connect(cfg["ftp_host"].strip(),
                        int(cfg.get("ftp_port") or 21), timeout=30)
            try:
                ftp.login(cfg.get("ftp_user") or "", cfg.get("ftp_pass") or "")
                if cfg.get("ftp_tls"):
                    ftp.prot_p()
                for part in [p for p in
                             (cfg.get("ftp_path") or "/").split("/") if p]:
                    try:
                        ftp.mkd(part)
                    except ftplib.error_perm:
                        pass
                    ftp.cwd(part)
                try:
                    ftp.mkd("today")
                except ftplib.error_perm:
                    pass
                ftp.cwd("today")
                for f in files:
                    with open(f, "rb") as fh:
                        ftp.storbinary("STOR " + f.name, fh)
            finally:
                try:
                    ftp.quit()
                except Exception:
                    ftp.close()
        except Exception as e:
            errors.append(f"FTP : {e}")

    return errors

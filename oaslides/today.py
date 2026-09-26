"""Diapo du jour : slide fixe sans visuel pour la diffusion pendant un
événement (titre + intervenants + animateur). Générée à la demande
depuis l'UI dans today/index.html, puis poussée vers les destinations
configurées. Version générique : logo, accent et QR (permalink
OpenAgenda) viennent des réglages / données de l'événement."""

import base64
import html
import io
import re
from pathlib import Path
from string import Template

from .media import ensure_fonts
from .paths import ASSET_DIR
from .settings import OUT_DIR, resolve_out_dir
from .slide import brand, _file_uri

_TEMPLATE = None
_TEMPLATE_QR = None

DARK = "#141414"
SERIES_DARK = "#16203f"


def _template():
    global _TEMPLATE
    if _TEMPLATE is None:
        _TEMPLATE = Template(
            (ASSET_DIR / "today_template.html").read_text(encoding="utf-8")
        )
    return _TEMPLATE


def _template_qr():
    global _TEMPLATE_QR
    if _TEMPLATE_QR is None:
        _TEMPLATE_QR = Template(
            (ASSET_DIR / "today_qr_template.html").read_text("utf-8")
        )
    return _TEMPLATE_QR


def today_html(data, fonts):
    """data : {title, tag, accent, bg, speakers[{name, quality}],
    moderator, note, access, series, series_logo}.
    Renvoie le HTML autonome (fontes embarquées), version sombre :
    fond sombre, texte clair, accent en contraste. Si `series` est
    renseigné, la composition passe en mode « série » : badge rond,
    titre majuscule."""
    b = brand()
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
        font_family=fonts.get("family") or b["font_family"],
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


def _qr_url(data, cfg):
    """Cible du QR : permalink OpenAgenda de l'événement, sinon l'URL du
    programme configurée, sinon la page publique de l'agenda."""
    if data.get("event_url"):
        return data["event_url"]
    if (cfg.get("program_url") or "").strip():
        u = cfg["program_url"].strip()
        return u if "://" in u else "https://" + u
    agenda = (cfg.get("oa_agenda") or "").strip()
    return f"https://openagenda.com/{agenda}" if agenda else ""


def qr_html(data, bg, fonts, cfg):
    """Slide QR : « Retrouvez cet événement… en scannant le QR code » —
    même fond sombre que la diapo du jour. Cible : permalink de
    l'événement ou page de l'agenda."""
    url = _qr_url(data, cfg)
    if not url:
        return ""
    import qrcode
    qr = qrcode.QRCode(border=0, box_size=18)
    qr.add_data(url)
    qr.make()
    img = qr.make_image(fill_color=SERIES_DARK, back_color="#ffffff")
    buf = io.BytesIO()
    img.convert("RGB").save(buf, "PNG")
    b = brand()
    target = html.escape(re.sub(r"^https?://", "", url))
    return _template_qr().substitute(
        font_faces=fonts.get("faces", ""),
        font_family=fonts.get("family") or b["font_family"],
        bg=bg,
        sentence=html.escape(
            "Retrouvez cet événement et tout le programme "
            "en scannant le QR code"),
        target=target,
        qr_data="data:image/png;base64," + base64.b64encode(
            buf.getvalue()).decode(),
        logo_html=b["logo"],
    )


def write_today(data, out_dir=None):
    """Écrit today/index.html (+ today/qr.html si une cible de QR est
    disponible) et renvoie le chemin de l'index."""
    out = Path(out_dir) if out_dir else OUT_DIR
    d = out / "today"
    d.mkdir(parents=True, exist_ok=True)
    dest = d / "index.html"
    series = (data.get("series") or "").strip()
    bg = data.get("bg") or (SERIES_DARK if series else DARK)
    fonts = ensure_fonts()
    dest.write_text(today_html(data, fonts), encoding="utf-8")
    from .settings import load_settings
    cfg = load_settings() or {}
    qr = qr_html(data, bg, fonts, cfg)
    if qr:
        (d / "qr.html").write_text(qr, encoding="utf-8")
    else:
        # pas de cible QR : on supprime les restes d'une éventuelle
        # génération précédente
        for f in ("qr.html", "qr.png"):
            p = d / f
            if p.exists():
                p.unlink()
    return dest


def render_today_png(size, out_dir=None):
    """Rend today/index.html en today/index.png (+ qr.html → qr.png si
    présent) à la résolution `size` (même réglage que les autres
    diapos). Renvoie le chemin du PNG principal."""
    from .slide import render_all

    out = Path(out_dir) if out_dir else OUT_DIR
    src = out / "today" / "index.html"
    png = out / "today" / "index.png"
    jobs = [(src, png)]
    qr_src = out / "today" / "qr.html"
    if qr_src.exists():
        jobs.append((qr_src, out / "today" / "qr.png"))
    list(render_all(jobs, size=size))
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

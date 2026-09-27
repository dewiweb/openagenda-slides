"""Orchestration : OpenAgenda → images → HTML → PNG → manifeste →
synchros. Source unique : l'agenda OpenAgenda configuré."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image

from .media import download_image, ensure_fonts
from .paths import OUT_DIR
from .oa import oa_list_events, filter_categories
from .extract import parse_series_map, parse_cats
from .slide import (
    render_all, slide_html, slide_name, SIZES, DEFAULT_SIZE,
    portrait_key, portrait_size,
)
from .sync import sync_ftp, sync_local, sync_smb


def _render_set(events, fonts, dest, size, orientation="landscape"):
    """Génère un jeu de diapos (HTML + PNG) dans `dest` et y supprime
    les fichiers obsolètes. Retourne la liste des PNG du jeu."""
    dest.mkdir(parents=True, exist_ok=True)
    html_dir = dest / "html"
    html_dir.mkdir(exist_ok=True)

    # ne re-rendre que les diapos nouvelles ou modifiées ; supprimer
    # celles qui n'existent plus (sobriété : pas de wipe systématique)
    to_render, expected_png, expected_html = [], set(), set()
    used = set()
    for i, ev in enumerate(events, start=1):
        name = slide_name(ev, i)
        while name in used:  # collision date+titre : suffixe
            name += f"-{i}"
        used.add(name)
        expected_png.add(f"{name}.png")
        expected_html.add(f"{name}.html")
        hp, pp = html_dir / f"{name}.html", dest / f"{name}.png"
        content = slide_html(ev, i - 1, fonts, orientation)
        # PNG corrompu/interrompu → on re-rend plutôt que tout échouer
        try:
            same_size = pp.exists() and Image.open(pp).size == size
        except Exception:
            same_size = False
        if (
            same_size
            and hp.exists()
            and hp.read_text("utf-8") == content
        ):
            continue
        hp.write_text(content, encoding="utf-8")
        to_render.append((hp, pp))

    for p in dest.glob("*.png"):
        if p.name not in expected_png:
            p.unlink()
            print(f"  - {p.name} supprimée")
    for p in html_dir.glob("*.html"):
        if p.name not in expected_html:
            p.unlink()

    print(f"  rendu {orientation} — {len(to_render)} à rendre "
          f"({len(expected_png) - len(to_render)} inchangées)…")
    for pp in render_all(to_render, size, orientation):
        print(f"  ✓ {pp.name}")

    pngs = sorted(dest.glob("*.png"))

    # manifeste du jeu attendu — uploadé en dernier par les synchros
    (dest / "manifest.txt").write_text(
        "\n".join(p.name for p in pngs) + "\n", encoding="utf-8"
    )
    return pngs


def _limit_events(events, cfg, max_events):
    """Filtre de fin de liste : par nombre (historique), par horizon
    « dans les N jours » ou « jusqu'au <date> ». Un événement est gardé
    si sa fenêtre [début, fin] intersecte [aujourd'hui, horizon] —
    les multi-jours en cours (épinglés) restent donc visibles."""
    import datetime
    cfg = cfg or {}
    mode = cfg.get("limit_mode", "count")
    if mode == "count":
        return events[:max_events] if max_events else events
    today = datetime.date.today()
    if mode == "days":
        horizon = today + datetime.timedelta(
            days=int(cfg.get("limit_days") or 0))
    elif mode == "date":
        try:
            horizon = datetime.date.fromisoformat(
                str(cfg.get("limit_date") or ""))
        except ValueError:
            return events
    else:
        return events
    out = []
    for ev in events:
        s = ev.get("_dt")
        if not s:
            out.append(ev)  # sans date (expo permanente) : toujours
            continue
        e = ev.get("_dt_end") or s
        sd, ed = datetime.date(*s[:3]), datetime.date(*e[:3])
        if sd <= horizon and ed >= today:
            out.append(ev)
    return out


def generate(out_dir=None, max_events=0, pages=99, cfg=None,
             size=DEFAULT_SIZE):
    """Génère le diaporama complet. Retourne la liste des PNG produits.
    cfg peut contenir les réglages ftp_*/smb_*/local_* pour pousser le
    dossier après génération."""
    out = Path(out_dir) if out_dir else OUT_DIR

    print("1/5 Récupération des événements OpenAgenda…")
    series_map = parse_series_map(
        (cfg or {}).get("series_map", "")) or None
    events = oa_list_events(cfg, series_map=series_map)
    cats = parse_cats((cfg or {}).get("gen_categories", ""))
    if cats:
        events = filter_categories(events, cats)
    events = _limit_events(events, cfg, max_events)
    print(f"  {len(events)} événements trouvés")
    if not events:
        raise RuntimeError(
            "Aucun événement trouvé — vérifiez le slug de l'agenda "
            "et les filtres de catégories."
        )

    print("2/5 Images…")
    # OA donne déjà desc/speakers/image — on télécharge juste l'image
    with ThreadPoolExecutor(max_workers=6) as ex:
        events = list(ex.map(download_image, events))

    # métadonnées pour la « diapo du jour » et la galerie
    import json
    out.mkdir(parents=True, exist_ok=True)
    (out / "events.json").write_text(
        json.dumps(
            [
                {
                    "title": e["title"], "url": e["url"],
                    "slide": slide_name(e, i),
                    "image": e.get("image") or e.get("card_img"),
                    "tag": e.get("tag"),
                    "specs": e["specs"],
                    "desc": e.get("desc", ""),
                    "desc_long": e.get("desc_long", ""),
                    "desc_md": e.get("desc_md", ""),
                    "credit": e.get("credit", ""),
                    "speakers": e.get("speakers", []),
                    "moderator": e.get("moderator", ""),
                    "note": e.get("note", ""),
                    "audience": e.get("audience", ""),
                    "access": e.get("access", ""),
                    "access_venue": e.get("access_venue", []),
                    "series": e.get("series", ""),
                    "online": e.get("online", False),
                }
                for i, e in enumerate(events, start=1)
            ],
            ensure_ascii=False, indent=1,
        ),
        encoding="utf-8",
    )

    print("3/5 Fontes…")
    fonts = ensure_fonts()
    # cache identité réinitialisé avec les réglages de CE run — sinon
    # _BRAND survivrait d'un run à l'autre et les retouches de
    # couleurs/logo/fonte resteraient sans effet jusqu'au redémarrage
    from .slide import brand
    brand(cfg or {})

    print(f"4/5 Génération du dossier {out}/…")
    gen_landscape = cfg is None or cfg.get("gen_landscape", 1)
    gen_portrait = cfg and cfg.get("gen_portrait")
    # migration : les diapos paysage vivaient à la racine avant
    # landscape/ — on retire les restes de l'ancienne arborescence
    # (fichiers générés uniquement : slide-*, html/, manifest.txt)
    if gen_landscape:
        for p in out.glob("slide-*.png"):
            p.unlink(missing_ok=True)
        hdir = out / "html"
        if hdir.is_dir():
            for p in hdir.glob("*.html"):
                p.unlink(missing_ok=True)
            try:
                hdir.rmdir()
            except OSError:
                pass
        (out / "manifest.txt").unlink(missing_ok=True)
    pngs = []
    if gen_landscape:
        pngs = _render_set(events, fonts, out / "landscape", size)
    if gen_portrait:
        # portrait A4 (impression, 150-300 dpi) ou écran 9:16 (écran
        # pivoté) selon portrait_format — sous-dossier portrait/
        fmt = (cfg or {}).get("portrait_format") or "a4"
        _render_set(events, fonts, out / "portrait",
                    portrait_size(size, fmt), portrait_key(fmt))

    # synchros : une destination en échec ne doit pas faire rater la
    # génération — les diapos locales sont bonnes, l'erreur part en
    # warning dans le journal (visible dans le statut de l'app)
    failed = []
    if cfg:
        if cfg.get("ftp_host"):
            print("6/6 Envoi FTP…")
            try:
                sync_ftp(out, cfg)
            except Exception as e:
                print(f"  ⚠ synchro FTP KO : {e}")
                failed.append("FTP")
        if cfg.get("smb_host"):
            print("    Envoi SMB…")
            try:
                sync_smb(out, cfg)
            except Exception as e:
                print(f"  ⚠ synchro SMB KO : {e}")
                failed.append("SMB")
        if cfg.get("local_dir"):
            print("    Copie dossier local…")
            try:
                sync_local(out, cfg)
            except Exception as e:
                print(f"  ⚠ copie locale KO : {e}")
                failed.append("dossier local")
    if failed:
        print(f"⚠ synchro(s) en échec : {', '.join(failed)} "
              "— les diapos locales sont à jour")

    n = len(pngs) + len(list((out / "portrait").glob("*.png")))
    print(f"\nTerminé : {n} diapos dans {out}/")
    return pngs

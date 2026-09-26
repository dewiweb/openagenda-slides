"""Source OpenAgenda, générique : n'importe quel agenda public.

Chaîne de repli :
  1. API v2 officielle (si `oa_api_key` renseignée) — timings filtrés
     côté serveur, schéma de l'agenda pour les libellés
  2. export legacy events.json (sans clé, endpoint déprécié mais
     public et complet — timings, tagGroups, lieu, images)

Produit le format d'événement commun : title, url, tag, specs{Date,
Séances, Durée, Lieu, Tarif, Public, Accessibilité}, desc, desc_long,
desc_md, speakers, moderator, note, access, access_venue, series,
image, credit, _dt, _dt_end, pinned.

Taxonomie : les catégories/publics viennent des `tagGroups` de
l'événement (libellés propres à chaque agenda) — le réglage
`tag_group` choisit quel groupe sert de catégorie (vide = premier
groupe « categorie* » trouvé, sinon le premier groupe).
"""

import datetime
import re
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

from .extract import (
    _extract_access, _extract_note, _extract_people, _clean_md, _norm_ws,
    ACCESS_KEYWORDS, VENUE_ACCESS,
)

API = "https://api.openagenda.com/v2"
UA = {"User-Agent": "oaslides/1.0"}


# ———————————————————— formatage ————————————————————

def _tz(location):
    """Fuseau du lieu de l'événement (champ `timezone` du lieu OA) ;
    None → on garde l'heure wall-clock publiée (offset propre à chaque
    timing)."""
    tz = ((location or {}).get("timezone") or "").strip()
    try:
        return ZoneInfo(tz) if tz else None
    except Exception:
        return None


def _local(dt, tz=None):
    """ISO → tuple (a, m, j, h, min) dans le fuseau du lieu si connu,
    sinon dans l'offset publié par l'agenda."""
    d = datetime.datetime.fromisoformat(dt.replace("Z", "+00:00"))
    if tz:
        d = d.astimezone(tz)
    return (d.year, d.month, d.day, d.hour, d.minute)


def _fmt_day(t):
    return f"{t[2]:02d}/{t[1]:02d}/{str(t[0])[2:]}"


def _fmt_time(t):
    return f"{t[3]}h{t[4]:02d}".replace("h00", "h")


def _duration(begin, end):
    """minutes entre deux timings → libellé '1h30' / '45 min' / '1h'."""
    mins = (datetime.datetime(*end) - datetime.datetime(*begin)
            ).total_seconds() // 60
    if mins <= 0 or mins >= 4 * 60:
        # ≥ 4 h = amplitude d'ouverture du lieu, pas durée de séance
        return ""
    h, m = divmod(int(mins), 60)
    return f"{h}h{m:02d}" if m else (f"{h}h" if h else f"{mins} min")


def _date_spec(timings):
    """Construit la spec Date + compteur de séances + durée + bornes.
    timings : liste de tuples locaux (begin, end) triés par début.
    Retourne (date_spec, nb_séances, durée, _dt, _dt_end, pinned)."""
    today = datetime.date.today()
    future = [t for t in timings if t[1][:3] >=
              (today.year, today.month, today.day)]
    if not future:
        future = timings
    first_b, _ = timings[0]
    last_e = timings[-1][1]
    span = (datetime.date(*last_e[:3]) - datetime.date(*first_b[:3])).days

    days = {t[0][:3] for t in timings}
    durs = sorted((datetime.datetime(*e) - datetime.datetime(*b))
                  .total_seconds() // 60 for b, e in timings)
    med = durs[len(durs) // 2]
    # un timing = bloc d'ouverture de journée (≥ 4 h) → vraie expo
    # permanente ; des séances courtes très nombreuses (animations
    # quotidiennes : 1600 × 30 min sur 2 ans) sont programmées —
    # « Prochaine séance » leur convient mieux
    open_blocks = med >= 4 * 60
    if span > 300 and open_blocks and len(days) >= span * .5:
        # collection/expo sur des années, ouverte quasiment tous les
        # jours → « Exposition permanente » ; le compteur et la durée
        # seraient absurdes. Un rendez-vous récurrent sur l'année
        # (~14 % des jours) n'en est pas une — branche récurrente.
        return "Exposition permanente", 0, "", None, None, False
    contiguous = (len(days) > 1 and span > 0 and len(days) >= span * .8
                  and (open_blocks or span <= 120))
    if contiguous:
        # événement multi-jours (temps fort, expo temporaire)
        date_spec = f"Du {_fmt_day(first_b)} au {_fmt_day(last_e)}"
        t3 = (today.year, today.month, today.day)
        pinned = first_b[:3] <= t3 <= last_e[:3]
        return date_spec, 0, "", first_b, last_e, pinned
    # séance(s) ponctuelle(s) : la prochaine porte la date — préfixée
    # « Prochaine séance : » quand l'événement est récurrent
    nx = next(iter(future))
    date_spec = f"{_fmt_day(nx[0])} à {_fmt_time(nx[0])}"
    if len(future) > 1:
        date_spec = f"Prochaine séance : {date_spec}"
    return (date_spec, len(future),
            _duration(nx[0], nx[1]), nx[0], nx[0], False)


def _timings_pairs(raw, tz=None):
    """Normalise timings v2 (begin/end) et legacy (start/end)."""
    out = []
    for t in raw or []:
        b = t.get("begin") or t.get("start")
        e = t.get("end")
        if b and e:
            out.append((_local(b, tz), _local(e, tz)))
    out.sort(key=lambda x: x[0])
    return out


# ———————————————————— taxonomie (tagGroups) ————————————————————

def _pick_tag_groups(e, cat_group=""):
    """Extrait (cat_value, cat_label, publics, tag_slugs) des tagGroups
    legacy. `cat_group` choisit le groupe catégorie (vide = auto :
    groupe « categorie* », sinon le premier)."""
    groups = e.get("tagGroups") or []
    cat_value = cat_label = None
    pubs = []
    tag_slugs = []
    for g in groups:
        for t in g.get("tags") or []:
            if t.get("slug"):
                tag_slugs.append(t["slug"])
    # groupe catégorie : réglage explicite, sinon « categorie* », sinon
    # le premier groupe non « publics* »
    cg = None
    if cat_group:
        cg = next((g for g in groups if g.get("slug") == cat_group), None)
    if cg is None:
        cg = next((g for g in groups
                   if (g.get("slug") or "").startswith("categorie")), None)
    if cg is None:
        cg = next((g for g in groups
                   if "public" not in (g.get("slug") or "").lower()), None)
    if cg and cg.get("tags"):
        t = cg["tags"][0]
        cat_value, cat_label = t.get("slug"), t.get("label")
    for g in groups:
        if "public" in (g.get("slug") or "").lower():
            pubs += [t.get("label") for t in g.get("tags") or []]
    return cat_value, cat_label, [p for p in pubs if p], tag_slugs


# ———————————————————— mapping événement ————————————————————

def _base_map(e, cat_value, cat_label, public_label, kws, cond, timings,
              title, url, desc, desc_long, html_txt, image, credit, lieu,
              access_codes, age=None, series_map=None, tag_slugs=None,
              tz=None):
    """Construit le dict événement commun (v2 et legacy convergent ici).
    `e` ne sert que de référence pour l'uid/canonicalUrl éventuels."""
    pairs = _timings_pairs(timings, tz)
    if pairs:
        date_spec, n_sessions, dur, dt, dt_end, pinned = (
            _date_spec(pairs))
    else:
        # aucun créneau : événement à durée indéterminée
        date_spec, n_sessions, dur = "En continu", 0, ""
        dt = dt_end = None
        pinned = False

    specs = {"Date": date_spec}
    if dur:
        specs["Durée"] = dur
    if lieu:
        specs["Lieu"] = lieu
    if cond:
        specs["Tarif"] = cond[:1].upper() + cond[1:]
    if public_label:
        pub = public_label
        if age and age.get("min"):
            pub += f" · dès {age['min']} ans"
        specs["Public"] = pub
    elif age and age.get("min"):
        specs["Public"] = f"Dès {age['min']} ans"

    tag = cat_label or "Événement"
    desc_md = _norm_ws(desc) or _norm_ws(desc_long)
    desc, desc_long = _clean_md(desc), _clean_md(desc_long)

    # intervenants / animateur / notes : heuristiques best-effort
    intro = BeautifulSoup(html_txt or "", "lxml") if html_txt else None
    speakers, moderator = _extract_people(intro, title, desc_long)
    note = _extract_note(desc_long)

    # accessibilité : mots-clés structurés OA ∪ mentions dans le texte
    access_labels = [lbl for k, lbl in ACCESS_KEYWORDS.items()
                     if k in kws]
    for lbl in (_extract_access(desc_long) or "").split("\n"):
        if lbl and lbl not in access_labels:
            access_labels.append(lbl)
    access = "\n".join(access_labels)
    if access:
        specs["Accessibilité"] = access.replace("\n", " · ")

    series = next((lbl for k, lbl in (series_map or {}).items()
                   if k in kws), "")

    return {
        "title": title, "url": url, "tag": tag, "color": None,
        "specs": specs, "desc": desc, "desc_long": desc_long,
        # markdown conservé : le rendu l'interprète (gras/italique),
        # les champs plats restent pour l'extraction et l'UI
        "desc_md": desc_md,
        "speakers": speakers, "moderator": moderator, "note": note,
        "audience": public_label or "", "access": access,
        "access_venue": [VENUE_ACCESS[c] for c in access_codes
                         if c in VENUE_ACCESS],
        "series": series, "image": image, "card_img": image,
        "credit": credit, "_dt": dt, "_dt_end": dt_end,
        "pinned": pinned, "_source": "oa", "_oa_cat": cat_value,
        # slugs de tous les tags (filtre utilisateur) + keywords bruts
        # conservés : base d'un éventuel filtre thématique ou de la
        # détection de séries — pas affichés sur la diapo
        "tag_slugs": tag_slugs or [],
        "keywords": kws,
    }


def _map_v2(e, cat_opts, pub_opts, agenda, series_map=None,
            cat_group=""):
    cat_id = e.get("categorie")
    cat_value, cat_label = (cat_opts.get(cat_id) or (None, None))
    pub_ids = e.get("publics") or []
    if isinstance(pub_ids, int):
        pub_ids = [pub_ids]
    pubs = [pub_opts.get(i) for i in pub_ids if i in pub_opts]
    kws = [k for k in ((e.get("keywords") or {}).get("fr") or []) if k]
    cond = (e.get("conditions") or {}).get("fr")
    acc = e.get("accessibility") or {}
    acc_codes = [k for k, v in acc.items() if v] \
        if isinstance(acc, dict) else list(acc)
    img = e.get("image") or {}
    image = (img.get("base", "") + img["filename"]) \
        if img.get("filename") else None
    for v in img.get("variants") or []:
        if v.get("type") == "full":
            image = img.get("base", "") + v["filename"]
    uid = e.get("uid")
    url = (e.get("canonicalUrl")
           or (f"https://openagenda.com/{agenda}/events/"
               f"{uid}_{e.get('slug', '')}" if uid else ""))
    # v2 ne porte pas toujours tagGroups ; la catégorie vient du schéma
    tag_slugs = [t.get("slug") for g in e.get("tagGroups") or []
                 for t in g.get("tags") or [] if t.get("slug")]
    ev = _base_map(
        e, cat_value, cat_label, " · ".join(p for p in pubs if p), kws,
        cond, e.get("timings"), (e.get("title") or {}).get("fr", ""), url,
        (e.get("description") or {}).get("fr", ""),
        (e.get("longDescription") or {}).get("fr", "")
        or (e.get("description") or {}).get("fr", ""),
        (e.get("html") or {}).get("fr", ""),
        image, e.get("imageCredits") or "",
        (e.get("location") or {}).get("name", ""),
        acc_codes, e.get("age"), series_map, tag_slugs,
        tz=_tz(e.get("location")))
    ev["online"] = e.get("attendanceMode") == 2
    if not e.get("timings"):
        # timings indisponibles même sur le détail : le texte
        # « dateRange » éditorial vaut mieux que rien
        dr = (e.get("dateRange") or {}).get("fr", "")
        dr = re.sub(r"\s*undefined\s*", " ", dr).strip(" ,")
        if dr:
            ev["specs"]["Date"] = dr
            ev["specs"].pop("Séances", None)
    return ev


def _map_legacy(e, series_map=None, cat_group=""):
    cat_value, cat_label, pubs, tag_slugs = _pick_tag_groups(e, cat_group)
    kws = [k for k in ((e.get("keywords") or {}).get("fr") or []) if k]
    cond = (e.get("conditions") or {}).get("fr")
    loc = e.get("location") or {}
    lieu = loc.get("name") or e.get("locationName") or ""
    ev = _base_map(
        e, cat_value, cat_label, " · ".join(pubs), kws,
        cond, e.get("timings"), (e.get("title") or {}).get("fr", ""),
        e.get("canonicalUrl") or "",
        (e.get("description") or {}).get("fr", ""),
        (e.get("longDescription") or {}).get("fr", "")
        or (e.get("description") or {}).get("fr", ""),
        (e.get("html") or {}).get("fr", ""),
        e.get("originalImage") or e.get("image"),
        e.get("imageCredits") or "", lieu,
        e.get("accessibility") or [], e.get("age"), series_map,
        tag_slugs, tz=_tz(loc))
    ev["online"] = e.get("attendanceMode") == 2
    if not e.get("timings"):
        # le texte éditorial « range » vaut mieux que « En continu »
        dr = (e.get("range") or {}).get("fr", "")
        dr = re.sub(r"\s*undefined\s*", " ", dr).strip(" ,")
        if dr:
            ev["specs"]["Date"] = dr
    return ev


# ———————————————————— fetch ————————————————————

def _get(url, **kw):
    from .net import get
    return get(url, headers=UA, **kw)


def _resolve_uid(agenda):
    """Le legacy export veut l'uid numérique ; le réglage accepte le
    slug lisible — on l'extrait de la page publique de l'agenda."""
    if str(agenda).isdigit():
        return int(agenda)
    html_txt = _get(f"https://openagenda.com/fr/{agenda}").text
    m = re.search(r"agendas/(\d+)", html_txt)
    if not m:
        raise RuntimeError(f"uid de l'agenda « {agenda} » introuvable")
    return int(m.group(1))


def _v2_events(agenda, key, series_map=None, cat_group=""):
    """API v2 officielle : schéma (libellés catégorie/public) puis
    événements à venir paginés."""
    a = _get(f"{API}/agendas/{agenda}",
             params={"key": key}).json()
    cat_opts, pub_opts = {}, {}
    for f in a.get("schema", {}).get("fields", []):
        opts = {o["id"]: (o.get("value"),
                         (o.get("label") or {}).get("fr"))
                for o in f.get("options") or []}
        if f["field"] == "categorie":
            cat_opts = opts                     # id → (value, label)
        elif f["field"] == "publics":
            pub_opts = {i: lbl for i, (_, lbl) in opts.items()}

    today = datetime.date.today().isoformat()
    events, offset = [], 0
    while True:
        d = _get(f"{API}/agendas/{agenda}/events",
                 params={"key": key, "size": 100, "offset": offset,
                         "detailed": 1,
                         "timings[gte]": today}).json()
        events += d.get("events", [])
        total = d.get("total", 0)
        offset += len(d.get("events", [])) or 100
        if not d.get("events") or offset >= total:
            break
    # la liste omet `timings` quand il y en a trop (récurrents :
    # ~40/an) — sans eux l'événement serait classé « En continu » ;
    # on va les chercher sur le détail
    for e in events:
        if not e.get("timings") and e.get("firstTiming"):
            try:
                d = _get(f"{API}/agendas/{agenda}/events/{e['uid']}",
                         params={"key": key}).json()
                full = d.get("event", d)
                if full.get("timings"):
                    e["timings"] = full["timings"]
            except Exception:
                pass  # le texte dateRange servira de spécification
    return [_map_v2(e, cat_opts, pub_opts, agenda, series_map, cat_group)
            for e in events]


def _legacy_events(agenda, series_map=None, cat_group=""):
    """Export public legacy (sans clé, déprécié) : tout l'historique,
    filtré côté client aux événements pas terminés."""
    uid = _resolve_uid(agenda)
    today = datetime.date.today()
    events, offset = [], 0
    while True:
        d = _get(f"https://openagenda.com/agendas/{uid}/events.json",
                 params={"limit": 100, "offset": offset}).json()
        batch = d.get("events", [])
        if not batch:
            break
        events += batch
        offset += len(batch)
        if offset >= d.get("total", 0):
            break
    out = []
    for e in events:
        pairs = _timings_pairs(e.get("timings"),
                               _tz(e.get("location") or {}))
        if pairs:
            last = datetime.date(*pairs[-1][1][:3])
        else:
            # pas de créneaux : repli sur lastDate (certains agendas
            # publient des événements sans timings détaillés)
            ld = (e.get("lastDate") or e.get("firstDate") or "")[:10]
            try:
                last = datetime.date.fromisoformat(ld)
            except ValueError:
                continue  # rien pour dater → on écarte
        if last < today:
            continue  # terminé — l'export n'a pas de filtre serveur
        out.append(_map_legacy(e, series_map, cat_group))
    return out


def oa_list_events(cfg):
    """Événements OpenAgenda selon les réglages : `oa_api_key` présent
    → API v2 ; sinon export legacy public."""
    agenda = (cfg.get("oa_agenda") or "").strip()
    if not agenda:
        raise RuntimeError("Aucun agenda configuré (réglage "
                           "« Agenda OpenAgenda » vide)")
    key = (cfg.get("oa_api_key") or "").strip()
    from .extract import parse_series_map
    series_map = parse_series_map(cfg.get("series_map", "")) or None
    cat_group = (cfg.get("tag_group") or "").strip()
    if key:
        print("  source : OpenAgenda API v2")
        return _v2_events(agenda, key, series_map, cat_group)
    print("  source : export OpenAgenda (sans clé — endpoint déprécié)")
    return _legacy_events(agenda, series_map, cat_group)


def list_tag_groups(agenda, limit=100):
    """Groupes de tags de l'agenda (export legacy, sans clé) →
    {slug_groupe: {nom, tags: [(slug, libellé)]}} — pour configurer
    `tag_group` et `tag_filter` dans l'UI."""
    uid = _resolve_uid(agenda)
    groups = {}
    d = _get(f"https://openagenda.com/agendas/{uid}/events.json",
             params={"limit": limit}).json()
    for e in d.get("events", []):
        for g in e.get("tagGroups") or []:
            gs = g.get("slug") or ""
            if not gs:
                continue
            grp = groups.setdefault(
                gs, {"name": g.get("name") or gs, "tags": {}})
            for t in g.get("tags") or []:
                if t.get("slug"):
                    grp["tags"][t["slug"]] = t.get("label") or t["slug"]
    return {k: {"name": v["name"],
                "tags": sorted(v["tags"].items())}
            for k, v in groups.items()}


def detect_series(agenda):
    """Propose des lignes « keyword = Libellé » pour le réglage
    series_map, en scannant les keywords de l'export legacy (public,
    sans clé). Les keywords techniques (accessibilité…) sont écartés."""
    kws = {}
    try:
        uid = _resolve_uid(agenda)
        d = _get(f"https://openagenda.com/agendas/{uid}/events.json",
                 params={"limit": 100}).json()
        for e in d.get("events", []):
            for k in (e.get("keywords") or {}).get("fr") or []:
                if k and k not in ACCESS_KEYWORDS:
                    kws[k] = kws.get(k, 0) + 1
    except Exception as e:
        print(f"  ! scan keywords OA KO : {e}")
    return [(k, re.sub(r"[-_]+", " ", k).strip().capitalize())
            for k in sorted(kws, key=lambda k: (-kws[k], k.lower()))]


def _norm(s):
    import unicodedata
    s = unicodedata.normalize("NFD", s or "")
    return "".join(c for c in s
                   if not unicodedata.combining(c) and c.isalnum()).lower()


def filter_categories(events, cats):
    """Restreint aux événements dont la catégorie ou un tag correspond
    aux libellés/slugs listés (réglage `gen_categories`, virgules).
    Comparaison normalisée : « Concert » = « concert » = « concerts »
    ne matchera que le slug exact ou le libellé exact. Sélection vide
    = tout l'agenda."""
    wanted = {_norm(c) for c in (cats or []) if str(c).strip()}
    if not wanted:
        return events
    out = []
    for e in events:
        hay = {_norm(e.get("tag")), _norm(e.get("_oa_cat"))} | \
            {_norm(s) for s in e.get("tag_slugs") or []}
        if wanted & hay:
            out.append(e)
    return out

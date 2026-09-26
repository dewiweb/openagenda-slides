"""Extraction et helpers génériques : markdown-lite OA, specs,
intervenants, séries éditoriales. Aucune dépendance à un site
particulier — tout provient des champs OpenAgenda."""

import re

SPEC_ICONS = {"Date": "calendar", "Séances": "calendar", "Durée": "timer",
              "Lieu": "pin", "Tarif": "ticket", "Public": "group",
              "Accessibilité": "accessibility"}
SPEC_ORDER = ["Date", "Séances", "Durée", "Lieu", "Tarif", "Public",
              "Accessibilité"]

# codes d'accessibilité d'OpenAgenda (v2 et legacy)
VENUE_ACCESS = {
    "ii": "Handicap intellectuel", "hi": "Handicap auditif",
    "vi": "Handicap visuel", "mi": "Handicap moteur",
    "pi": "Handicap psychique",
}

# keywords OA « déficiences » → mention d'accessibilité actionnable
ACCESS_KEYWORDS = {
    "defautidif_lsf": "Interprétation en LSF",
    "defauditif_amp": "Dispositifs d'écoute amplifiée",
    "defvisuel": "Audiodescription",
}


# ———————————————————— texte ————————————————————

def _norm_ws(text):
    """Espaces invisibles OA (zero-width, insécable) → espace normal,
    sinon « 15h00Où » quand le saut de ligne markdown est réduit.
    Conserve les marqueurs markdown — version destinée au rendu HTML."""
    if not text:
        return ""
    return text.replace("​", " ").replace(" ", " ").strip()


def _clean_md(text):
    """Markdown-lite OA → texte plat (extraction, specs, UI)."""
    text = _norm_ws(text)
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)   # **gras**
    text = re.sub(r"__(.+?)__", r"\1", text)       # __gras__
    text = re.sub(r"(?<!\w)\*(.+?)\*(?!\w)", r"\1", text)  # *ital*
    text = re.sub(r"\[(.+?)\]\([^)]*\)", r"\1", text)      # [lien](url)
    text = re.sub(r"^#+\s*", "", text, flags=re.M)         # ## titre
    return text.strip()


# mentions d'accessibilité « actionnables » repérables dans la
# description (pas de champ dédié côté OpenAgenda : texte libre des
# programmateurs). Chaque motif produit un libellé normalisé affichable
# sur une diapo.
_ACCESS_PATTERNS = [
    (re.compile(r"interpr[ée]t\w*\s+en\s+LSF|langue des signes", re.I),
     "Interprétation en LSF"),
    (re.compile(r"audiodescri\w*|audio-description", re.I),
     "Audiodescription"),
    (re.compile(r"surtitr", re.I), "Surtitrage"),
    (re.compile(r"boucle magn[ée]tique|collier magn[ée]tique"
               r"|casque d'amplification", re.I),
     "Dispositifs d'écoute amplifiée"),
]


def _extract_access(text):
    """Mentions d'accessibilité trouvées dans la description détaillée,
    une par ligne, dédupliquées."""
    out = []
    for pat, label in _ACCESS_PATTERNS:
        if pat.search(text) and label not in out:
            out.append(label)
    return "\n".join(out)


# ——— extraction best-effort des intervenants / animateurs ———
# Les rédacteurs ont une certaine liberté ; les noms sont *souvent* en
# <strong> suivis de leur qualité, l'animateur signalé par « animé par ».
# Des replis existent (« X est qualité » dans le texte, « avec X » dans
# le titre). L'UI permet de corriger avant génération de la diapo du
# jour.

_NAME = r"[A-ZÀ-Ý][\wÀ-ÿ'’\-]+(?:\s+[A-ZÀ-Ý][\wÀ-ÿ'’\-]+){1,4}"

# coupe une qualité aux frontières narratives / mentions annexes
_QUALITY_CUT = re.compile(
    r"(?:\.(?=\s|$)"
    r"|\s+et\s+anim[ée]e?|\s+anim[ée]e?\s+par|\s+En lien|\s+En partenariat"
    r"|\s+Rencontre|\s+Suivie|\s+Dans le cadre|\s+Production\b"
    r"|\s+Auteurs?\b|\s+mise en scène|\s+dont\b"
    r"|,\s+(?:racontent|retrace|revient|explique|présente|analyse|interroge"
    r"|détaille|propose|débat|explore|explorent|décrypte|décryptent|imprime"
    r"|impriment|emmène|plonge|interprète|nous|ils|il)\b).*", re.S)

# la qualité commence directement par un verbe narratif → pas une qualité
_LEADING_VERB = re.compile(
    r"^(?:imprime|impriment|explore|explorent|retrace|retracent|décrypte"
    r"|décryptent|revient|reviennent|ensemble|nous|ils|il)\b")


def _clean_quality(t):
    t = " ".join(t.split())
    t = re.sub(r"^(?:est\s+|,\s*|:\s*)", "", t)
    t = _QUALITY_CUT.sub("", t)
    t = t.strip(" ,.;:")
    t = re.sub(r"\s+et$", "", t).strip()
    return "" if _LEADING_VERB.match(t) else t


def _is_name(s):
    return (
        3 <= len(s) <= 60 and ":" not in s and s[0].isupper()
        and len(s.split()) >= 2
    )


def _extract_people(intro_long, title, text):
    speakers, seen = [], set()

    def add(name, quality=""):
        name = name.strip(" ,.;:")
        if _is_name(name) and name not in seen:
            seen.add(name)
            speakers.append({"name": name, "quality": quality[:220]})

    # noms en <strong>/<b> : la qualité est le texte jusqu'au suivant
    strongs = []
    for st in (intro_long.select("strong, b") if intro_long else []):
        name = " ".join(st.get_text().split())
        bits = []
        for sib in st.next_siblings:
            if getattr(sib, "name", None) in ("strong", "b", "br", "p"):
                break
            bits.append(sib.get_text() if hasattr(sib, "get_text") else str(sib))
        strongs.append((name, "".join(bits)))
    quals = [_clean_quality(q) for _, q in strongs]
    for i, q in enumerate(quals):
        if q in ("et", "&") and i + 1 < len(quals):
            quals[i] = quals[i + 1]  # « A et B, qualité commune »
        elif q.startswith("et "):
            # « A et l'historien B » : la qualité est partagée par la paire
            shared = re.sub(
                r"^(?:l['’]|le |la |les |un |une |des )", "",
                q[3:].strip())
            quals[i] = shared
            if i + 1 < len(quals):
                quals[i + 1] = shared
    for (name, _), q in zip(strongs, quals):
        add(name, q)

    # repli : « X est qualité » directement dans le texte
    if not speakers:
        for m in re.finditer(rf"({_NAME})\s+est\s+([^.;\n]{{4,180}})", text):
            add(m.group(1), _clean_quality(m.group(2)))

    # repli : « … avec X » dans le titre
    if not speakers:
        m = re.search(r"avec\s+(.{3,50})$", title, re.I)
        if m:
            for nm in re.split(r"\s+et\s+|,", m.group(1)):
                add(nm)

    moderator = ""
    for pat in (r"anim[ée]e?\s+par\s+(" + _NAME + ")",
                r"présentée?\s+par\s+(" + _NAME + ")"):
        m = re.search(pat, text)
        if m:
            moderator = m.group(1)
            break
    # l'animateur n'est pas un intervenant
    if moderator:
        speakers = [s for s in speakers if s["name"] != moderator]
    return speakers, moderator


# phrases de la description détaillée qui relèvent d'une mention de pied
# de diapo (partenaires, dédicace…) — elles doivent *commencer* le
# segment pour éviter les faux positifs du récit. Proposition
# préremplie du champ « notes » de la diapo du jour.
_NOTE_RE = re.compile(
    r"^(?:en partenariat|en lien avec|dans le cadre|suivi[ée]e?\b"
    r"|rencontre suivie|entrée libre|sur réservation|séance de dédicace"
    r"|une séance de dédicace|gratuit\b)", re.I)


def _extract_note(text):
    notes = []
    for ln in (text or "").split("\n"):
        ln = " ".join(ln.split()).strip(" ​")
        if not ln:
            continue
        # retire le bout « animée par … » déjà affiché à part
        ln = re.sub(r"^.*?anim[ée]e?\s+par\s+" + _NAME, "", ln)
        for seg in re.split(r"(?<=[.!?])\s+", ln):
            seg = re.sub(r"^et\s+", "", seg.strip(" ,.;:"))
            if seg and _NOTE_RE.match(seg) and seg not in notes:
                notes.append(seg[0].upper() + seg[1:])
    return "\n".join(notes)


# ———————————————————— séries éditoriales ————————————————————
# format du réglage series_map : une ligne « identifiant = Libellé »
# ou « identifiant = Libellé | chemin/logo.png » (l'identifiant est un
# keyword OpenAgenda de l'événement). Lignes vides/# ignorées.

def parse_series(text):
    """Renvoie une liste de (identifiant, libellé, logo)."""
    out = []
    for line in (text or "").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, rest = line.split("=", 1)
        label, _, logo = rest.partition("|")
        k, label, logo = k.strip(), label.strip(), logo.strip()
        if k and label:
            out.append((k, label, logo or None))
    return out


def parse_series_map(text):
    """identifiant → libellé (matching keywords OA)."""
    return {k: l for k, l, _ in parse_series(text)}


def parse_cats(text):
    """« slug1, libellé 2 » → liste de termes de filtrage
    (réglage gen_categories)."""
    return [t.strip() for t in (text or "").split(",") if t.strip()]


def parse_kv(text):
    """« Clé = valeur » par ligne → dict (réglage spec_overrides).
    Lignes vides/# ignorées."""
    out = {}
    for line in (text or "").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k, v = k.strip(), v.strip()
        if k:
            out[k] = v
    return out


def series_logo(text, label):
    """Chemin du logo associé au libellé de série, ou None."""
    return next((g for _, l, g in parse_series(text)
                 if l == label and g), None)


def _norm_series(s):
    """minuscules, sans accents ni séparateurs — tolère « Grandstemoins »
    vs « grandstemoins » ou « Les grands témoins »."""
    import unicodedata
    s = unicodedata.normalize("NFD", s or "")
    return "".join(c for c in s
                   if not unicodedata.combining(c) and c.isalnum()).lower()


def series_brand(text, series):
    """Résout (libellé canonique, logo) pour une série détectée —
    events.json peut contenir un libellé d'une ancienne config ou le
    keyword brut : on matche clé et libellé de series_map (normalisés).
    Renvoie (None, None) si la série n'est pas dans le tableau —
    l'appelant garde alors la valeur brute."""
    s = _norm_series(series)
    if not s:
        return "", None
    for k, l, g in parse_series(text):
        nk, nl = _norm_series(k), _norm_series(l)
        if s == nl or s == nk or s in nk or nk in s:
            return l, g
    return None, None

"""Réglages persistés (settings.json dans le dossier de sortie) + état
runtime partagé."""

import json
import os
import threading
from pathlib import Path

from .paths import OUT_DIR as DEFAULT_OUT
from . import secrets

OUT_DIR = Path(os.environ.get("OUT_DIR", DEFAULT_OUT))
SETTINGS_FILE = Path(os.environ.get("SETTINGS_FILE", OUT_DIR / "settings.json"))

DEFAULTS = {
    # ——— source OpenAgenda ———
    "oa_agenda": "",            # slug ou uid numérique — obligatoire
    "oa_api_key": "",           # optionnel : API v2, sinon export public
    # ——— identité visuelle ———
    "org_name": "",             # nom de la structure (diapo du jour)
    "program_url": "",          # page programme — footer (défaut :
    #                           https://openagenda.com/<agenda>)
    "footer_text": "Tout le programme sur",  # accroche du pied de page
    #                                        (vide = URL seule)
    "logo_path": "",            # logo SVG/PNG (filigrane, badge série)
    "card_bg": "#efeae6",       # fond des diapos
    "accent": "#e2dff0",        # pastille du jour, badge de série
    "font_family": "",          # vide = pile système
    # ——— contenu ———
    "tag_group": "",            # slug du groupe de tags servant de
    #                           catégorie (vide = auto : « categorie* »)
    "gen_categories": "",       # slugs/libellés de tags retenus,
    #                           virgules (vide = tout l'agenda)
    "series_map": "",           # « keyword = Libellé | logo.png »/ligne
    # ——— specs affichées sur les diapos ———
    "specs_show": "",           # clés affichées, virgules — vide =
    #                           toutes (Date toujours affichée)
    "spec_overrides": "",       # « Clé = valeur forcée »/ligne
    "next_label": "Prochaine séance : ",  # préfixe récurrent (vide =
    #                                     date seule)
    # ——— fenêtre de génération ———
    "interval_min": 0,
    "sched_times": "",
    "max_events": 0,
    "limit_mode": "count",   # count | days | date
    "limit_days": 14,
    "limit_date": "",        # ISO YYYY-MM-DD
    "resolution": "uhd",
    "gen_landscape": 1,
    "gen_portrait": 0,
    "portrait_format": "a4",  # a4 (impression) | screen (écran 9:16)
    # ——— destinations ———
    "ftp_host": "",
    "ftp_port": 21,
    "ftp_user": "",
    "ftp_pass": "",
    "ftp_path": "/",
    "ftp_tls": 0,
    "ftp_send_landscape": 1,
    "ftp_send_portrait": 0,
    "smb_host": "",
    "smb_share": "",
    "smb_path": "",
    "smb_user": "",
    "smb_pass": "",
    "smb_send_landscape": 1,
    "smb_send_portrait": 0,
    "local_dir": "",
    "local_send_landscape": 1,
    "local_send_portrait": 0,
    "out_dir": "",
    # ——— app ———
    "close_to_tray": 1,
    "start_minimized": 0,
    "autostart_app": 0,
    "autostart_slideshow": "none",
    "ss_delay": 8,
    "ss_transition": "fade",
    "ss_tdur": 1500,
    "ss_screen": -1,
    "ss_delay_p": 8,
    "ss_transition_p": "fade",
    "ss_tdur_p": 1500,
    "ss_screen_p": -1,
}

# état runtime (génération en cours, journal, dernier run)
state = {"running": False, "last_run": None, "last_error": None, "log": []}
lock = threading.Lock()

# last_run persisté : lu une seule fois au démarrage — les appels
# suivants de load_settings() ne doivent pas écraser la valeur
# courante (course avec le writer de run_generation).
try:
    state["last_run"] = json.loads(
        SETTINGS_FILE.read_text()).get("last_run")
except Exception:
    pass


def load_settings():
    try:
        s = json.loads(SETTINGS_FILE.read_text())
    except Exception:
        s = {}
    out = dict(DEFAULTS)
    for k, d in DEFAULTS.items():
        v = s.get(k, d)
        if isinstance(d, int):
            try:
                out[k] = int(v)
            except (TypeError, ValueError):
                pass
        else:
            out[k] = str(v)
    # secrets : env var puis trousseau OS priment sur le fichier ;
    # la valeur en clair du JSON reste le dernier repli
    for k in secrets.KEYS:
        v = secrets.load(k)
        if v is not None:
            out[k] = v
    return out


def resolve_out_dir(cfg=None):
    """Dossier de sortie effectif : réglage `out_dir` (disque local,
    lecteur mappé, UNC) s'il est rempli, sinon OUT_DIR env/défaut."""
    if cfg is None:
        cfg = load_settings()
    d = (cfg.get("out_dir") or "").strip()
    return Path(d) if d else OUT_DIR


def save_settings(s):
    """Écriture atomique (tmp + os.replace) : un crash en cours
    d'écriture ne peut pas tronquer settings.json."""
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(s)
    # secrets → trousseau OS quand il existe ; le fichier ne garde
    # alors que des chaînes vides (migration des anciens fichiers :
    # la valeur en clair disparaît au premier enregistrement)
    for k in secrets.KEYS:
        if payload.get(k) and secrets.store(k, payload[k]):
            payload[k] = ""
    if state["last_run"]:
        payload["last_run"] = state["last_run"]
    tmp = SETTINGS_FILE.with_name(SETTINGS_FILE.name + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2))
    os.replace(tmp, SETTINGS_FILE)

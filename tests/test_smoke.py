"""Smoke tests — filet de sécurité minimal avant un build.

Lancés par la CI (unittest, pas de dépendance externe au-delà du
requirements runtime) :
    python -m unittest discover -s tests -v

Couvre : round-trip des réglages, résolution des secrets,
comparaison de versions, autostart, parsing des séries, et le
mapping OpenAgenda legacy (tagGroups, timings, champs absents).
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

# env posé AVANT tout import oaslides — settings.py lit les
# variables au moment de l'import
_TMP = Path(tempfile.mkdtemp(prefix="oas-test-"))
os.environ["OUT_DIR"] = str(_TMP)
os.environ["SETTINGS_FILE"] = str(_TMP / "settings.json")
os.environ["OASLIDES_CACHE_DIR"] = str(_TMP / "cache")
os.environ["OASLIDES_FONT_DIR"] = str(_TMP / "fonts")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from oaslides import autostart, secrets                 # noqa: E402
from oaslides import settings as st                     # noqa: E402
from oaslides import version                            # noqa: E402
from oaslides.extract import parse_series_map, series_brand  # noqa: E402
from oaslides import oa                                 # noqa: E402


class SettingsTest(unittest.TestCase):

    def test_roundtrip_and_atomic_write(self):
        s = st.load_settings()
        s["interval_min"] = 90
        s["out_dir"] = "D:\\diaporama"
        s["limit_mode"] = "days"
        s["oa_agenda"] = "mon-agenda"
        st.save_settings(s)
        s2 = st.load_settings()
        self.assertEqual(s2["interval_min"], 90)
        self.assertEqual(s2["out_dir"], "D:\\diaporama")
        self.assertEqual(s2["limit_mode"], "days")
        self.assertEqual(s2["oa_agenda"], "mon-agenda")
        # le fichier est du JSON valide, pas de .tmp résiduel
        json.loads((_TMP / "settings.json").read_text())
        self.assertFalse((_TMP / "settings.json.tmp").exists())

    def test_defaults_present(self):
        s = st.load_settings()
        for k in ("ss_delay", "ss_screen", "autostart_app",
                  "gen_landscape", "oa_agenda", "accent", "card_bg",
                  "tag_group", "gen_categories"):
            self.assertIn(k, s)

    def test_resolve_out_dir_override(self):
        s = st.load_settings()
        s["out_dir"] = str(_TMP / "custom")
        self.assertEqual(st.resolve_out_dir(s), _TMP / "custom")


class SecretsTest(unittest.TestCase):

    def test_env_wins(self):
        os.environ["OASLIDES_FTP_PASS"] = "s3cret!"
        try:
            self.assertEqual(secrets.load("ftp_pass"), "s3cret!")
            self.assertEqual(secrets.where("ftp_pass"), "env")
            # store() avec env override : la valeur ne doit pas rester
            # dans le fichier
            self.assertTrue(secrets.store("ftp_pass", "s3cret!"))
        finally:
            del os.environ["OASLIDES_FTP_PASS"]

    def test_missing_secret(self):
        self.assertIsNone(secrets.load("ftp_pass"))


class VersionTest(unittest.TestCase):

    def test_newer(self):
        version.VERSION = "0.5.0"
        self.assertTrue(version.newer_than_current("v0.5.1"))
        self.assertTrue(version.newer_than_current("v0.6.0-beta.1"))
        self.assertFalse(version.newer_than_current("v0.5.0"))
        self.assertFalse(version.newer_than_current("v0.4.9"))


class UiCollisionTest(unittest.TestCase):
    """Deux mixins ne doivent pas définir le même nom de méthode :
    la MRO de MainWindow en masque une et les signaux Qt connectés à
    `self.<nom>` tombent sur la mauvaise — silencieusement, car
    PySide6 ignore les arguments excédentaires (bug réel :
    _preview_slide existait dans GeneralTabMixin et GalleryTabMixin,
    le double-clic galerie rendait l'aperçu « branding »).

    Analyse statique par AST : importer les modules tirerait PySide6,
    indisponible sur un runner sans libs GL."""

    def test_no_shadowed_methods_between_mixins(self):
        import ast
        ui = ROOT / "ui"
        seen, dup = {}, []
        for fname in ("tabs_general.py", "tabs_destinations.py",
                      "tabs_gallery.py", "today.py"):
            tree = ast.parse((ui / fname).read_text("utf-8"))
            for node in ast.walk(tree):
                if not isinstance(node, ast.ClassDef):
                    continue
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef,
                                         ast.AsyncFunctionDef)) \
                            and not item.name.startswith("__"):
                        if item.name in seen:
                            dup.append(f"{item.name} : "
                                       f"{seen[item.name]} vs "
                                       f"{fname}:{node.name}")
                        else:
                            seen[item.name] = f"{fname}:{node.name}"
        self.assertEqual(dup, [])


class AutostartTest(unittest.TestCase):

    def test_cmd_known(self):
        # _cmd() ne doit jamais renvoyer None — sinon apply() écrirait
        # une entrée autostart vide
        cmd = autostart._cmd()
        self.assertIsInstance(cmd, str)
        self.assertTrue(cmd.strip())

    @unittest.skipUnless(sys.platform == "linux", "autostart freedesktop")
    def test_apply_linux(self):
        autostart.apply(True)
        f = autostart._linux_file()
        self.assertTrue(f.exists())
        self.assertIn("OpenAgendaSlides", f.read_text())
        autostart.apply(False)
        self.assertFalse(f.exists())


class ParseTest(unittest.TestCase):

    def test_series_map(self):
        text = ("grandstemoins = Les grands témoins | logo.png\n"
                "autre = Autre série\n"
                "# commentaire")
        m = parse_series_map(text)
        self.assertEqual(m.get("grandstemoins"), "Les grands témoins")
        self.assertEqual(m.get("autre"), "Autre série")

    def test_series_brand_tolerant(self):
        text = "grandstemoins = Les grands témoins | gt.png"
        # le keyword brut stocké dans un events.json doit retrouver
        # le libellé canonique et le logo
        lbl, logo = series_brand(text, "Grandstemoins")
        self.assertEqual(lbl, "Les grands témoins")
        self.assertEqual(logo, "gt.png")
        lbl, _ = series_brand(text, "inconnue")
        self.assertIsNone(lbl)


# ———————————————————— mapping OpenAgenda ————————————————————

def _legacy_ev(**kw):
    """Événement legacy minimal plausible ; kw écrase les défauts."""
    import datetime as dt
    nxt = dt.date.today() + dt.timedelta(days=10)
    base = {
        "uid": 1234,
        "title": {"fr": "Concert test"},
        "description": {"fr": "Une soirée **exceptionnelle**."},
        "longDescription": {"fr": "Avec **Alice Durand**, journaliste, "
                                  "animée par Bob Martin."},
        "html": {"fr": "<p>Avec <strong>Alice Durand</strong>, "
                       "journaliste, animée par Bob Martin.</p>"},
        "canonicalUrl": "https://openagenda.com/x/events/1234",
        "conditions": {"fr": "gratuit, sur inscription"},
        "timings": [
            {"start": f"{nxt.isoformat()}T20:00:00+02:00",
             "end": f"{nxt.isoformat()}T22:00:00+02:00"},
        ],
        "tagGroups": [
            {"slug": "categorie", "name": "Catégorie",
             "tags": [{"slug": "concert", "label": "Concert"}]},
            {"slug": "publics", "name": "Publics",
             "tags": [{"slug": "tout-public", "label": "Tout public"}]},
        ],
        "keywords": {"fr": ["grandstemoins", "defauditif_amp"]},
        "originalImage": "https://exemple.fr/visu.jpg",
        "imageCredits": "© DR",
        "location": {"name": "La salle", "timezone": "Europe/Paris"},
        "attendanceMode": 1,
        "age": {"min": 12},
    }
    base.update(kw)
    return base


class OaMapTest(unittest.TestCase):

    def test_legacy_basic(self):
        ev = oa._map_legacy(_legacy_ev(),
                            {"grandstemoins": "Les grands témoins"})
        self.assertEqual(ev["title"], "Concert test")
        self.assertEqual(ev["tag"], "Concert")
        self.assertIn("20h", ev["specs"]["Date"])
        self.assertEqual(ev["specs"]["Tarif"],
                         "Gratuit, sur inscription")
        self.assertEqual(ev["specs"]["Public"],
                         "Tout public · dès 12 ans")
        self.assertEqual(ev["specs"]["Lieu"], "La salle")
        self.assertEqual(ev["series"], "Les grands témoins")
        self.assertIn("Dispositifs d'écoute amplifiée",
                      ev["access"])
        self.assertFalse(ev["online"])
        self.assertIn("grandstemoins", ev["keywords"])
        self.assertIn("concert", ev["tag_slugs"])
        # intervenants extraits du HTML/markdown
        names = [s["name"] for s in ev["speakers"]]
        self.assertIn("Alice Durand", names)
        self.assertEqual(ev["moderator"], "Bob Martin")

    def test_no_taggroups(self):
        ev = oa._map_legacy(_legacy_ev(tagGroups=None))
        self.assertEqual(ev["tag"], "Événement")
        self.assertNotIn("Public", ev["specs"].get("Public", "") or ""
                         and {} or {"Public": ev["specs"].get("Public")}
                         and {"ok": 1} or {})
        # dès N ans remonte quand même
        self.assertEqual(ev["specs"]["Public"], "Dès 12 ans")

    def test_no_timings_range_fallback(self):
        ev = oa._map_legacy(_legacy_ev(
            timings=None, range={"fr": "Tous les jours de 10h à 18h"}))
        self.assertEqual(ev["specs"]["Date"],
                         "Tous les jours de 10h à 18h")

    def test_no_timings_no_range(self):
        ev = oa._map_legacy(_legacy_ev(timings=None, range=None))
        self.assertEqual(ev["specs"]["Date"], "En continu")

    def test_custom_cat_group(self):
        # agenda dont le groupe catégorie ne s'appelle pas « categorie »
        e = _legacy_ev(tagGroups=[
            {"slug": "categories-metropolitaines",
             "name": "Catégories Métropolitaines",
             "tags": [{"slug": "sante", "label": "Santé"}]},
            {"slug": "publics", "name": "Publics",
             "tags": [{"slug": "ados", "label": "Ados"}]},
        ])
        ev = oa._map_legacy(e, cat_group="categories-metropolitaines")
        self.assertEqual(ev["tag"], "Santé")
        self.assertIn("Ados", ev["specs"]["Public"])

    def test_online_event(self):
        ev = oa._map_legacy(_legacy_ev(attendanceMode=2))
        self.assertTrue(ev["online"])

    def test_filter_categories(self):
        evs = [oa._map_legacy(_legacy_ev()),
               oa._map_legacy(_legacy_ev(
                   tagGroups=[{"slug": "categorie", "name": "Cat",
                               "tags": [{"slug": "expo",
                                         "label": "Exposition"}]}]))]
        self.assertEqual(len(oa.filter_categories(evs, [])), 2)
        self.assertEqual(len(oa.filter_categories(evs, ["concert"])), 1)
        self.assertEqual(len(oa.filter_categories(
            evs, ["Exposition"])), 1)

    def test_recurring_sessions(self):
        import datetime as dt
        d0 = dt.date.today() + dt.timedelta(days=3)
        timings = [
            {"start": (d0 + dt.timedelta(days=i)).isoformat()
                      + "T19:00:00+02:00",
             "end": (d0 + dt.timedelta(days=i)).isoformat()
                    + "T20:30:00+02:00"}
            for i in range(0, 21, 7)
        ]
        ev = oa._map_legacy(_legacy_ev(timings=timings))
        self.assertTrue(ev["specs"]["Date"].startswith("Prochaine"))
        self.assertEqual(ev["specs"]["Durée"], "1h30")

    def test_spec_prefs(self):
        prefs = {
            "next_label": "",                       # pas de préfixe
            "specs_show": {"Durée", "Tarif"},       # Lieu/Public masqués
            "spec_overrides": {"Tarif": "Gratuit",
                               "Lieu": "Salle A"},  # ajout forcé
        }
        ev = oa._map_legacy(_legacy_ev(), prefs=prefs)
        self.assertNotIn("Prochaine", ev["specs"]["Date"])
        self.assertNotIn("Public", ev["specs"])
        self.assertEqual(ev["specs"]["Tarif"], "Gratuit")
        # « Lieu » masqué dans specs_show : l'override ne le réintroduit
        # pas non plus
        self.assertNotIn("Lieu", ev["specs"])
        # override sur une spec affichée qui n'existe pas → ajoutée
        prefs["specs_show"] = {"Durée", "Lieu"}
        ev = oa._map_legacy(
            _legacy_ev(location=None, locationName=""), prefs=prefs)
        self.assertEqual(ev["specs"]["Lieu"], "Salle A")


def _v2_ev(**kw):
    """Événement v2 plausible ; kw écrase les défauts. Mélange dicts
    multilingues et chaînes aplaties (monolingual=fr)."""
    import datetime as dt
    nxt = dt.date.today() + dt.timedelta(days=10)
    base = {
        "uid": 9, "slug": "concert-x",
        "title": {"fr": "Concert v2"},
        "description": "Chaîne monolingue aplatie",
        "longDescription": {"fr": "Avec **Jean Martin**."},
        "conditions": {"fr": "5 €"},
        "keywords": {"fr": ["seriefest"]},
        "categorie": 1,                       # id d'option standard
        "categories-metropolitaines": [2],    # champ additionnel
        "publics": [3],
        "timings": [
            {"begin": f"{nxt.isoformat()}T20:00:00.000+02:00",
             "end": f"{nxt.isoformat()}T22:00:00.000+02:00"},
        ],
        "attendanceMode": 1,
        "age": {"min": 6},
        "location": {"name": "Salle V2", "timezone": "Europe/Paris"},
        "image": {"base": "https://x.fr/", "filename": "a.jpg"},
    }
    base.update(kw)
    return base


class OaV2Test(unittest.TestCase):
    OPT_FIELDS = {
        "categorie": {1: ("concert", "Concert")},
        "categories-metropolitaines": {2: ("sante", "Santé")},
        "publics": {3: ("tout-public", "Tout public")},
    }

    def test_v2_basic(self):
        ev = oa._map_v2(_v2_ev(), self.OPT_FIELDS, "categorie",
                        "mon-agenda", {"seriefest": "Festival"})
        self.assertEqual(ev["title"], "Concert v2")
        self.assertEqual(ev["tag"], "Concert")
        self.assertEqual(ev["desc"], "Chaîne monolingue aplatie")
        self.assertEqual(ev["specs"]["Tarif"], "5 €")
        self.assertEqual(ev["specs"]["Public"], "Tout public · dès 6 ans")
        self.assertEqual(ev["series"], "Festival")
        # slugs d'options de TOUS les champs alimentent le filtre
        for s in ("concert", "sante", "tout-public"):
            self.assertIn(s, ev["tag_slugs"])
        self.assertIn("9_concert-x", ev["url"])

    def test_v2_custom_cat_field(self):
        # tag_group pointant sur un champ additionnel
        ev = oa._map_v2(_v2_ev(), self.OPT_FIELDS,
                        "categories-metropolitaines", "a")
        self.assertEqual(ev["tag"], "Santé")

    def test_v2_keywords_none(self):
        ev = oa._map_v2(_v2_ev(keywords=None), self.OPT_FIELDS,
                        "categorie", "a")
        self.assertEqual(ev["tag"], "Concert")

    def test_langs_flat_and_dict(self):
        self.assertEqual(oa._langs({"fr": "x"}), "x")
        self.assertEqual(oa._langs("chaîne"), "chaîne")
        self.assertEqual(oa._langs(None), "")
        self.assertEqual(oa._langs({"de": "nur"}), "nur")  # repli 1ʳᵉ langue


if __name__ == "__main__":
    unittest.main()

"""Onglet « Style » — mixin de MainWindow : tout ce qui concerne
l'apparence des diapos est réuni ici.

- Identité visuelle : structure, URL, accroche, logo, couleurs, fonte
  (réglages de la diapo — collectés/enregistrés comme avant, même clés).
- Métriques des gabarits : chaque assets/slide_template*.html expose
  ses réglages en variables CSS `--var` dans son bloc :root (cf.
  assets/README.md) — présentées en champs numériques par orientation.
- Aperçu : diapo d'exemple re-rendue à chaque modification
  (débrayable), ou vraie diapo de l'agenda à la demande.

Seules les valeurs différentes du défaut du gabarit sont enregistrées
(clé `style_overrides` : {orientation: {"--var": "val"}}) — une
évolution des défauts bénéficie aux paramètres non retouchés.
Aucun __init__ propre : les méthodes sont appelées sur la fenêtre.
"""

import base64
import io
import tempfile
import threading
from pathlib import Path

from PySide6.QtCore import Qt, QEvent, QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFormLayout, QFrame, QGroupBox, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QScrollArea, QSpinBox, QVBoxLayout,
    QWidget,
)

from oaslides.settings import load_settings

# paramètres exposés : (--var CSS du gabarit, libellé, min, max, suffixe)
STYLE_GROUPS = [
    ("Carte & visuel", [
        ("--card-radius", "Arrondi de la carte", 0, 140, " px"),
        ("--photo-radius", "Arrondi du visuel", 0, 100, " px"),
        ("--wm-size", "Filigranes de logo — taille", 0, 1400, " px"),
    ]),
    ("Textes", [
        ("--h1-lines", "Titre — lignes max", 1, 8, ""),
        ("--desc-size", "Description — corps", 12, 90, " px"),
        ("--desc-lines", "Description — lignes max", 1, 12, ""),
        ("--spec-size", "Infos pratiques — corps", 12, 90, " px"),
    ]),
    ("Pastille & pied de page", [
        ("--tag-size", "Pastille catégorie — corps", 12, 72, " px"),
        ("--attrib-size", "Pied de page — corps", 8, 48, " px"),
    ]),
]

ORIENTATIONS = [
    ("Paysage 16:9", "landscape"),
    ("Portrait A4", "portrait"),
    ("Portrait écran 9:16", "portrait-screen"),
]


class StyleTabMixin:

    def _style_tab(self):
        outer = QWidget()
        outer_lay = QVBoxLayout(outer)
        outer_lay.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea(widgetResizable=True)
        scroll.setFrameShape(QFrame.NoFrame)
        w = QWidget()
        scroll.setWidget(w)
        outer_lay.addWidget(scroll)
        lay = QVBoxLayout(w)
        lay.setContentsMargins(18, 14, 18, 14)
        lay.setSpacing(14)

        self._style_ovr = {}       # {orientation: {"--var": "val"}}
        self._style_boxes = {}     # {"--var": QSpinBox}
        self._style_loading = False
        self._style_busy = False
        self._style_pm = None      # dernier rendu, re-scalé au resize
        self._style_seen = False   # premier affichage → premier rendu

        body = QHBoxLayout()
        body.setSpacing(14)

        # ——— colonne gauche : identité + métriques ———
        params = QVBoxLayout()
        params.setSpacing(12)

        ident = QGroupBox("Identité visuelle")
        f = QFormLayout(ident)
        f.setLabelAlignment(Qt.AlignRight)
        self.org_name = QLineEdit(
            placeholderText="nom affiché de la structure")
        self.program_url = QLineEdit(
            placeholderText="https://mon-site.fr/programme — vide = "
                            "page OpenAgenda de l'agenda")
        self.footer_text = QLineEdit(
            placeholderText="Tout le programme sur / Retrouvez-nous "
                            "sur…")
        self.logo_path = QLineEdit(
            placeholderText="SVG monochrome ou PNG à fond transparent")
        self.logo_path.setToolTip(
            "Format attendu :\n"
            "• SVG monochrome de préférence — il est reteinté "
            "automatiquement selon le contexte (filigrane clair sur "
            "fond sombre, foncé sur carte claire, dans le badge de "
            "série). Utiliser fill=\"currentColor\" ou une couleur "
            "unique ; un SVG multicolore gardera ses couleurs mais "
            "pourra peu contraster.\n"
            "• PNG/WebP : fond transparent obligatoire — sinon le "
            "rectangle opaque apparaîtra dans les filigranes.\n"
            "• Forme plutôt carrée : affiché dans un cadre carré, "
            "jamais rogné (contain).\n"
            "• Le SVG vectoriel reste net à toutes les tailles — "
            "pour un raster, prévoir ≥ 800 px de large.")
        brow = QHBoxLayout()
        brow.addWidget(self.logo_path, 1)
        br = QPushButton("Parcourir…")
        br.setProperty("ghost", True)
        br.clicked.connect(self._pick_logo)
        brow.addWidget(br)
        f.addRow("Structure", self.org_name)
        f.addRow("URL du programme", self.program_url)
        f.addRow("Accroche du pied", self.footer_text)
        f.addRow("Logo", brow)
        self.card_bg = self._color_row(f, "Fond des diapos", "#efeae6")
        self.accent = self._color_row(f, "Accentuation", "#e2dff0")
        self.font_family = QLineEdit(
            placeholderText="vide = pile système · ex. « Inter Regular » "
                            "(famille CSS ou fichier du dossier fonts/)")
        self.font_family.setToolTip(
            "Famille de fonte CSS : nom seul (espaces OK, guillemets "
            "facultatifs) ou pile « Inter, Helvetica ». Pour une fonte "
            "embarquée, déposer le fichier dans fonts/ et écrire le nom "
            "du fichier sans extension, tirets remplacés par des espaces "
            "(Inter-SemiBold.woff2 → « Inter SemiBold »). La pile "
            "système de repli est toujours ajoutée.")
        f.addRow("Fonte", self.font_family)
        # verdict de résolution : la pile CSS replie en silence si la
        # famille est absente — l'aperçu resterait identique sans
        # qu'on comprenne pourquoi
        self.font_hint = QLabel("")
        f.addRow("", self.font_hint)
        self.font_family.textChanged.connect(self._font_check)
        self._font_check()
        # identité : retouche visible à l'aperçu sans attendre le save —
        # textChanged couvre aussi la pipette et « Parcourir… » (qui ne
        # passent pas par editingFinished)
        for w_ in (self.org_name, self.program_url, self.footer_text,
                   self.logo_path, self.card_bg, self.accent,
                   self.font_family):
            w_.textChanged.connect(self._style_soft_refresh)
        params.addWidget(ident)

        # ——— format + actions ———
        head = QGroupBox("Format retouché")
        h = QHBoxLayout(head)
        self.style_fmt = QComboBox()
        for label, key in ORIENTATIONS:
            self.style_fmt.addItem(label, key)
        self.style_fmt.setFixedWidth(210)
        self.style_fmt.currentIndexChanged.connect(
            self._style_fmt_changed)
        h.addWidget(self.style_fmt)
        h.addSpacing(14)
        self.style_auto = QCheckBox("Aperçu automatique")
        self.style_auto.setChecked(True)
        h.addWidget(self.style_auto)
        h.addStretch(1)
        rst = QPushButton("Réinitialiser ce format")
        rst.setProperty("ghost", True)
        rst.clicked.connect(self._style_reset)
        h.addWidget(rst)
        params.addWidget(head)

        # ——— métriques du gabarit (variables --… du :root) ———
        for title, rows in STYLE_GROUPS:
            g = QGroupBox(title)
            f = QFormLayout(g)
            f.setLabelAlignment(Qt.AlignRight)
            for var, label, lo, hi, unit in rows:
                sb = QSpinBox(minimum=lo, maximum=hi, suffix=unit)
                sb.setFixedWidth(110)
                sb.setToolTip(var)
                sb.valueChanged.connect(self._style_changed)
                self._style_boxes[var] = sb
                f.addRow(label, sb)
            params.addWidget(g)
        params.addStretch(1)
        body.addLayout(params)

        # ——— aperçu ———
        pv = QGroupBox("Aperçu")
        pv_lay = QVBoxLayout(pv)
        self.style_view = QLabel("aperçu en attente")
        self.style_view.setAlignment(Qt.AlignCenter)
        self.style_view.setMinimumSize(430, 300)
        pv_lay.addWidget(self.style_view, 1)
        hint = QLabel("L'aperçu reflète les réglages courants — "
                      "« Enregistrer » pour les appliquer.")
        hint.setWordWrap(True)
        pv_lay.addWidget(hint)
        row = QHBoxLayout()
        self.style_status = QLabel("")
        row.addWidget(self.style_status, 1)
        ref = QPushButton("Rafraîchir")
        ref.setProperty("ghost", True)
        ref.clicked.connect(self._style_preview)
        row.addWidget(ref)
        real = QPushButton("Avec un événement réel")
        real.setProperty("ghost", True)
        real.setToolTip("Enregistre les réglages puis rend une vraie "
                        "diapo de l'agenda — la plus représentative "
                        "(image + infos)")
        real.clicked.connect(self._preview_slide)
        row.addWidget(real)
        self.preview_lbl = QLabel("")
        pv_lay.addLayout(row)
        pv_lay.addWidget(self.preview_lbl)
        body.addWidget(pv, 1)
        lay.addLayout(body, 1)

        # délai court : une série de retouches ne déclenche qu'un rendu
        self._style_timer = QTimer(
            self, singleShot=True, interval=600,
            timeout=self._style_preview)

        # premier rendu à la première visite de l'onglet (lazy — le
        # démarrage de l'app ne paie pas le lancement de Chromium) ;
        # resize de la zone → re-scale du dernier rendu
        outer.installEventFilter(self)
        self.style_view.installEventFilter(self)

        self._style_reload_boxes()
        return outer

    def eventFilter(self, obj, ev):
        if ev.type() == QEvent.Show and obj is self._tab_style \
                and not self._style_seen:
            self._style_seen = True
            if self.style_auto.isChecked():
                self._style_timer.start()
        elif ev.type() == QEvent.Resize and obj is self.style_view \
                and self._style_pm:
            self._style_view_update()
        return super().eventFilter(obj, ev)

    # ——— état ———

    def _style_orientation(self):
        return self.style_fmt.currentData() or "landscape"

    def _style_defaults(self, orientation=None):
        """Valeurs par défaut du gabarit (lues dans son :root)."""
        from oaslides import slide as sl
        return sl.template_vars(orientation or self._style_orientation())

    @staticmethod
    def _style_num(css_val):
        """'31px' → 31 ; 'auto'/vide → 0 (pour les spinboxes)."""
        import re
        m = re.match(r"(-?\d+(?:\.\d+)?)", str(css_val or ""))
        return float(m.group(1)) if m else 0

    def _style_reload_boxes(self):
        """Remplit les champs : surcharge enregistrée sinon défaut, avec
        repère visuel « modifié » et défaut du gabarit en infobulle."""
        self._style_loading = True
        try:
            ovr = self._style_ovr.get(self._style_orientation()) or {}
            defs = self._style_defaults()
            for var, sb in self._style_boxes.items():
                raw = ovr.get(var) or defs.get(var)
                sb.setValue(int(round(self._style_num(raw))))
                sb.setToolTip(f"{var} — défaut du gabarit : "
                              f"{defs.get(var, '?')}")
                self._style_mark(sb, var in ovr)
        finally:
            self._style_loading = False

    @staticmethod
    def _style_mark(sb, on):
        """Bordure accentuée sur un champ dont la valeur ≠ défaut."""
        if bool(sb.property("modified")) != on:
            sb.setProperty("modified", on)
            sb.style().unpolish(sb)
            sb.style().polish(sb)

    def _style_fmt_changed(self, *_):
        self._style_reload_boxes()
        if self.style_auto.isChecked():
            self._style_timer.start()

    def _style_changed(self, *_):
        if self._style_loading:
            return
        ori = self._style_orientation()
        defs = self._style_defaults(ori)
        cur = {}
        for var, sb in self._style_boxes.items():
            default = self._style_num(defs.get(var))
            modified = abs(sb.value() - default) > 1e-6
            self._style_mark(sb, modified)
            if modified:
                # unité du défaut conservée (px) ; sans suffixe sinon
                unit = "px" if str(defs.get(var, "")).endswith("px") \
                    else ""
                cur[var] = f"{sb.value()}{unit}"
        if cur:
            self._style_ovr[ori] = cur
        else:
            self._style_ovr.pop(ori, None)
        self._mark_dirty()
        if self.style_auto.isChecked():
            self._style_timer.start()

    def _style_reset(self):
        self._style_ovr.pop(self._style_orientation(), None)
        self._style_reload_boxes()
        self._mark_dirty()
        if self.style_auto.isChecked():
            self._style_timer.start()

    # ——— collecte / chargement (appelés par window.py) ———

    def _style_collect(self):
        return {o: dict(v) for o, v in self._style_ovr.items() if v}

    def _style_load(self, data):
        self._style_ovr = {o: dict(v) for o, v in (data or {}).items()
                           if isinstance(v, dict)}
        self._style_reload_boxes()

    # ——— aperçu ———

    def _style_preview(self):
        """Rend une diapo d'exemple avec les réglages COURANTS de l'UI
        (non enregistrés) — identité + surcharges de style — en worker,
        puis affiche le PNG dans l'onglet."""
        if self._style_busy:
            self._style_timer.start()  # un rendu est en cours : replanifie
            return
        from oaslides.settings import state
        if state["running"]:
            # pas de navigateur de rendu concurrent d'une génération
            self.style_status.setText("génération en cours…")
            self._style_timer.start()
            return
        self._style_busy = True
        self.style_status.setText("rendu…")
        ori = self._style_orientation()
        cfg = self._collect()  # capture l'état courant, sans enregistrer

        def work():
            import oaslides.slide as sl
            prev_brand, prev_cfg = sl._BRAND, sl._CFG
            try:
                sl.brand(cfg)
                ev = _sample_event()
                html = sl.slide_html(ev, 0, _fonts(), ori)
                d = tempfile.mkdtemp(prefix="oaslides-style-")
                hp = Path(d) / "style.html"
                pp = Path(d) / "style.png"
                hp.write_text(html, encoding="utf-8")
                w, h = sl.DESIGNS[ori]
                list(sl.render_all([(hp, pp)],
                                   size=(w, h), orientation=ori))
                self.style_done.emit(str(pp), "")
            except Exception as ex:
                self.style_done.emit("", str(ex))
            finally:
                sl._BRAND, sl._CFG = prev_brand, prev_cfg

        threading.Thread(target=work, daemon=True).start()

    def _on_style_done(self, path, err):
        self._style_busy = False
        if not path:
            self.style_status.setText(f"échec : {err}")
            return
        pm = QPixmap(path)
        if pm.isNull():
            self.style_status.setText("aperçu illisible")
            return
        self._style_pm = pm
        self._style_view_update()
        self.style_status.setText("")

    def _style_view_update(self):
        if self._style_pm:
            self.style_view.setPixmap(self._style_pm.scaled(
                self.style_view.size(), Qt.KeepAspectRatio,
                Qt.SmoothTransformation))

    # ——— identité visuelle ———

    def _font_check(self, *_):
        """Indique quelle famille de la pile saisie sera réellement
        utilisée (installées + fonts/ embarquées) — une famille absente
        replie sans signaler, l'aperçu semble ignorer le réglage."""
        import re
        raw = self.font_family.text().strip()
        if not raw:
            self.font_hint.setText("pile système par défaut")
            self.font_hint.setStyleSheet("")
            return
        names = [re.sub(r"^['\"]|['\"]$", "", n.strip())
                 for n in raw.split(",") if n.strip()]
        try:
            emb = {f.casefold() for f in _fonts()["families"]}
        except Exception:
            emb = set()
        generics = {"sans-serif", "serif", "monospace", "cursive",
                    "fantasy", "system-ui"}
        # résolution réelle via fontconfig (identique à Chromium)
        from PySide6.QtGui import QFont, QFontInfo
        def resolve(n):
            if n.casefold() in emb:
                return n  # fichier embarqué dans fonts/
            return QFontInfo(QFont(n)).family()
        hit = next((n for n in names
                    if n.casefold() not in generics
                    and resolve(n).casefold() == n.casefold()), None)
        if hit:
            self.font_hint.setText(f"✓ « {hit} » sera utilisée")
            self.font_hint.setStyleSheet("color:#8fbc8f")
            return
        gen = next((n for n in names if n.casefold() in generics), None)
        if gen:
            self.font_hint.setText(f"« {gen} » → {resolve(gen)}")
        else:
            self.font_hint.setText(
                f"« {names[0]} » introuvable — « {resolve(names[0])} » "
                "à l'aperçu (ou déposer le fichier dans fonts/)")
        self.font_hint.setStyleSheet("color:#c99483")

    def _style_soft_refresh(self):
        """Champ identité quitté → l'aperçu reflète la retouche (l'état
        courant des champs est utilisé, sans attendre « Enregistrer »)."""
        if self.style_auto.isChecked():
            self._style_timer.start()

    def _color_row(self, form, label, default):
        """Champ couleur #rrggbb + bouton pipette (QColorDialog)."""
        from PySide6.QtWidgets import QColorDialog
        from PySide6.QtGui import QColor
        w = QLineEdit(placeholderText=default)
        w.setFixedWidth(120)
        btn = QPushButton("…")
        btn.setProperty("ghost", True)
        btn.setFixedWidth(36)
        row = QHBoxLayout()
        row.addWidget(w)
        row.addWidget(btn)
        row.addStretch(1)

        def pick():
            c = QColorDialog.getColor(QColor(w.text() or default), self,
                                      label)
            if c.isValid():
                w.setText(c.name())
        btn.clicked.connect(pick)
        form.addRow(label, row)
        return w

    def _pick_logo(self):
        from PySide6.QtWidgets import QFileDialog
        f, _ = QFileDialog.getOpenFileName(
            self, "Logo de la structure", "",
            "Images (*.svg *.png *.jpg *.jpeg *.webp)")
        if f:
            self.logo_path.setText(f)

    def _preview_slide(self):
        """Aperçu réel : enregistre les réglages, rend une diapo de
        l'agenda (la plus représentative : image + specs) puis l'ouvre
        dans l'aperçu — itération couleurs/logo/fonte sans run."""
        if not self.oa_agenda.text().strip():
            self.preview_lbl.setText("renseignez d'abord l'agenda")
            return
        self._save()
        self.preview_lbl.setText("rendu…")

        def work():
            try:
                import oaslides.slide as sl
                sl._BRAND = sl._CFG = None  # relecture des réglages
                cfg = load_settings()
                from oaslides.oa import oa_list_events, filter_categories
                from oaslides.extract import parse_cats
                from oaslides.media import download_image, ensure_fonts
                from oaslides.settings import resolve_out_dir
                evs = filter_categories(
                    oa_list_events(cfg),
                    parse_cats(cfg.get("gen_categories", "")))
                if not evs:
                    raise RuntimeError("aucun événement sur l'agenda "
                                       "(filtre trop restrictif ?)")
                e = max(evs[:10], key=lambda x: (
                    bool(x.get("image")), len(x.get("specs", {}))))
                download_image(e)
                out = resolve_out_dir(cfg)
                out.mkdir(parents=True, exist_ok=True)
                hp, pp = out / "_preview.html", out / "_preview.png"
                hp.write_text(
                    sl.slide_html(e, 0, ensure_fonts()), "utf-8")
                size = sl.SIZES.get(cfg.get("resolution"), sl.DEFAULT_SIZE)
                list(sl.render_all([(hp, pp)], size=size))
                self.preview_done.emit(str(pp), "")
            except Exception as ex:
                self.preview_done.emit("", str(ex))

        threading.Thread(target=work, daemon=True).start()

    def _on_preview_done(self, path, err):
        if not path:
            self.preview_lbl.setText(f"échec : {err}")
            return
        self.preview_lbl.setText("")
        from .preview import preview_image
        preview_image(self, path, "Aperçu de diapo")


def _fonts():
    from oaslides.media import ensure_fonts
    return ensure_fonts()


def _sample_event():
    """Événement d'exemple autonome pour l'aperçu : visuel synthétique
    (dégradé + disques, rien de réseau), pastille, 4 lignes de specs,
    crédit — tous les éléments stylables sont visibles."""
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (900, 1100))
    px = img.load()
    for y in range(img.height):          # dégradé vertical
        t = y / img.height
        c = tuple(int(a + (b - a) * t)
                  for a, b in zip((38, 52, 96), (96, 56, 120)))
        for x in range(img.width):
            px[x, y] = c
    dr = ImageDraw.Draw(img)
    dr.ellipse([560, 80, 980, 500], outline=(255, 255, 255), width=14)
    dr.ellipse([-160, 640, 380, 1180], outline=(255, 214, 160), width=20)
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=82)
    return {
        "title": "Titre d'exemple volontairement long pour exercer "
                 "le nombre de lignes du titre",
        "desc": "Un extrait de description assez long pour juger du "
                "corps, des retours à la ligne et de l'équilibre du "
                "bloc texte — la phrase continue pour occuper "
                "plusieurs lignes afin que les réglages « lignes "
                "max » et « corps » aient un effet visible à "
                "l'aperçu, même réduits.",
        "desc_md": "", "tag": "Catégorie",
        "img_data": "data:image/jpeg;base64," + base64.b64encode(
            buf.getvalue()).decode(),
        "credit": "© crédit photo", "pinned": False,
        "specs": {"Date": "jeudi 12 mars à 20h00", "Durée": "1h30",
                  "Lieu": "Grande salle",
                  "Tarif": "10 €, gratuit -18 ans"},
    }

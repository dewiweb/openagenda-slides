"""Onglet « Style » — mixin de MainWindow.

Édition WYSIWYG des métriques des gabarits : chaque gabarit
assets/slide_template*.html expose ses réglages en variables CSS
`--var` dans son bloc :root (cf. assets/README.md). Ici elles sont
présentées en curseurs/champs numériques, par orientation, avec aperçu
réel re-rendu à chaque modification (débrayable).

Seules les valeurs différentes du défaut du gabarit sont enregistrées
(clé de réglage `style_overrides` : {orientation: {"--var": "val"}}) —
une évolution des défauts bénéficie aux paramètres non retouchés.
Aucun __init__ propre : les méthodes sont appelées sur la fenêtre.
"""

import base64
import io
import tempfile
import threading
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFormLayout, QFrame, QGroupBox, QHBoxLayout,
    QLabel, QPushButton, QScrollArea, QSpinBox, QVBoxLayout, QWidget,
)

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

        # ——— format + actions ———
        head = QGroupBox("Format")
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
        lay.addWidget(head)

        body = QHBoxLayout()
        body.setSpacing(14)

        # ——— paramètres ———
        params = QVBoxLayout()
        params.setSpacing(12)
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
        row = QHBoxLayout()
        self.style_status = QLabel("")
        row.addWidget(self.style_status, 1)
        ref = QPushButton("Rafraîchir")
        ref.setProperty("ghost", True)
        ref.clicked.connect(self._style_preview)
        row.addWidget(ref)
        pv_lay.addLayout(row)
        body.addWidget(pv, 1)
        lay.addLayout(body, 1)

        # délai court : une série de retouches ne déclenche qu'un rendu
        self._style_timer = QTimer(
            self, singleShot=True, interval=600,
            timeout=self._style_preview)

        self._style_reload_boxes()
        return outer

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
        """Remplit les champs : surcharge enregistrée sinon défaut."""
        self._style_loading = True
        try:
            ovr = self._style_ovr.get(self._style_orientation()) or {}
            defs = self._style_defaults()
            for var, sb in self._style_boxes.items():
                raw = ovr.get(var) or defs.get(var)
                sb.setValue(int(round(self._style_num(raw))))
        finally:
            self._style_loading = False

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
            if abs(sb.value() - default) > 1e-6:
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
        self.style_view.setPixmap(pm.scaled(
            self.style_view.size(), Qt.KeepAspectRatio,
            Qt.SmoothTransformation))
        self.style_status.setText("")


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
        "title": "Titre d'exemple — la diapo de démonstration",
        "desc": "Un extrait de description pour juger du corps, des "
                "retours à la ligne et de l'équilibre du bloc texte.",
        "desc_md": "", "tag": "Catégorie",
        "img_data": "data:image/jpeg;base64," + base64.b64encode(
            buf.getvalue()).decode(),
        "credit": "© crédit photo", "pinned": False,
        "specs": {"Date": "jeudi 12 mars à 20h00", "Durée": "1h30",
                  "Lieu": "Grande salle",
                  "Tarif": "10 €, gratuit -18 ans"},
    }

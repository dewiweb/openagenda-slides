"""Onglet « Général » — mixin de MainWindow (aucun __init__ propre :
les méthodes sont appelées sur la fenêtre, qui fournit les signaux,
_mark_dirty et les widgets partagés)."""

import threading

from PySide6.QtCore import Qt, QDate
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDateEdit, QFormLayout, QFrame,
    QGroupBox, QHBoxLayout, QLabel, QLineEdit,
    QPlainTextEdit, QPushButton, QScrollArea, QSpinBox, QStackedWidget,
    QVBoxLayout, QWidget,
)

from oaslides.settings import load_settings
from .style import _pw


class GeneralTabMixin:

    def _general_tab(self):
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

        sett = QGroupBox("Réglages")
        f = QFormLayout(sett)
        f.setLabelAlignment(Qt.AlignRight)
        self.interval = QSpinBox(minimum=0, maximum=720,
                                 suffix=" min (0 = off)")
        self.interval.setSingleStep(5)
        self.interval.setFixedWidth(160)
        self.sched_times = QLineEdit()
        self.sched_times.setPlaceholderText("ex. 06:00, 18:30")
        self.sched_times.setFixedWidth(190)
        # limitation des diapos : nombre, horizon en jours, ou date
        self.limit_mode = QComboBox()
        self.limit_mode.setFixedWidth(190)
        self.limit_mode.addItem("Premiers N événements", "count")
        self.limit_mode.addItem("Dans les N jours", "days")
        self.limit_mode.addItem("Jusqu'au …", "date")
        self._limit_stack = QStackedWidget()
        self.maxev = QSpinBox(minimum=0, maximum=999,
                              suffix=" (0 = tous)")
        self.maxev.setFixedWidth(160)
        self.limit_days = QSpinBox(minimum=1, maximum=365, value=14,
                                   suffix=" jours")
        self.limit_days.setFixedWidth(160)
        self.limit_date = QDateEdit(calendarPopup=True)
        self.limit_date.setFixedWidth(160)
        self.limit_date.setDate(
            QDate.currentDate().addDays(30))
        self.limit_date.setMinimumDate(QDate.currentDate())
        self._limit_stack.addWidget(self.maxev)
        self._limit_stack.addWidget(self.limit_days)
        self._limit_stack.addWidget(self.limit_date)
        self.limit_mode.currentIndexChanged.connect(
            self._limit_stack.setCurrentIndex)
        row = QHBoxLayout()
        row.addWidget(self.limit_mode)
        row.addWidget(self._limit_stack)
        row.addStretch(1)
        self.res = QComboBox()
        self.res.setFixedWidth(220)
        self.res.addItem("UHD 3840×2160", "uhd")
        self.res.addItem("HD 1920×1080", "hd")
        self.gen_ls = QCheckBox("Paysage — dans le dossier de sortie")
        self.gen_pt = QCheckBox("Portrait — sous-dossier portrait/")
        self.portrait_fmt = QComboBox()
        self.portrait_fmt.addItem("A4 — impression", "a4")
        self.portrait_fmt.addItem("Écran 9:16 — diffusion", "screen")
        self.portrait_fmt.setEnabled(False)
        self.gen_pt.toggled.connect(self.portrait_fmt.setEnabled)
        prow = QHBoxLayout()
        prow.addWidget(self.gen_pt)
        prow.addWidget(self.portrait_fmt)
        prow.addStretch(1)
        f.addRow("Rafraîchissement auto", self.interval)
        f.addRow("… et/ou à heures fixes", self.sched_times)
        f.addRow("Diapos générées", row)
        f.addRow("Résolution", self.res)
        f.addRow("Layouts générés", self.gen_ls)
        f.addRow("", prow)
        lay.addWidget(sett)

        catsbox = QGroupBox("Catégories générées")
        f = QFormLayout(catsbox)
        f.setLabelAlignment(Qt.AlignRight)
        self.gen_cats = QLineEdit()
        self.gen_cats.setPlaceholderText(
            "vide = tout l'agenda · sinon slugs/libellés séparés "
            "par des virgules : concert, exposition")
        f.addRow("Tags retenus", self.gen_cats)
        row = QHBoxLayout()
        ls = QPushButton("Lister les groupes de tags de l'agenda")
        ls.setProperty("ghost", True)
        ls.setToolTip("Interroge l'export public OpenAgenda et affiche "
                      "les groupes de tags (catégories, publics…) et "
                      "leurs valeurs — utile pour choisir les filtres")
        ls.clicked.connect(self._list_tag_groups)
        row.addWidget(ls)
        self.tags_lbl = QLabel()
        self.tags_lbl.setWordWrap(True)
        row.addWidget(self.tags_lbl, 1)
        f.addRow("", row)
        lay.addWidget(catsbox)

        sp = QGroupBox("Informations affichées (specs)")
        f = QFormLayout(sp)
        f.setLabelAlignment(Qt.AlignRight)
        # une ligne par spec : case « afficher » + champ de valeur
        # forcée (vide = valeur OpenAgenda). Date : toujours affichée.
        self._spec_rows = {}
        for key in ("Durée", "Lieu", "Tarif", "Public",
                    "Accessibilité"):
            cb = QCheckBox(key)
            cb.setChecked(True)
            ov = QLineEdit(placeholderText="valeur forcée (optionnel)")
            ov.setMinimumWidth(220)
            row = QHBoxLayout()
            row.addWidget(cb)
            row.addWidget(ov, 1)
            f.addRow(row)
            self._spec_rows[key] = (cb, ov)
        self.next_label = QLineEdit(
            placeholderText="Prochaine séance : ")
        self.next_label.setToolTip(
            "Préfixe de la spec Date pour les événements à plusieurs "
            "séances — vide = afficher la date seule")
        f.addRow("Préfixe récurrent", self.next_label)
        lay.addWidget(sp)

        sers = QGroupBox("Séries éditoriales — keyword OA = Libellé "
                         "[| logo.png] par ligne")
        f = QFormLayout(sers)
        self.series_map = QPlainTextEdit()
        self.series_map.setMaximumHeight(72)
        self.series_map.setPlaceholderText(
            "grandstemoins = Les grands témoins | logo-gt.png")
        f.addRow(self.series_map)
        row = QHBoxLayout()
        det = QPushButton("Détecter dans les mots-clés")
        det.setProperty("ghost", True)
        det.setToolTip("Scanne les mots-clés OpenAgenda de l'agenda, "
                       "puis ajoute les candidats au champ")
        det.clicked.connect(self._detect_series)
        row.addWidget(det)
        self.series_test = QLabel()
        row.addWidget(self.series_test, 1)
        f.addRow("", row)
        lay.addWidget(sers)

        oa = QGroupBox("Agenda OpenAgenda")
        f = QFormLayout(oa)
        f.setLabelAlignment(Qt.AlignRight)
        self.oa_agenda = QLineEdit(
            placeholderText="slug ou uid — ex. mon-agenda")
        self.oa_key = _pw("(optionnel — sans clé : export public)")
        self.tag_group = QLineEdit(
            placeholderText="vide = auto (groupe « categorie* »)")
        f.addRow("Agenda", self.oa_agenda)
        f.addRow("Clé API v2", self.oa_key)
        f.addRow("Groupe catégorie", self.tag_group)
        row = QHBoxLayout()
        t = QPushButton("Tester la connexion")
        t.setProperty("ghost", True)
        t.clicked.connect(lambda: self._test("oa"))
        row.addWidget(t)
        self.oa_test = QLabel("")
        row.addWidget(self.oa_test)
        row.addStretch(1)
        f.addRow(row)
        lay.addWidget(oa)

        ident = QGroupBox("Identité visuelle")
        f = QFormLayout(ident)
        f.setLabelAlignment(Qt.AlignRight)
        self.org_name = QLineEdit(
            placeholderText="nom affiché de la structure")
        self.program_url = QLineEdit(
            placeholderText="https://mon-site.fr/programme — vide = "
                            "page OpenAgenda de l'agenda")
        self.footer_text = QLineEdit(
            placeholderText="Tout le programme sur / Retrouvez-nous sur…")
        self.logo_path = QLineEdit(
            placeholderText="SVG ou PNG — filigrane, badge série")
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
            placeholderText="vide = pile système · sinon nom CSS ou "
                            "famille d'un fichier du dossier fonts/")
        f.addRow("Fonte", self.font_family)
        lay.addWidget(ident)

        appbox = QGroupBox("Application")
        f = QFormLayout(appbox)
        f.setLabelAlignment(Qt.AlignRight)
        self.close_to_tray = QCheckBox(
            "Réduire dans la zone de notification à la fermeture")
        self.close_to_tray.setToolTip(
            "Coché : fermer la fenêtre garde l'app active dans le tray "
            "(planificateur et notifications continuent).\n"
            "Décoché : fermer la fenêtre quitte l'application.")
        if not self._tray_ok:
            # désactivée mais conserve la valeur enregistrée : un save
            # sur une machine sans tray n'efface pas la préférence
            self.close_to_tray.setEnabled(False)
            self.close_to_tray.setText(
                "Réduire dans la zone de notification "
                "(indisponible sur ce système)")
        f.addRow("Fermeture", self.close_to_tray)
        self.start_min = QCheckBox(
            "Démarrer réduite dans la zone de notification")
        if not self._tray_ok:
            self.start_min.setEnabled(False)
            self.start_min.setText(
                "Démarrer réduite (zone de notification indisponible)")
        f.addRow("Démarrage", self.start_min)
        self.autostart_app = QCheckBox(
            "Lancer l'application à l'ouverture de session")
        self.autostart_app.setToolTip(
            "Indispensable sur un poste d'affichage : sans ça, un "
            "redémarrage (Windows Update, coupure) laisse l'écran vide.")
        f.addRow("Session", self.autostart_app)
        self.autostart_ss = QComboBox()
        self.autostart_ss.setFixedWidth(220)
        self.autostart_ss.addItem("Pas de diaporama", "none")
        self.autostart_ss.addItem("Diaporama paysage", "landscape")
        self.autostart_ss.addItem("Diaporama portrait", "portrait")
        f.addRow("Au démarrage", self.autostart_ss)
        row = QHBoxLayout()
        u = QPushButton("Vérifier les mises à jour")
        u.setProperty("ghost", True)
        u.clicked.connect(self._check_update)
        row.addWidget(u)
        self.update_lbl = QLabel()
        self.update_lbl.setOpenExternalLinks(True)
        row.addWidget(self.update_lbl, 1)
        from oaslides.version import VERSION
        f.addRow(f"Version {VERSION}", row)
        lay.addWidget(appbox)

        log = QGroupBox("Journal")
        v = QVBoxLayout(log)
        self.log = QPlainTextEdit(readOnly=True)
        self.log.setPlaceholderText(
            "Le journal de génération s'affichera ici.")
        self.log.setStyleSheet(
            "font-family:monospace;font-size:12.5px;color:#bfbbb8")
        v.addWidget(self.log)
        log.setMinimumHeight(180)
        lay.addWidget(log, 1)
        return outer

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

    def _list_tag_groups(self):
        """Affiche les groupes de tags (et leurs valeurs) de l'agenda
        configuré — aide au choix de « Groupe catégorie » et des
        filtres. Export public, sans clé."""
        self.tags_lbl.setText("interrogation de l'agenda…")
        s = self._collect() if hasattr(self, "_collect") else {}
        agenda = (s.get("oa_agenda") or self.oa_agenda.text()).strip()
        if not agenda:
            self.tags_lbl.setText("renseignez d'abord l'agenda")
            return

        def work():
            try:
                from oaslides.oa import list_tag_groups
                groups = list_tag_groups(agenda)
                txt = " · ".join(
                    f"{v['name']} [{slug}] : "
                    + ", ".join(l for _, l in v["tags"][:8])
                    for slug, v in groups.items()) or "aucun tagGroup"
            except Exception as e:
                txt = f"échec : {e}"
            self.series_done.emit([("__tags__", txt)])

        threading.Thread(target=work, daemon=True).start()

    def _detect_series(self):
        """Scanne les keywords OA de l'agenda en worker — ajoute les
        candidats manquants au champ, sans rien écraser."""
        agenda = self.oa_agenda.text().strip()
        if not agenda:
            self.series_test.setText("renseignez d'abord l'agenda")
            return
        self.series_test.setText("détection…")

        def work():
            try:
                from oaslides.oa import detect_series
                found = detect_series(agenda)
            except Exception as e:
                found = [("__erreur__", str(e))]
            self.series_done.emit(found)

        threading.Thread(target=work, daemon=True).start()

    def _on_series_done(self, found):
        if found and found[0][0] == "__tags__":
            self.tags_lbl.setText(found[0][1])
            return
        if found and found[0][0] == "__erreur__":
            self.series_test.setText(f"échec : {found[0][1]}")
            return
        existing = {l.split("=", 1)[0].strip() for l in
                    self.series_map.toPlainText().splitlines()
                    if "=" in l}
        added = [f"{k} = {v}" for k, v in found if k not in existing]
        if added:
            cur = self.series_map.toPlainText().rstrip()
            self.series_map.setPlainText(
                (cur + "\n" if cur else "") + "\n".join(added))
            self._mark_dirty()
        self.series_test.setText(
            f"{len(added)} série(s) ajoutée(s), "
            f"{len(found) - len(added)} déjà listée(s)")

    def _check_update(self):
        """Interroge l'API GitHub releases en worker — résultat livré
        par le signal update_done dans le thread GUI."""
        self.update_lbl.setText("recherche…")

        def work():
            try:
                from oaslides.net import get
                d = get("https://api.github.com/repos/dewiweb/"
                        "openagenda-slides/releases/latest").json()
                self.update_done.emit(d.get("tag_name") or "",
                                      d.get("html_url") or "")
            except Exception as e:
                self.update_done.emit("", str(e))

        threading.Thread(target=work, daemon=True).start()

    def _on_update_done(self, tag, url_or_err):
        if not tag:
            self.update_lbl.setText(f"échec : {url_or_err}")
            return
        from oaslides.version import VERSION, newer_than_current
        if newer_than_current(tag):
            self.update_lbl.setText(
                f'<a href="{url_or_err}" style="color:#c99483">'
                f"{tag} disponible — télécharger</a>")
        else:
            self.update_lbl.setText(f"à jour ({VERSION})")

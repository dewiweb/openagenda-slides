"""Onglet « Général » — mixin de MainWindow (aucun __init__ propre :
les méthodes sont appelées sur la fenêtre, qui fournit les signaux,
_mark_dirty et les widgets partagés)."""

import threading

from PySide6.QtCore import Qt, QDate
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDateEdit, QFormLayout, QFrame,
    QGridLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
    QPlainTextEdit, QPushButton, QScrollArea, QSpinBox, QStackedWidget,
    QVBoxLayout, QWidget,
)

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

        # l'agenda est la clé de voûte : premier groupe — sa saisie
        # déclenche la découverte des catégories plus bas
        oa = QGroupBox("Agenda OpenAgenda")
        f = QFormLayout(oa)
        f.setLabelAlignment(Qt.AlignRight)
        self.oa_agenda = QLineEdit(
            placeholderText="slug ou uid — ex. mon-agenda")
        # agenda renseigné → découverte automatique des catégories
        self.oa_agenda.editingFinished.connect(
            self._maybe_discover_cats)
        self.oa_key = _pw("(optionnel — sans clé : export public)")
        # combo éditable : slugs découverts en liste, saisie libre
        # conservée — l'utilisateur ne tape jamais un slug à la main
        self.tag_group = QComboBox(editable=True)
        self.tag_group.setFixedWidth(230)
        self.tag_group.lineEdit().setPlaceholderText(
            "vide = auto (groupe « categorie* »)")
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
        row = QHBoxLayout()
        ls = QPushButton("Découvrir les catégories de l'agenda")
        ls.setProperty("ghost", True)
        ls.setToolTip("Interroge l'export public OpenAgenda et liste "
                      "les groupes de tags (catégories, publics…) — "
                      "décochez celles à exclure des générations")
        ls.clicked.connect(self._list_tag_groups)
        row.addWidget(ls)
        self.tags_lbl = QLabel()
        self.tags_lbl.setWordWrap(True)
        row.addWidget(self.tags_lbl, 1)
        f.addRow("", row)
        # cases découvertes, groupées par groupe de tags — remplies à
        # la découverte (auto à la saisie de l'agenda / au test)
        self._cat_checks = []          # [(slug, libellé, QCheckBox)]
        self._cats_loading = False
        self._cats_agenda = ""
        self.cats_panel = QWidget()
        self.cats_panel.setObjectName("catsPanel")
        self.cats_lay = QVBoxLayout(self.cats_panel)
        self.cats_lay.setContentsMargins(0, 0, 0, 0)
        self.cats_lay.setSpacing(4)
        self.cats_panel.hide()
        f.addRow(self.cats_panel)
        self.gen_cats = QLineEdit()
        self.gen_cats.setPlaceholderText(
            "vide = tout l'agenda · alimenté par les cases, édition "
            "avancée possible (slugs/libellés, virgules)")
        self.gen_cats.setToolTip(
            "Sélection envoyée à la génération : slugs des cases "
            "cochées + éventuels termes hors taxonomie de l'agenda")
        f.addRow("Tags retenus", self.gen_cats)
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
        self.series_map.setToolTip(
            "Une ligne par série : mot-clé OpenAgenda = Libellé "
            "affiché | fichier logo optionnel.\n"
            "Logo de série : PNG ou SVG à fond transparent, plutôt "
            "carré — il remplace le rond de série dans la diapo du "
            "jour (affiché à ~88 % du rond, jamais rogné).")
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

    def _maybe_discover_cats(self):
        """Lance la découverte si l'agenda saisi diffère du dernier
        découvert — appelé à la fin de l'édition du champ agenda."""
        agenda = self.oa_agenda.text().strip()
        if agenda and agenda != self._cats_agenda:
            self._list_tag_groups()

    def _list_tag_groups(self):
        """Découvre les groupes de tags de l'agenda (export public,
        sans clé) et peuple les cases à cocher des catégories —
        une section par groupe, état initial depuis « Tags retenus »."""
        agenda = self.oa_agenda.text().strip()
        if not agenda:
            self.tags_lbl.setText("renseignez d'abord l'agenda")
            return
        # changement d'agenda : catégories, séries et groupe
        # catégorie sont propres à l'ancien agenda — réinitialisés
        # dans _populate_cats, c.-à-d. seulement si la découverte
        # répond (un échec ne détruit pas les réglages existants).
        # _cats_agenda n'est mis à jour qu'au succès, sinon une
        # redécouverte du même agenda ne remarquerait pas le changement.
        self._cats_pending_agenda = agenda
        self._cats_pending_reset = bool(
            self._cats_agenda and agenda != self._cats_agenda)
        self.tags_lbl.setText("découverte des catégories…")
        s = self._collect() if hasattr(self, "_collect") else {}
        key = (s.get("oa_api_key") or "").strip()

        def work():
            try:
                from oaslides.oa import list_tag_groups
                groups = list_tag_groups(agenda, key=key)
                self.series_done.emit([("__cats__", groups)])
            except Exception as e:
                self.series_done.emit([("__tags__", f"échec : {e}")])

        threading.Thread(target=work, daemon=True).start()

    def _populate_cats(self, groups):
        """Remplit le panneau de cases depuis {slug_groupe: {name,
        tags: [(slug, libellé)]}} — tout coché si « Tags retenus »
        est vide, sinon seules les valeurs listées le sont."""
        from oaslides.extract import parse_cats
        from oaslides.oa import _norm
        if getattr(self, "_cats_pending_reset", False):
            self._cats_reset = True
            self.gen_cats.clear()
            self.series_map.clear()
            self.tag_group.setEditText("")
        self._cats_pending_reset = False
        self._cats_agenda = getattr(
            self, "_cats_pending_agenda", self._cats_agenda)
        while self.cats_lay.count():
            it = self.cats_lay.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
            elif it.layout():
                while it.layout().count():
                    sub = it.layout().takeAt(0)
                    if sub.widget():
                        sub.widget().deleteLater()
        self._cat_checks = []
        if not groups:
            self.tags_lbl.setText(
                "aucun groupe de tags — cet agenda n'a pas de "
                "catégories (filtrage manuel possible ci-dessous)")
            self.cats_panel.hide()
            return
        terms = {_norm(t) for t in parse_cats(self.gen_cats.text())}
        self._cats_loading = True
        try:
            for gslug, g in groups.items():
                head = QLabel(f"{g['name']}  [{gslug}]")
                head.setStyleSheet("color:#8f8c8a;font-size:12px")
                self.cats_lay.addWidget(head)
                grid = QGridLayout()
                grid.setContentsMargins(12, 0, 0, 0)
                grid.setHorizontalSpacing(16)
                for i, (slug, label) in enumerate(g["tags"]):
                    cb = QCheckBox(label or slug)
                    cb.setChecked(
                        not terms
                        or _norm(slug) in terms
                        or _norm(label) in terms)
                    cb.toggled.connect(self._sync_gen_cats)
                    grid.addWidget(cb, i // 3, i % 3)
                    self._cat_checks.append((slug, label, cb))
                self.cats_lay.addLayout(grid)
        finally:
            self._cats_loading = False
        n = sum(len(g["tags"]) for g in groups.values())
        note = " — filtres de l'ancien agenda réinitialisés" \
            if getattr(self, "_cats_reset", False) else ""
        self._cats_reset = False
        self.tags_lbl.setText(
            f"{len(groups)} groupe(s), {n} tag(s) — "
            "décochez ce qui ne doit pas être généré" + note)
        self.cats_panel.show()
        # la combo « Groupe catégorie » propose les slugs découverts
        # (nom du groupe en infobulle) — saisie libre préservée
        cur = self.tag_group.currentText()
        self.tag_group.blockSignals(True)
        self.tag_group.clear()
        for gslug, g in groups.items():
            self.tag_group.addItem(gslug)
            self.tag_group.setItemData(
                self.tag_group.count() - 1, g["name"], Qt.ToolTipRole)
        self.tag_group.setEditText(cur)
        self.tag_group.blockSignals(False)

    def _sync_gen_cats(self, *_):
        """Cases → champ « Tags retenus » : slugs cochés (tout coché =
        vide = tout l'agenda) + termes saisis hors taxonomie connue,
        préservés tels quels."""
        if self._cats_loading or not self._cat_checks:
            return
        from oaslides.extract import parse_cats
        from oaslides.oa import _norm
        known = {_norm(s) for s, _, _ in self._cat_checks} | \
            {_norm(l) for _, l, _ in self._cat_checks}
        extras = [t for t in parse_cats(self.gen_cats.text())
                  if _norm(t) not in known]
        checked = [s for s, _, cb in self._cat_checks if cb.isChecked()]
        txt = "" if len(checked) == len(self._cat_checks) \
            and not extras else ", ".join(checked + extras)
        if txt != self.gen_cats.text().strip():
            self.gen_cats.setText(txt)  # textChanged → _mark_dirty

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
        if found and found[0][0] == "__cats__":
            self._populate_cats(found[0][1])
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

    def _check_update(self, quiet=False):
        """Interroge l'API GitHub releases en worker — résultat livré
        par le signal update_done dans le thread GUI. `quiet` (check
        automatique au démarrage) : « recherche… » et « à jour » ne
        polluent pas le libellé — seules nouveauté et rien ne passent."""
        self._upd_quiet = quiet
        if not quiet:
            self.update_lbl.setText("recherche…")

        def work():
            try:
                from oaslides.net import get
                from oaslides.version import VERSION
                # releases/latest ignore les préreleases — or les betas
                # sont marquées prerelease. On prend donc la liste :
                # version courante beta → plus récente, beta incluse ;
                # stable → uniquement les stables (pas de beta proposée)
                d = get("https://api.github.com/repos/dewiweb/"
                        "openagenda-slides/releases?per_page=10").json()
                beta = "-" in VERSION
                tag = url = ""
                for r in (d if isinstance(d, list) else []):
                    if r.get("draft") or (r.get("prerelease")
                                          and not beta):
                        continue
                    tag, url = (r.get("tag_name") or "",
                                r.get("html_url") or "")
                    break
                self.update_done.emit(tag, url)
            except Exception as e:
                self.update_done.emit("", str(e))

        threading.Thread(target=work, daemon=True).start()

    def _on_update_done(self, tag, url_or_err):
        quiet = getattr(self, "_upd_quiet", False)
        if not tag:
            if not quiet:
                self.update_lbl.setText(f"échec : {url_or_err}")
            return
        from oaslides.version import VERSION, newer_than_current
        if newer_than_current(tag):
            self.update_lbl.setText(
                f'<a href="{url_or_err}" style="color:#c99483">'
                f"{tag} disponible — télécharger</a>")
            if quiet:
                self.statusBar().showMessage(
                    f"Nouvelle version {tag} disponible — "
                    "voir l'onglet Général", 8000)
        elif not quiet:
            self.update_lbl.setText(f"à jour ({VERSION})")

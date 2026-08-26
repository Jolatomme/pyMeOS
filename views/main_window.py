"""
views/main_window.py
====================
Main application window (equivalent to meos.cpp WndProc + tab system).

Hosts all tab panels in a QTabWidget, owns the CompetitionController,
connects the SI reader, and provides menu / toolbar / status bar.
"""
from __future__ import annotations

import sys
from typing import Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QMainWindow, QTabWidget, QStatusBar, QMenuBar,
    QMenu, QFileDialog, QMessageBox, QInputDialog,
    QApplication, QToolBar, QLabel,
)
from PySide6.QtGui import QAction, QIcon, QKeySequence

from controllers.competition import CompetitionController
from hardware.si_reader import SIReaderManager
from utils.icon_utils import get_icon
from views.tabs.tab_competition import TabCompetition
from views.tabs.tab_runner      import TabRunner
from views.tabs.tab_team        import TabTeam
from views.tabs.tab_class       import TabClass
from views.tabs.tab_course      import TabCourse
from views.tabs.tab_control     import TabControl
from views.tabs.tab_club        import TabClub
from views.tabs.tab_si          import TabSI
from views.tabs.tab_results     import TabResults
from views.tabs.tab_speaker     import TabSpeaker
from views.tabs.tab_auto        import TabAuto

APP_TITLE   = "PyMeOS  Orienteering Software"
APP_VERSION = "0.0.1"

# File-dialog filter strings used in multiple places
_OPEN_FILTER = "MeOS XML (*.meosxml *.mexml *.xml);;All Files (*)"
_SAVE_FILTER = "MeOS XML (*.mexml);;All Files (*)"


class MainWindow(QMainWindow):
    def __init__(self, db_url: str = "sqlite:///pymeos.db") -> None:
        super().__init__()

        #  Controller & hardware 
        self._ctrl     = CompetitionController(parent=self)
        self._si_mgr   = SIReaderManager(parent=self)

        # Connect SI reader  controller
        self._si_mgr.card_received.connect(self._on_card_received)
        self._si_mgr.error.connect(self._on_si_error)

        # Connect controller messages  status bar
        self._ctrl.status_message.connect(self._show_status)

        #  Window chrome 
        self.setWindowTitle(APP_TITLE)
        self.resize(1200, 800)

        self._build_menu()
        self._build_toolbar()
        self._build_tabs()
        self._build_statusbar()

        #  Auto-save timer (every 5 min) 
        self._autosave_timer = QTimer(self)
        self._autosave_timer.timeout.connect(self._autosave)
        self._autosave_timer.start(5 * 60 * 1000)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_menu(self):
        mb = self.menuBar()

        # File menu
        file_menu = mb.addMenu("&File")
        act_new    = QAction(get_icon("general/new"), "&New Competition", self,
                             shortcut=QKeySequence.New,
                             triggered=self._action_new)
        act_open   = QAction(get_icon("general/open"), "&Open...", self,
                             shortcut=QKeySequence.Open,
                             triggered=self._action_open)
        act_save   = QAction(get_icon("general/save"), "&Save", self,
                             shortcut=QKeySequence.Save,
                             triggered=self._action_save)
        act_saveas = QAction(get_icon("general/save_as"), "Save &As...", self,
                             triggered=self._action_save_as)
        act_import_iof = QAction("Import IOF XML 3.0...", self,
                                 triggered=self._action_import_iof)
        act_export_iof = QAction("Export IOF XML 3.0...", self,
                                 triggered=self._action_export_iof)
        act_quit   = QAction(get_icon("general/quit"), "&Quit", self,
                             shortcut=QKeySequence.Quit,
                             triggered=self.close)

        file_menu.addAction(act_new)
        file_menu.addAction(act_open)
        file_menu.addAction(act_save)
        file_menu.addAction(act_saveas)
        file_menu.addSeparator()
        file_menu.addAction(act_import_iof)
        file_menu.addAction(act_export_iof)
        file_menu.addSeparator()
        file_menu.addAction(act_quit)

        # Competition menu
        comp_menu = mb.addMenu("&Competition")
        comp_menu.addAction(QAction(
            get_icon("actions/calculate"), "Recalculate All Results", self,
            triggered=self._action_recalc))
        comp_menu.addAction(QAction(
            get_icon("actions/draw"), "Draw Start Times...", self,
            triggered=self._action_draw))

        # SI menu
        si_menu = mb.addMenu("&SI Reader")
        si_menu.addAction(QAction(
            get_icon("si/usb"), "Open Port...", self, triggered=self._action_open_port))
        si_menu.addAction(QAction(
            get_icon("si/usb_off"), "Close All Ports", self, triggered=self._si_mgr.close_all))
        si_menu.addAction(QAction(
            get_icon("si/test_card"), "Test Mode (simulation)", self, triggered=self._action_test_si))

        # Help menu
        help_menu = mb.addMenu("&Help")
        help_menu.addAction(QAction(
            get_icon("general/about"), "About...", self, triggered=self._action_about))

    def _build_toolbar(self):
        tb = self.addToolBar("Main")
        tb.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        tb.addAction(QAction(get_icon("general/new"), "New",  self, triggered=self._action_new))
        tb.addAction(QAction(get_icon("general/open"), "Open", self, triggered=self._action_open))
        tb.addAction(QAction(get_icon("general/save"), "Save", self, triggered=self._action_save))
        tb.addSeparator()
        tb.addAction(QAction(get_icon("actions/calculate"), "Recalculate", self,
                             triggered=self._action_recalc))

    def _build_tabs(self):
        self._tabs = QTabWidget()
        self._tabs.setTabPosition(QTabWidget.North)
        self.setCentralWidget(self._tabs)

        ctrl = self._ctrl

        def add(widget, label: str, icon_name: str = ""):
            if icon_name:
                self._tabs.addTab(widget, get_icon(icon_name), label)
            else:
                self._tabs.addTab(widget, label)
            return widget

        self._tab_competition = add(TabCompetition(ctrl), "Competition", "competition/runner")
        self._tab_runner      = add(TabRunner(ctrl),      "Runners", "competition/runner")
        self._tab_team        = add(TabTeam(ctrl),        "Teams", "competition/team")
        self._tab_class       = add(TabClass(ctrl),       "Classes", "competition/class")
        self._tab_course      = add(TabCourse(ctrl),      "Courses", "competition/course")
        self._tab_control     = add(TabControl(ctrl),     "Controls", "competition/control")
        self._tab_club        = add(TabClub(ctrl),        "Clubs", "competition/club")
        self._tab_si          = add(TabSI(ctrl),          "SI Cards", "si/card")
        self._tab_results     = add(TabResults(ctrl),     "Results", "competition/results")
        self._tab_speaker     = add(TabSpeaker(ctrl),     "Speaker", "competition/speaker")
        self._tab_auto        = add(TabAuto(ctrl),        "Automation", "general/settings")

        # Refresh active tab on switch
        self._tabs.currentChanged.connect(self._on_tab_changed)

    def _build_statusbar(self):
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._lbl_status = QLabel("Ready")
        self._lbl_si     = QLabel("SI: ")
        self._status_bar.addWidget(self._lbl_status, 1)
        self._status_bar.addPermanentWidget(self._lbl_si)

    # ------------------------------------------------------------------
    # Tab switching
    # ------------------------------------------------------------------

    def _on_tab_changed(self, index: int):
        widget = self._tabs.widget(index)
        if hasattr(widget, "load_page"):
            widget.load_page()

    # ------------------------------------------------------------------
    # File menu actions
    # ------------------------------------------------------------------

    def _action_new(self):
        name, ok = QInputDialog.getText(
            self, "New Competition", "Competition name:")
        if ok and name:
            self._ctrl.new_event(name)
            self._refresh_all_tabs()

    def _action_open(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Competition",
            filter=_OPEN_FILTER)
        if path:
            ok = self._ctrl.open_event_from_xml(path)
            if ok:
                self._refresh_all_tabs()
            else:
                QMessageBox.critical(self, "Error",
                                     "Failed to open competition file.")

    def _action_save(self):
        if self._ctrl.event.current_file:
            self._ctrl.save_event_to_xml(self._ctrl.event.current_file)
        else:
            self._action_save_as()

    def _action_save_as(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Competition",
            filter=_SAVE_FILTER)
        if path:
            if not path.endswith((".mexml", ".meosxml")):
                path += ".mexml"
            self._ctrl.event.current_file = path
            self._ctrl.save_event_to_xml(path)

    def _action_import_iof(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Import IOF XML 3.0",
            filter="IOF XML (*.xml);;All Files (*)")
        if not path:
            return
        from formats.iof30 import import_iof30
        try:
            import_iof30(path, self._ctrl.event)
            self._refresh_all_tabs()
            self._show_status("IOF import complete.")
        except Exception as e:
            QMessageBox.critical(self, "Import Error", str(e))

    def _action_export_iof(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export IOF XML 3.0",
            filter="IOF XML (*.xml);;All Files (*)")
        if not path:
            return
        from formats.iof30 import export_result_list
        try:
            export_result_list(self._ctrl.event, path)
            self._show_status(f"Exported to {path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", str(e))

    # ------------------------------------------------------------------
    # Competition menu actions
    # ------------------------------------------------------------------

    def _action_recalc(self):
        self._ctrl.recalculate_all_results()

    def _action_draw(self):
        # Simplified: draw starts for first class
        classes = [c for c in self._ctrl.event.classes.values() if not c.removed]
        if not classes:
            QMessageBox.information(self, "Draw", "No classes defined.")
            return
        
        class_id = classes[0].id
        first_start = 0  # 00:00:00 in internal units
        interval = 600   # 1 minute in internal units (0.1s units)
        self._ctrl.draw_starts(class_id, first_start, interval, scramble=True)

    # ------------------------------------------------------------------
    # SI menu actions
    # ------------------------------------------------------------------

    def _action_open_port(self):
        # Handled by TabSI
        pass

    def _action_test_si(self):
        self._si_mgr.open_port("TEST", test_mode=True)
        self._show_status("Test mode active (simulation).")

    # ------------------------------------------------------------------
    # Help menu actions
    # ------------------------------------------------------------------

    def _action_about(self):
        QMessageBox.about(
            self, "About PyMeOS",
            f"<h2>{APP_TITLE}</h2>\n"
            f"<p>Version {APP_VERSION}</p>\n"
            "<p>A cross-platform orienteering event management system.</p>\n"
            "<p>Python port of MeOS by Melin Software HB.</p>\n"
            "<p><a href='https://github.com/Jolatomme/pyMeOS'>GitHub</a></p>"
        )
    # ------------------------------------------------------------------
    # SI card handling
    # ------------------------------------------------------------------

    def _on_card_received(self, ev):
        self._ctrl.on_card_read(ev)
        self._lbl_si.setText(f"SI: Card {ev.card.card_number} read")

    def _on_si_error(self, port: str, message: str):
        self._show_status(f"SI Error [{port}]: {message}")

    # ------------------------------------------------------------------
    # Status bar
    # ------------------------------------------------------------------

    def _show_status(self, msg: str):
        self._lbl_status.setText(msg)

    # ------------------------------------------------------------------
    # Refresh
    # ------------------------------------------------------------------

    def _refresh_all_tabs(self):
        for i in range(self._tabs.count()):
            widget = self._tabs.widget(i)
            if hasattr(widget, "load_page"):
                widget.load_page()

    def _autosave(self):
        if self._ctrl.event.current_file:
            self._ctrl.save_event_to_xml(self._ctrl.event.current_file)

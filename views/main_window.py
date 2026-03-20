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

APP_TITLE   = "PyMeOS – Orienteering Software"
APP_VERSION = "0.0.1"

# File-dialog filter strings used in multiple places
_OPEN_FILTER = "MeOS XML (*.meosxml *.mexml *.xml);;All Files (*)"
_SAVE_FILTER = "MeOS XML (*.mexml);;All Files (*)"


class MainWindow(QMainWindow):
    def __init__(self, db_url: str = "sqlite:///pymeos.db") -> None:
        super().__init__()

        # ── Controller & hardware ──────────────────────────────────────
        self._ctrl     = CompetitionController(parent=self)
        self._si_mgr   = SIReaderManager(parent=self)

        # Connect SI reader → controller
        self._si_mgr.card_received.connect(self._on_card_received)
        self._si_mgr.error.connect(self._on_si_error)

        # Connect controller messages → status bar
        self._ctrl.status_message.connect(self._show_status)

        # ── Window chrome ──────────────────────────────────────────────
        self.setWindowTitle(APP_TITLE)
        self.resize(1200, 800)

        self._build_menu()
        self._build_toolbar()
        self._build_tabs()
        self._build_statusbar()

        # ── Auto-save timer (every 5 min) ─────────────────────────────
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
        act_new    = QAction("&New Competition", self,
                             shortcut=QKeySequence.New,
                             triggered=self._action_new)
        act_open   = QAction("&Open…", self,
                             shortcut=QKeySequence.Open,
                             triggered=self._action_open)
        act_save   = QAction("&Save", self,
                             shortcut=QKeySequence.Save,
                             triggered=self._action_save)
        act_saveas = QAction("Save &As…", self,
                             triggered=self._action_save_as)
        act_import_iof = QAction("Import IOF XML 3.0…", self,
                                 triggered=self._action_import_iof)
        act_export_iof = QAction("Export IOF XML 3.0…", self,
                                 triggered=self._action_export_iof)
        act_quit   = QAction("&Quit", self,
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
            "Recalculate All Results", self,
            triggered=self._action_recalc))
        comp_menu.addAction(QAction(
            "Draw Start Times…", self,
            triggered=self._action_draw))

        # SI menu
        si_menu = mb.addMenu("&SI Reader")
        si_menu.addAction(QAction(
            "Open Port…", self, triggered=self._action_open_port))
        si_menu.addAction(QAction(
            "Close All Ports", self, triggered=self._si_mgr.close_all))
        si_menu.addAction(QAction(
            "Test Mode (simulation)", self, triggered=self._action_test_si))

        # Help menu
        help_menu = mb.addMenu("&Help")
        help_menu.addAction(QAction(
            "About…", self, triggered=self._action_about))

    def _build_toolbar(self):
        tb = self.addToolBar("Main")
        tb.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        tb.addAction(QAction("New",  self, triggered=self._action_new))
        tb.addAction(QAction("Open", self, triggered=self._action_open))
        tb.addAction(QAction("Save", self, triggered=self._action_save))
        tb.addSeparator()
        tb.addAction(QAction("Recalculate", self,
                             triggered=self._action_recalc))

    def _build_tabs(self):
        self._tabs = QTabWidget()
        self._tabs.setTabPosition(QTabWidget.North)
        self.setCentralWidget(self._tabs)

        ctrl = self._ctrl

        def add(widget, label: str):
            self._tabs.addTab(widget, label)
            return widget

        self._tab_competition = add(TabCompetition(ctrl), "Competition")
        self._tab_runner      = add(TabRunner(ctrl),      "Runners")
        self._tab_team        = add(TabTeam(ctrl),        "Teams")
        self._tab_class       = add(TabClass(ctrl),       "Classes")
        self._tab_course      = add(TabCourse(ctrl),      "Courses")
        self._tab_control     = add(TabControl(ctrl),     "Controls")
        self._tab_club        = add(TabClub(ctrl),        "Clubs")
        self._tab_si          = add(TabSI(ctrl),          "SI Cards")
        self._tab_results     = add(TabResults(ctrl),     "Results")
        self._tab_speaker     = add(TabSpeaker(ctrl),     "Speaker")
        self._tab_auto        = add(TabAuto(ctrl),        "Automation")

        # Refresh active tab on switch
        self._tabs.currentChanged.connect(self._on_tab_changed)

    def _build_statusbar(self):
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._lbl_status = QLabel("Ready")
        self._lbl_si     = QLabel("SI: –")
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
        self._show_status("Results recalculated.")
        current = self._tabs.currentWidget()
        if isinstance(current, TabResults):
            current.load_page()

    def _action_draw(self):
        """Simple draw dialog – full implementation in TabClass."""
        self._tabs.setCurrentWidget(self._tab_class)

    # ------------------------------------------------------------------
    # SI reader actions
    # ------------------------------------------------------------------

    def _action_open_port(self):
        available = SIReaderManager.list_serial_ports()
        choices   = available + ["TEST"]
        if not choices:
            QMessageBox.information(self, "No Ports",
                                    "No serial ports found.")
            return
        port, ok = QInputDialog.getItem(
            self, "Open SI Port", "Select port:", choices, 0, False)
        if ok and port:
            test_mode = (port == "TEST")
            if self._si_mgr.open_port(port, test_mode=test_mode):
                self._lbl_si.setText(f"SI: {port}")
                self._show_status(f"SI port {port} opened.")
            else:
                QMessageBox.warning(self, "Port Error",
                                    f"Could not open {port}.")

    def _action_test_si(self):
        self._si_mgr.open_port("TEST", test_mode=True)
        self._lbl_si.setText("SI: TEST")
        self._show_status("SI test mode active.")

    def _on_card_received(self, si_card):
        """Route incoming SI card to the controller."""
        from hardware.si_reader import SICardReadEvent
        port = (self._si_mgr.open_ports[0]
                if self._si_mgr.open_ports else "")
        self._ctrl.on_card_read(SICardReadEvent(card=si_card, port=port))
        if isinstance(self._tabs.currentWidget(), TabSI):
            self._tabs.currentWidget().load_page()

    def _on_si_error(self, port: str, msg: str):
        self._show_status(f"SI error on {port}: {msg}")

    # ------------------------------------------------------------------
    # Help
    # ------------------------------------------------------------------

    def _action_about(self):
        QMessageBox.about(
            self, f"About {APP_TITLE}",
            f"<h2>PyMeOS {APP_VERSION}</h2>"
            "<p>Cross-platform orienteering event management software.</p>"
            "<p>Python/PySide6 port of MeOS (Melin Software HB).</p>"
            "<p>Licensed under GPL v3.</p>",
        )

    # ------------------------------------------------------------------
    # Housekeeping
    # ------------------------------------------------------------------

    def _show_status(self, msg: str):
        self._lbl_status.setText(msg)
        self._status_bar.showMessage(msg, 5000)

    def _autosave(self):
        if self._ctrl.event and self._ctrl.event.current_file:
            self._ctrl.save_event_to_xml(self._ctrl.event.current_file)

    def _refresh_all_tabs(self):
        for i in range(self._tabs.count()):
            w = self._tabs.widget(i)
            if hasattr(w, "clear_competition_data"):
                w.clear_competition_data()
        w = self._tabs.currentWidget()
        if hasattr(w, "load_page"):
            w.load_page()

    def closeEvent(self, event):
        ev       = self._ctrl.event
        has_file = bool(ev and ev.current_file)
        has_data = bool(ev and ev.data_revision > 0)

        if has_file and has_data:
            reply = QMessageBox.question(
                self, "Quit",
                "Save before quitting?",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
            )
            if reply == QMessageBox.Cancel:
                event.ignore()
                return
            if reply == QMessageBox.Yes:
                self._action_save()

        self._si_mgr.close_all()
        event.accept()

    def recalculate_all_results(self):
        """Public API used by TabAuto etc."""
        self._action_recalc()

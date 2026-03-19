"""Smoke tests for views/main_window.py and all tab panels."""
import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


@pytest.fixture
def window(qtbot):
    from persistence import init_db
    init_db("sqlite:///:memory:")
    from views.main_window import MainWindow
    w = MainWindow(db_url="sqlite:///:memory:")
    qtbot.addWidget(w)
    w.show()
    return w


class TestMainWindowSmoke:
    def test_window_shows(self, window, qtbot):
        assert window.isVisible()

    def test_has_tabs(self, window):
        assert window._tabs.count() >= 8

    def test_tab_labels(self, window):
        labels = [window._tabs.tabText(i) for i in range(window._tabs.count())]
        for expected in ("Competition", "Runners", "Classes", "Courses",
                         "Controls", "SI Cards", "Results"):
            assert any(expected in lbl for lbl in labels), \
                f"Tab '{expected}' not found in {labels}"


class TestTabNavigation:
    def test_switch_to_runner_tab(self, window, qtbot):
        window._tabs.setCurrentWidget(window._tab_runner)
        qtbot.wait(100)
        assert window._tabs.currentWidget() is window._tab_runner

    def test_switch_to_results_tab(self, window, qtbot):
        window._tabs.setCurrentWidget(window._tab_results)
        qtbot.wait(100)
        assert window._tabs.currentWidget() is window._tab_results

    def test_all_tabs_load_without_crash(self, window, qtbot):
        for i in range(window._tabs.count()):
            window._tabs.setCurrentIndex(i)
            qtbot.wait(50)   # allow paint events


class TestNewEvent:
    def test_new_event_via_controller(self, window, qtbot):
        window._ctrl.new_event("Smoke Test Event")
        qtbot.wait(100)
        assert window._ctrl.event.name == "Smoke Test Event"

    def test_runner_tab_after_new_event(self, window, qtbot):
        window._ctrl.new_event("E")
        window._tabs.setCurrentWidget(window._tab_runner)
        window._tab_runner.load_page()
        qtbot.wait(100)

    def test_add_runner_appears_in_table(self, window, qtbot):
        window._ctrl.new_event("E")
        window._ctrl.add_runner("Alice", "Smith", class_name="M21")
        window._tabs.setCurrentWidget(window._tab_runner)
        window._tab_runner.load_page()
        qtbot.wait(100)
        # Table should have at least 1 row
        assert window._tab_runner._model.rowCount() >= 1


class TestStatusBar:
    def test_status_updates_on_new_event(self, window, qtbot):
        received = []
        window._ctrl.status_message.connect(received.append)
        window._ctrl.new_event("Status Test")
        qtbot.wait(100)
        assert any("Status Test" in m for m in received)


class TestSIIntegration:
    def test_open_test_port(self, window, qtbot):
        mgr = window._si_mgr
        ok  = mgr.open_port("TEST", test_mode=True)
        assert ok
        assert "TEST" in mgr.open_ports
        mgr.close_all()

    def test_card_processed_signal(self, window, qtbot):
        from models.card import SICard
        from models.punch import SIPunch
        from hardware.si_reader import SICardReadEvent
        from utils.time_utils import encode

        window._ctrl.new_event("E")
        runner = window._ctrl.add_runner("Bob", "B", card_number=777777)

        si = SICard()
        si.card_number  = 777777
        si.start_punch  = SIPunch(code=1, time=encode(3600))
        si.finish_punch = SIPunch(code=2, time=encode(3600 + 300))

        received = []
        window._ctrl.card_processed.connect(lambda cid: received.append(cid))

        ev = SICardReadEvent(card=si, port="TEST")
        window._ctrl.on_card_read(ev)
        qtbot.wait(200)
        assert len(received) == 1

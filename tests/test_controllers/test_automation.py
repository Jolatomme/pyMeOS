"""Tests for controllers/automation.py"""
import pytest
import sys
import time
import threading
import logging
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from models import Event
from controllers.automation import (
    AutomationController, AutoTaskConfig, TaskType, TaskStatus
)


@pytest.fixture
def event():
    ev = Event()
    ev.name = "Test Event"
    return ev


@pytest.fixture
def controller(event):
    ctrl = AutomationController(event)
    yield ctrl
    ctrl.stop()


class TestAutoTaskConfig:
    def test_default_config(self):
        cfg = AutoTaskConfig(task_type=TaskType.Backup)
        assert cfg.task_type == TaskType.Backup
        assert cfg.interval_seconds == 60
        assert cfg.enabled is True
        assert cfg.output_path == ""

    def test_custom_config(self):
        cfg = AutoTaskConfig(
            task_type=TaskType.LiveResults,
            interval_seconds=300,
            enabled=False,
            upload_url="http://example.com",
            upload_user="user",
            upload_password="pass"
        )
        assert cfg.task_type == TaskType.LiveResults
        assert cfg.interval_seconds == 300
        assert cfg.enabled is False
        assert cfg.upload_url == "http://example.com"
        assert cfg.upload_user == "user"


class TestTaskStatus:
    def test_default_status(self):
        st = TaskStatus(TaskType.Backup)
        assert st.task_type == TaskType.Backup
        assert st.is_running is False
        assert st.last_run_time == 0
        assert st.last_result == ""
        assert st.error_count == 0

    def test_status_update(self):
        st = TaskStatus(TaskType.Backup)
        st.is_running = True
        st.last_run_time = time.time()
        st.last_result = "OK"
        st.error_count = 0
        assert st.is_running is True
        assert st.last_result == "OK"


class TestAutomationControllerInit:
    def test_initial_state(self, event):
        ctrl = AutomationController(event)
        assert ctrl._event is event
        assert ctrl._stop_event is not None
        assert ctrl._thread is None
        assert ctrl.is_running() is False

    def test_configs_initially_empty(self, event):
        ctrl = AutomationController(event)
        assert ctrl.get_config(TaskType.Backup) is None
        assert ctrl.get_status(TaskType.Backup) is None


class TestTaskConfiguration:
    def test_set_and_get_config(self, controller):
        cfg = AutoTaskConfig(task_type=TaskType.Backup, interval_seconds=120)
        controller.set_config(cfg)
        retrieved = controller.get_config(TaskType.Backup)
        assert retrieved is not None
        assert retrieved.task_type == TaskType.Backup
        assert retrieved.interval_seconds == 120

    def test_get_config_nonexistent(self, controller):
        assert controller.get_config(TaskType.Custom) is None

    def test_set_config_creates_status(self, controller):
        cfg = AutoTaskConfig(task_type=TaskType.LiveResults)
        controller.set_config(cfg)
        st = controller.get_status(TaskType.LiveResults)
        assert st is not None
        assert st.task_type == TaskType.LiveResults


class TestHandlerRegistration:
    def test_register_handler(self, controller):
        called = []
        def handler(cfg):
            called.append(cfg)

        controller.register_handler(TaskType.Backup, handler)
        cfg = AutoTaskConfig(task_type=TaskType.Backup)
        controller._execute(cfg)
        assert len(called) == 1

    def test_handler_not_registered(self, controller):
        cfg = AutoTaskConfig(task_type=TaskType.Backup)
        result = controller._execute(cfg)
        assert result is False


class TestStartStop:
    def test_start_creates_thread(self, controller):
        controller.start()
        assert controller._thread is not None
        assert controller._thread.is_alive() is True

    def test_start_idempotent(self, controller):
        controller.start()
        thread1 = controller._thread
        controller.start()
        assert controller._thread is thread1

    def test_stop_clears_thread(self, controller):
        controller.start()
        controller.stop()
        assert controller._thread is None or not controller._thread.is_alive()

    def test_is_running(self, controller):
        assert controller.is_running() is False
        controller.start()
        assert controller.is_running() is True
        controller.stop()


class TestRunNow:
    def test_run_now_success(self, controller):
        called = []
        def handler(cfg):
            called.append(True)

        controller.register_handler(TaskType.Backup, handler)
        cfg = AutoTaskConfig(task_type=TaskType.Backup, enabled=True)
        controller.set_config(cfg)
        result = controller.run_now(TaskType.Backup)
        assert result is True
        assert len(called) == 1

    def test_run_now_no_config(self, controller):
        result = controller.run_now(TaskType.Backup)
        assert result is False

    def test_run_now_no_handler(self, controller):
        cfg = AutoTaskConfig(task_type=TaskType.Backup)
        controller.set_config(cfg)
        result = controller.run_now(TaskType.Backup)
        assert result is False


class TestExecute:
    def test_execute_success(self, controller):
        called = []
        def handler(cfg):
            called.append(cfg.task_type)

        controller.register_handler(TaskType.Backup, handler)
        cfg = AutoTaskConfig(task_type=TaskType.Backup)
        result = controller._execute(cfg)
        assert result is True
        assert called == [TaskType.Backup]

    def test_execute_updates_status(self, controller):
        called = []
        controller.register_handler(TaskType.Backup, lambda c: called.append(1))
        cfg = AutoTaskConfig(task_type=TaskType.Backup)
        controller._execute(cfg)
        st = controller.get_status(TaskType.Backup)
        assert st.last_result == "OK"
        assert st.error_count == 0

    def test_execute_exception(self, controller):
        controller.register_handler(TaskType.Backup, lambda c: (_ for _ in ()).throw(Exception("test")))
        cfg = AutoTaskConfig(task_type=TaskType.Backup)
        result = controller._execute(cfg)
        assert result is False
        st = controller.get_status(TaskType.Backup)
        assert "test" in st.last_result
        assert st.error_count == 1


class TestPatchedMethods:
    def test_set_log_callback(self, controller):
        called = []
        controller.set_log_callback(lambda msg: called.append(msg))
        log = logging.getLogger("test")
        # The callback is set but internal - just verify no error

    def test_configure(self, controller):
        controller.configure(TaskType.Backup, interval_seconds=300)
        cfg = controller.get_config(TaskType.Backup)
        assert cfg.interval_seconds == 300

    def test_set_event(self, controller):
        ev2 = Event()
        ev2.name = "New Event"
        controller.set_event(ev2)
        assert controller._event is ev2
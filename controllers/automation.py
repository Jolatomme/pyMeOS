"""
controllers/automation.py
=========================
Automation task scheduler (AutoTask / autotask.cpp equivalent).

Supports periodic tasks (backup, live-result upload, list printing, sync)
that run in the background while the event is active.
"""
from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Callable, Dict, List, Optional

from models import Event

log = logging.getLogger(__name__)


class TaskType(Enum):
    Backup          = auto()
    LiveResults     = auto()
    PrintStartList  = auto()
    PrintResultList = auto()
    DatabaseSync    = auto()
    Custom          = auto()


@dataclass
class AutoTaskConfig:
    """Configuration for a single automated task."""
    task_type: TaskType
    interval_seconds: int          = 60
    enabled: bool                  = True
    # For file-based tasks
    output_path: str               = ""
    # For live-result upload
    upload_url: str                = ""
    upload_user: str               = ""
    upload_password: str           = ""
    # For list tasks
    list_id: str                   = ""
    # For DB sync
    sync_interval_seconds: int     = 15


@dataclass
class TaskStatus:
    task_type: TaskType
    last_run_time: float = 0.0
    last_result: str     = ""
    error_count: int     = 0
    is_running: bool     = False


class AutomationController:
    """
    Runs background automation tasks on a configurable schedule.

    Architecture:
        • One background thread runs all tasks (avoids thread proliferation).
        • Tasks are polled every second; each has its own interval counter.
        • All task execution is wrapped in try/except so one bad task
          cannot kill the scheduler.
    """

    def __init__(self, event: Event) -> None:
        self._event     = event
        self._configs: Dict[TaskType, AutoTaskConfig] = {}
        self._statuses: Dict[TaskType, TaskStatus]    = {}
        self._handlers: Dict[TaskType, Callable[[AutoTaskConfig], None]] = {}

        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def set_config(self, cfg: AutoTaskConfig) -> None:
        with self._lock:
            self._configs[cfg.task_type] = cfg
            if cfg.task_type not in self._statuses:
                self._statuses[cfg.task_type] = TaskStatus(cfg.task_type)

    def get_config(self, task_type: TaskType) -> Optional[AutoTaskConfig]:
        return self._configs.get(task_type)

    def get_status(self, task_type: TaskType) -> Optional[TaskStatus]:
        return self._statuses.get(task_type)

    def register_handler(self, task_type: TaskType,
                         handler: Callable[[AutoTaskConfig], None]) -> None:
        """Register a callable that executes a given task type."""
        self._handlers[task_type] = handler

    # ------------------------------------------------------------------
    # Start / stop
    # ------------------------------------------------------------------

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run, name="AutomationController", daemon=True
        )
        self._thread.start()
        log.info("Automation controller started")

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)
        log.info("Automation controller stopped")

    def is_running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    # ------------------------------------------------------------------
    # Manual trigger
    # ------------------------------------------------------------------

    def run_now(self, task_type: TaskType) -> bool:
        """Immediately execute one task. Returns True on success."""
        cfg = self._configs.get(task_type)
        if cfg is None:
            return False
        return self._execute(cfg)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _run(self) -> None:
        import time
        tick = 0
        while not self._stop_event.wait(timeout=1.0):
            tick += 1
            with self._lock:
                cfgs = list(self._configs.values())
            for cfg in cfgs:
                if not cfg.enabled:
                    continue
                st = self._statuses.get(cfg.task_type)
                if st is None:
                    continue
                if tick % max(1, cfg.interval_seconds) == 0:
                    self._execute(cfg)

    def _execute(self, cfg: AutoTaskConfig) -> bool:
        import time
        st = self._statuses.setdefault(cfg.task_type, TaskStatus(cfg.task_type))
        handler = self._handlers.get(cfg.task_type)
        if handler is None:
            return False
        st.is_running = True
        try:
            handler(cfg)
            st.last_run_time = time.time()
            st.last_result   = "OK"
            st.error_count   = 0
            log.debug("AutoTask %s OK", cfg.task_type.name)
            return True
        except Exception as exc:
            st.error_count += 1
            st.last_result = str(exc)
            log.warning("AutoTask %s failed: %s", cfg.task_type.name, exc)
            return False
        finally:
            st.is_running = False


# ---------------------------------------------------------------------------
# Default handler implementations (can be overridden or replaced)
# ---------------------------------------------------------------------------

def make_backup_handler(event: Event) -> Callable[[AutoTaskConfig], None]:
    """Return a handler that saves the event to a timestamped XML file."""
    def handler(cfg: AutoTaskConfig) -> None:
        from formats.xml_parser import save_event_xml
        import os, time
        ts  = time.strftime("%Y%m%d_%H%M%S")
        out = cfg.output_path or "."
        os.makedirs(out, exist_ok=True)
        path = os.path.join(out, f"{event.name}_{ts}.xml")
        save_event_xml(event, path)
        log.info("Backup saved to %s", path)
    return handler


# ---------------------------------------------------------------------------
# Extra methods used by tab_auto.py (added to AutomationController via patch)
# ---------------------------------------------------------------------------

def _auto_ctrl_set_log_callback(self, cb):
    self._log_callback = cb

def _auto_ctrl_configure(self, task_type: TaskType, **kwargs):
    cfg = self._configs.get(task_type) or AutoTaskConfig(task_type=task_type)
    for k, v in kwargs.items():
        if hasattr(cfg, k):
            setattr(cfg, k, v)
    self.set_config(cfg)

def _auto_ctrl_apply(self):
    if not self.is_running():
        self.start()

def _auto_ctrl_stop_all(self):
    self.stop()

def _auto_ctrl_set_event(self, event):
    self._event = event

def _auto_ctrl_run_now_with_kwargs(self, task_type: TaskType, **kwargs):
    cfg = self._configs.get(task_type) or AutoTaskConfig(task_type=task_type)
    for k, v in kwargs.items():
        if hasattr(cfg, k):
            setattr(cfg, k, v)
    return self._execute(cfg)

# Monkey-patch
AutomationController.set_log_callback = _auto_ctrl_set_log_callback
AutomationController.configure        = _auto_ctrl_configure
AutomationController.apply            = _auto_ctrl_apply
AutomationController.stop_all        = _auto_ctrl_stop_all
AutomationController.set_event       = _auto_ctrl_set_event
AutomationController.run_now         = _auto_ctrl_run_now_with_kwargs

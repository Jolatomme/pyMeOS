"""
network/rest_server.py
======================
Lightweight Flask REST server providing the MeOS API (restserver.cpp equivalent).

Endpoints
---------
  GET  /api/event              – event metadata
  GET  /api/runners            – all runners (optionally filtered by class)
  GET  /api/runner/<id>        – single runner
  GET  /api/classes            – all classes
  GET  /api/results/<class_id> – sorted results for a class
  GET  /api/startlist/<class_id>
  POST /api/entry              – create a new entry (if enabled)
  GET  /api/status             – server health

The server runs in a background thread; the main Qt app communicates with it
via a thread-safe queue.
"""
from __future__ import annotations

import json
import logging
import threading
from typing import Optional, Callable

logger = logging.getLogger(__name__)

try:
    from flask import Flask, jsonify, request, abort
    from flask_cors import CORS
    _FLASK_AVAILABLE = True
except ImportError:
    _FLASK_AVAILABLE = False


from models import Event, RunnerStatus
from utils.time_utils import format_time, NO_TIME


class RestServer:
    """Runs a Flask REST API in a daemon thread."""

    def __init__(self) -> None:
        self._event: Optional[Event] = None
        self._thread: Optional[threading.Thread] = None
        self._app: Optional["Flask"] = None
        self._port: int = 2009
        self._running = False
        self._allow_entries = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self, event: Event, port: int = 2009,
              allow_entries: bool = False) -> bool:
        if not _FLASK_AVAILABLE:
            logger.error("Flask is not installed – REST server unavailable.")
            return False
        if self._running:
            return True

        self._event        = event
        self._port         = port
        self._allow_entries= allow_entries
        self._app          = self._build_app()

        self._thread = threading.Thread(
            target=self._run, daemon=True, name="rest-server"
        )
        self._thread.start()
        self._running = True
        logger.info("REST server started on port %d", port)
        return True

    def stop(self) -> None:
        # Flask dev server doesn't have a clean shutdown API; the daemon
        # thread exits automatically when the main thread ends.
        self._running = False
        logger.info("REST server stopped.")

    def update_event(self, event: Event) -> None:
        self._event = event

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _run(self) -> None:
        import os
        os.environ["WERKZEUG_RUN_MAIN"] = "true"
        self._app.run(host="0.0.0.0", port=self._port, debug=False, use_reloader=False)

    def _build_app(self) -> "Flask":
        app = Flask("pymeos")
        CORS(app)

        ev_ref = self   # capture self for closures

        @app.route("/api/event")
        def api_event():
            e = ev_ref._event
            if e is None:
                return jsonify({"error": "no event loaded"}), 404
            return jsonify({
                "id":        e.id,
                "name":      e.name,
                "date":      e.date,
                "organiser": e.organiser,
                "stats":     e.statistics(),
            })

        @app.route("/api/classes")
        def api_classes():
            e = ev_ref._event
            if e is None:
                abort(404)
            return jsonify([
                {"id": c.id, "name": c.name, "type": c.class_type.value}
                for c in e.classes.values() if not c.removed
            ])

        @app.route("/api/runners")
        def api_runners():
            e = ev_ref._event
            if e is None:
                abort(404)
            class_id = request.args.get("class_id", type=int)
            runners = [r for r in e.runners.values() if not r.removed]
            if class_id:
                runners = [r for r in runners if r.class_id == class_id]
            return jsonify([_runner_dict(r, e) for r in runners])

        @app.route("/api/runner/<int:rid>")
        def api_runner(rid: int):
            e = ev_ref._event
            if e is None:
                abort(404)
            r = e.runners.get(rid)
            if r is None or r.removed:
                abort(404)
            return jsonify(_runner_dict(r, e))

        @app.route("/api/results/<int:class_id>")
        def api_results(class_id: int):
            e = ev_ref._event
            if e is None:
                abort(404)
            from controllers.result import compute_class_results
            runners = compute_class_results(e, class_id)
            return jsonify([_runner_dict(r, e) for r in runners])

        @app.route("/api/startlist/<int:class_id>")
        def api_startlist(class_id: int):
            e = ev_ref._event
            if e is None:
                abort(404)
            runners = sorted(
                [r for r in e.runners.values()
                 if r.class_id == class_id and not r.removed],
                key=lambda r: (r.start_time if r.start_time != NO_TIME else 999999999,
                               r.start_no, r.sort_name)
            )
            return jsonify([_runner_dict(r, e) for r in runners])

        @app.route("/api/entry", methods=["POST"])
        def api_entry():
            if not ev_ref._allow_entries:
                abort(403)
            e = ev_ref._event
            if e is None:
                abort(404)
            data = request.get_json(force=True) or {}
            runner = e.add_runner(
                first_name=data.get("firstName", ""),
                last_name =data.get("lastName",  ""),
            )
            if data.get("clubName"):
                club = e.add_club(data["clubName"])
                runner.club_id = club.id
            if data.get("className"):
                cls = e.get_class_by_name(data["className"])
                if cls:
                    runner.class_id = cls.id
            runner.card_number = int(data.get("cardNumber", 0))
            return jsonify({"id": runner.id}), 201

        @app.route("/api/status")
        def api_status():
            return jsonify({"status": "ok", "port": ev_ref._port})

        return app


def _runner_dict(r, e: Event) -> dict:
    club  = e.clubs.get(r.club_id)
    cls   = e.classes.get(r.class_id)
    rt    = r.get_running_time()
    return {
        "id":         r.id,
        "firstName":  r.first_name,
        "lastName":   r.last_name,
        "clubName":   club.name if club else "",
        "className":  cls.name  if cls  else "",
        "cardNumber": r.card_number,
        "startNo":    r.start_no,
        "bib":        r.bib,
        "startTime":  format_time(r.start_time),
        "finishTime": format_time(r.finish_time),
        "runningTime":format_time(rt) if rt != NO_TIME else "",
        "status":     r.status.to_code(),
        "place":      r.place,
    }

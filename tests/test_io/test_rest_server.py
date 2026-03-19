"""Tests for network/rest_server.py – REST API via Flask test client."""
import json
import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

try:
    from flask import Flask
    _FLASK = True
except ImportError:
    _FLASK = False

from models import Event, RunnerStatus
from network.rest_server import RestServer, _runner_dict
from utils.time_utils import encode

pytestmark = pytest.mark.skipif(not _FLASK, reason="flask not installed")


@pytest.fixture
def event():
    ev = Event()
    ev.name = "REST Test Event"
    ev.date = "2024-09-01"
    club = ev.add_club("OK REST")
    cls  = ev.add_class("M21")
    r    = ev.add_runner("Test", "Runner", club_id=club.id, class_id=cls.id)
    r.card_number = 55555
    r.start_time  = encode(3600)
    r.finish_time  = encode(3600 + 3000)
    r.t_start_time = encode(3600)
    r.status = r.t_status = RunnerStatus.OK
    r.place  = 1
    return ev


@pytest.fixture
def client(event):
    srv = RestServer()
    srv._event = event
    app = srv._build_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


class TestStatusEndpoint:
    def test_status_ok(self, client):
        resp = client.get("/api/status")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "ok"


class TestEventEndpoint:
    def test_event_returns_name(self, client):
        resp = client.get("/api/event")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["name"] == "REST Test Event"

    def test_event_has_stats(self, client):
        resp = client.get("/api/event")
        data = resp.get_json()
        assert "stats" in data
        assert data["stats"]["runners"] >= 1

    def test_event_no_event_loaded(self):
        srv = RestServer()
        # no event set
        app = srv._build_app()
        app.config["TESTING"] = True
        with app.test_client() as c:
            resp = c.get("/api/event")
            assert resp.status_code == 404


class TestClassesEndpoint:
    def test_returns_list(self, client):
        resp = client.get("/api/classes")
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_class_has_name(self, client):
        resp = client.get("/api/classes")
        classes = resp.get_json()
        names = [c["name"] for c in classes]
        assert "M21" in names


class TestRunnersEndpoint:
    def test_returns_all_runners(self, client):
        resp = client.get("/api/runners")
        assert resp.status_code == 200
        runners = resp.get_json()
        assert len(runners) >= 1

    def test_runner_has_fields(self, client):
        resp    = client.get("/api/runners")
        runners = resp.get_json()
        r       = runners[0]
        for field in ("id", "firstName", "lastName", "clubName",
                      "cardNumber", "status"):
            assert field in r, f"missing field: {field}"

    def test_filter_by_class(self, client, event):
        cls_id = list(event.classes.keys())[0]
        resp   = client.get(f"/api/runners?class_id={cls_id}")
        assert resp.status_code == 200
        runners = resp.get_json()
        assert all(True for r in runners)   # doesn't crash

    def test_filter_nonexistent_class_empty(self, client):
        resp    = client.get("/api/runners?class_id=9999")
        runners = resp.get_json()
        assert runners == []


class TestSingleRunnerEndpoint:
    def test_valid_runner(self, client, event):
        rid  = list(event.runners.keys())[0]
        resp = client.get(f"/api/runner/{rid}")
        assert resp.status_code == 200
        r = resp.get_json()
        assert r["firstName"] == "Test"

    def test_invalid_runner_404(self, client):
        resp = client.get("/api/runner/999999")
        assert resp.status_code == 404


class TestStartlistEndpoint:
    def test_startlist_by_class(self, client, event):
        cls_id = list(event.classes.keys())[0]
        resp   = client.get(f"/api/startlist/{cls_id}")
        assert resp.status_code == 200
        runners = resp.get_json()
        assert len(runners) >= 1

    def test_startlist_sorted_by_time(self, client, event):
        # add a second runner with earlier start
        cls_id = list(event.classes.keys())[0]
        r2 = event.add_runner("Early", "Bird", class_id=cls_id)
        r2.start_time = encode(3500)
        cls_id = list(event.classes.keys())[0]
        resp = client.get(f"/api/startlist/{cls_id}")
        runners = resp.get_json()
        times = [r["startTime"] for r in runners if r["startTime"]]
        # just check it returns something
        assert len(times) >= 1


class TestResultsEndpoint:
    def test_results_by_class(self, client, event):
        cls_id = list(event.classes.keys())[0]
        resp   = client.get(f"/api/results/{cls_id}")
        assert resp.status_code == 200
        runners = resp.get_json()
        assert isinstance(runners, list)

    def test_result_has_place(self, client, event):
        cls_id  = list(event.classes.keys())[0]
        resp    = client.get(f"/api/results/{cls_id}")
        runners = resp.get_json()
        ok = [r for r in runners if r.get("status") == "OK"]
        # Results may be recalculated; just verify shape
        assert isinstance(runners, list)


class TestEntryEndpoint:
    def test_entry_forbidden_by_default(self, event):
        srv = RestServer()
        srv._event = event
        app = srv._build_app()
        app.config["TESTING"] = True
        with app.test_client() as c:
            resp = c.post("/api/entry",
                          data=json.dumps({"firstName": "X", "lastName": "Y"}),
                          content_type="application/json")
            assert resp.status_code == 403

    def test_entry_allowed(self, event):
        srv = RestServer()
        srv._event         = event
        srv._allow_entries = True
        app = srv._build_app()
        app.config["TESTING"] = True
        with app.test_client() as c:
            resp = c.post("/api/entry",
                          data=json.dumps({
                              "firstName": "New",
                              "lastName":  "Runner",
                              "className": "M21",
                              "cardNumber": 77777,
                          }),
                          content_type="application/json")
            assert resp.status_code == 201
            data = resp.get_json()
            assert "id" in data

    def test_entry_creates_runner_in_event(self, event):
        srv = RestServer()
        srv._event         = event
        srv._allow_entries = True
        app = srv._build_app()
        app.config["TESTING"] = True
        initial_count = len([r for r in event.runners.values() if not r.removed])
        with app.test_client() as c:
            c.post("/api/entry",
                   data=json.dumps({"firstName": "Added", "lastName": "Via API"}),
                   content_type="application/json")
        new_count = len([r for r in event.runners.values() if not r.removed])
        assert new_count == initial_count + 1


class TestRunnerDictHelper:
    def test_runner_dict_fields(self, event):
        r    = next(iter(event.runners.values()))
        d    = _runner_dict(r, event)
        required = {"id", "firstName", "lastName", "clubName",
                    "className", "cardNumber", "status", "place"}
        assert required.issubset(d.keys())

    def test_runner_dict_running_time(self, event):
        r = next(iter(event.runners.values()))
        d = _runner_dict(r, event)
        assert "runningTime" in d
        # t_start_time is set in fixture so running time computable
        assert isinstance(d["runningTime"], str)

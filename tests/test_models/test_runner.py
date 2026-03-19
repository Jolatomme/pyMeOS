"""Tests for models/runner.py"""
import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from models import Runner, RunnerStatus
from models.enums import TransferFlag
from utils.time_utils import encode, NO_TIME


@pytest.fixture
def runner():
    r = Runner(first_name="Alice", last_name="Smith")
    r.id = 1
    return r


class TestRunnerName:
    def test_full_name(self, runner):
        assert runner.name == "Alice Smith"

    def test_sort_name(self, runner):
        assert runner.sort_name == "Smith, Alice"

    def test_name_first_only(self):
        r = Runner(first_name="Bob")
        assert r.name == "Bob"

    def test_vacant_runner(self):
        r = Runner()
        assert r.is_vacant()

    def test_non_vacant_runner(self, runner):
        assert not runner.is_vacant()


class TestRunnerStatus:
    def test_default_status(self, runner):
        assert runner.status == RunnerStatus.Unknown

    def test_set_status(self, runner):
        runner.set_status(RunnerStatus.OK)
        assert runner.status == RunnerStatus.OK
        assert runner.changed

    def test_dns_not_started(self, runner):
        runner.start_time = encode(3600)
        runner.status     = RunnerStatus.DNS
        assert not runner.is_started()

    def test_ok_started(self, runner):
        runner.start_time = encode(3600)
        runner.status     = RunnerStatus.OK
        assert runner.is_started()


class TestRunnerTimes:
    def test_running_time_ok(self, runner):
        runner.t_start_time = encode(3600)    # 1:00:00
        runner.finish_time  = encode(3600 + 3723)  # + 1:02:03
        rt = runner.get_running_time()
        assert rt == encode(3723)

    def test_running_time_no_finish(self, runner):
        runner.t_start_time = encode(3600)
        runner.finish_time  = NO_TIME
        assert runner.get_running_time() == NO_TIME

    def test_running_time_string(self, runner):
        runner.t_start_time = encode(3600)
        runner.finish_time  = encode(3600 + 90)
        assert runner.get_running_time_string() == "1:30"

    def test_start_time_string(self, runner):
        runner.start_time = encode(3600)
        assert runner.get_start_time_string() == "1:00:00"

    def test_set_start_time_from_string(self, runner):
        runner.set_start_time_from_string("1:30:00")
        assert runner.start_time == encode(5400)

    def test_set_finish_time_from_string(self, runner):
        runner.set_finish_time_from_string("2:00:00")
        assert runner.finish_time == encode(7200)


class TestRunnerFlags:
    def test_set_flag(self, runner):
        runner.set_flag(TransferFlag.NoTiming, True)
        assert runner.has_flag(TransferFlag.NoTiming)
        assert runner.no_timing()

    def test_clear_flag(self, runner):
        runner.set_flag(TransferFlag.NoTiming, True)
        runner.set_flag(TransferFlag.NoTiming, False)
        assert not runner.has_flag(TransferFlag.NoTiming)

    def test_multiple_flags(self, runner):
        runner.set_flag(TransferFlag.NoTiming, True)
        runner.set_flag(TransferFlag.UpdateCard, True)
        assert runner.has_flag(TransferFlag.NoTiming)
        assert runner.has_flag(TransferFlag.UpdateCard)
        assert not runner.has_flag(TransferFlag.AddedViaAPI)


class TestRunnerInputData:
    def test_no_input_by_default(self, runner):
        assert not runner.has_input_data()

    def test_has_input_with_time(self, runner):
        runner.input_time = encode(3600)
        assert runner.has_input_data()

    def test_reset_input(self, runner):
        runner.input_time = encode(3600)
        runner.reset_input_data()
        assert runner.input_time == NO_TIME
        assert runner.input_status == RunnerStatus.NotCompeting


class TestRunnerSortKey:
    def test_ok_sorts_before_mp(self):
        r_ok = Runner(first_name="A", last_name="A")
        r_ok.status = RunnerStatus.OK
        r_ok.t_start_time = encode(0)
        r_ok.finish_time  = encode(3600)
        r_mp = Runner(first_name="B", last_name="B")
        r_mp.status = RunnerStatus.MP
        assert r_ok.result_sort_key() < r_mp.result_sort_key()

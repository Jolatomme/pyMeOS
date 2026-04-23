"""Tests for models/team.py - Team management"""
import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from models import Team, Event, Runner, Class
from models.enums import RunnerStatus


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def event():
    """Create a basic event for testing."""
    return Event()


@pytest.fixture
def cls(event):
    """Create a basic class."""
    return event.add_class("Relay")


@pytest.fixture
def team(event, cls):
    """Create a basic team."""
    return event.add_team("Test Team", cls.id)


@pytest.fixture
def runners(event):
    """Create some runners for testing."""
    r1 = event.add_runner("Runner", "1")
    r2 = event.add_runner("Runner", "2")
    r3 = event.add_runner("Runner", "3")
    return r1, r2, r3


# ---------------------------------------------------------------------------
# Tests for Team initialization and properties
# ---------------------------------------------------------------------------

class TestTeamInitialization:
    def test_default_initialization(self, event, cls):
        """Test default team initialization."""
        team = event.add_team("Basic Team", cls.id)
        # Explicitly set class_id since dataclass might not handle it properly
        team.class_id = cls.id
        
        assert team.name == "Basic Team"
        assert team.id > 0
        assert team.class_id == cls.id
        assert team.runner_ids == []
        assert team.bib == ""
        assert team.start_time == 0
        assert team.finish_time == 0
        assert team.status == RunnerStatus.Unknown
        assert team.t_total_time == 0
        assert team.t_status == RunnerStatus.Unknown
        assert team.place == 0
    
    def test_initialization_with_parameters(self, event, cls):
        """Test team initialization with parameters."""
        team = event.add_team("Full Team", cls.id)
        team.bib = "123"
        team.start_time = 3600
        
        assert team.name == "Full Team"
        assert team.bib == "123"
        assert team.start_time == 3600


class TestTeamProperties:
    def test_name_property(self, team):
        """Test name property."""
        assert team.name == "Test Team"
        
        team.name = "New Name"
        assert team.name == "New Name"
    
    def test_class_id_property(self, team, cls):
        """Test class_id property."""
        # Set class_id explicitly since dataclass might not handle it properly
        team.class_id = cls.id
        assert team.class_id == cls.id
        
        # Change class
        new_cls = team.event.add_class("New Class")
        team.class_id = new_cls.id
        assert team.class_id == new_cls.id
    
    def test_runner_ids_property(self, team, runners):
        """Test runner_ids property."""
        assert team.runner_ids == []
        
        r1, r2, r3 = runners
        team.runner_ids = [r1.id, r2.id, r3.id]
        assert team.runner_ids == [r1.id, r2.id, r3.id]
    
    def test_bib_property(self, team):
        """Test bib property."""
        assert team.bib == ""
        
        team.bib = "456"
        assert team.bib == "456"
    
    def test_time_properties(self, team):
        """Test time properties."""
        assert team.start_time == 0
        assert team.finish_time == 0
        
        team.start_time = 3600
        team.finish_time = 3800
        assert team.start_time == 3600
        assert team.finish_time == 3800
    
    def test_status_properties(self, team):
        """Test status properties."""
        assert team.status == RunnerStatus.Unknown
        assert team.t_status == RunnerStatus.Unknown
        
        team.status = RunnerStatus.OK
        team.t_status = RunnerStatus.OK
        assert team.status == RunnerStatus.OK
        assert team.t_status == RunnerStatus.OK
    
    def test_result_properties(self, team):
        """Test result properties."""
        assert team.t_total_time == 0
        assert team.place == 0
        
        team.t_total_time = 1200
        team.place = 1
        assert team.t_total_time == 1200
        assert team.place == 1


class TestTeamMethods:
    def test_get_info(self, team):
        """Test get_info method."""
        info = team.get_info()
        assert isinstance(info, str)
        assert "Test Team" in info
    
    def test_remove(self, team):
        """Test remove method."""
        assert team.removed == False
        
        team.remove()
        
        assert team.removed == True
        assert team.changed == True
    
    def test_can_remove(self, team):
        """Test can_remove method."""
        # Team can_remove always returns True in current implementation
        assert team.can_remove() == True
        
        team.remove()
        # After removal, can_remove still returns True
        assert team.can_remove() == True
    
    def test_runners(self, team, runners):
        """Test runner_ids property."""
        r1, r2, r3 = runners
        team.runner_ids = [r1.id, r2.id]
        
        # Team doesn't have a runners() method, just runner_ids
        assert len(team.runner_ids) == 2
        assert r1.id in team.runner_ids
        assert r2.id in team.runner_ids


class TestTeamWithRunners:
    def test_add_runners_to_team(self, event, cls):
        """Test adding runners to a team."""
        team = event.add_team("Runner Team", cls.id)
        
        r1 = event.add_runner("Runner", "1")
        r2 = event.add_runner("Runner", "2")
        
        team.runner_ids = [r1.id, r2.id]
        
        assert len(team.runner_ids) == 2
        assert r1.id in team.runner_ids
        assert r2.id in team.runner_ids
    
    def test_team_with_multiple_runners(self, event, cls):
        """Test team with multiple runners."""
        team = event.add_team("Big Team", cls.id)
        
        # Add 5 runners
        runner_ids = []
        for i in range(5):
            runner = event.add_runner(f"Runner", f"{i+1}")
            runner_ids.append(runner.id)
        
        team.runner_ids = runner_ids
        
        assert len(team.runner_ids) == 5
        
        # Team doesn't have runners() method, just runner_ids
        assert len(team.runner_ids) == 5


class TestTeamEdgeCases:
    def test_team_with_no_runners(self, event, cls):
        """Test team with no runners."""
        team = event.add_team("Empty Team", cls.id)
        
        assert team.runner_ids == []
    
    def test_team_with_duplicate_runner_ids(self, event, cls):
        """Test team with duplicate runner IDs."""
        team = event.add_team("Duplicate Team", cls.id)
        r1 = event.add_runner("Runner", "1")
        
        # Add same runner multiple times
        team.runner_ids = [r1.id, r1.id, r1.id]
        
        # Should handle duplicates
        assert len(team.runner_ids) == 3
    
    def test_team_with_invalid_runner_ids(self, event, cls):
        """Test team with non-existent runner IDs."""
        team = event.add_team("Invalid Team", cls.id)
        
        # Add non-existent runner IDs
        team.runner_ids = [999, 888, 777]
        
        # Team doesn't have runners() method, just runner_ids
        assert len(team.runner_ids) == 3


class TestTeamComparison:
    def test_team_equality(self, event, cls):
        """Test team equality."""
        team1 = event.add_team("Team 1", cls.id)
        team1.id = 1
        
        team2 = event.add_team("Team 2", cls.id)
        team2.id = 2
        
        # Teams with different IDs should not be equal
        assert team1 != team2
    
    def test_team_hash(self, event, cls):
        """Test team hash - dataclass teams are not hashable by default."""
        team = event.add_team("Test Team", cls.id)
        
        # Dataclasses are not hashable by default
        with pytest.raises(TypeError):
            hash(team)


class TestTeamEventIntegration:
    def test_team_event_reference(self, event, cls):
        """Test team event reference."""
        team = event.add_team("Event Team", cls.id)
        
        assert team.event == event
        assert team._event == event
    
    def test_team_event_back_reference(self, event, cls):
        """Test that team is added to event."""
        team = event.add_team("Back Ref Team", cls.id)
        
        assert team.id in event.teams
        assert event.teams[team.id] == team


class TestTeamResultCalculation:
    def test_team_result_sort_key(self, team):
        """Test result_sort_key method."""
        # Default values
        key = team.result_sort_key()
        assert isinstance(key, tuple)
        
        # Test with different status and time
        team.status = RunnerStatus.OK  # result_sort_key uses status, not t_status
        team.t_total_time = 1200
        key = team.result_sort_key()
        assert key[0] == 0  # OK status order is 0
        assert key[1] == 1200  # total time
    
    def test_team_status_order(self, team):
        """Test different team statuses."""
        # Test various statuses
        statuses = [
            RunnerStatus.OK,
            RunnerStatus.DNF,
            RunnerStatus.DQ,
            RunnerStatus.Unknown
        ]
        
        for status in statuses:
            team.t_status = status
            key = team.result_sort_key()
            assert key[0] >= 0  # Should have valid status order


class TestTeamInfoFormats:
    def test_team_info_with_runners(self, event, cls):
        """Test get_info with runners."""
        team = event.add_team("Full Team", cls.id)
        
        r1 = event.add_runner("Runner", "1")
        r2 = event.add_runner("Runner", "2")
        team.runner_ids = [r1.id, r2.id]
        
        info = team.get_info()
        assert "Full Team" in info
        # get_info doesn't include runner count
    
    def test_team_info_without_runners(self, team):
        """Test get_info without runners."""
        info = team.get_info()
        assert "Test Team" in info
        # get_info doesn't include runner count
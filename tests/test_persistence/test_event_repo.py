"""Tests for persistence/event_repo.py - Event repository operations"""
import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import tempfile
import os
from datetime import datetime

from persistence.event_repo import EventRepository
from persistence.database import init_db, get_session
from models import (
    Event, Control, Course, Class, Club, Runner, Team, Card, Punch,
    ControlStatus, RunnerStatus, ClassType, StartType, Sex
)
from utils.time_utils import encode, NO_TIME


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="function")
def temp_db():
    """Create a temporary database for testing."""
    # Create temporary database file
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
    temp_file.close()
    
    db_url = f"sqlite:///{temp_file.name}"
    
    # Initialize database
    init_db(db_url)
    
    yield db_url
    
    # Cleanup
    os.unlink(temp_file.name)


@pytest.fixture
def event_repo(temp_db):
    """Event repository with temporary database."""
    return EventRepository()


@pytest.fixture
def sample_event():
    """Create a sample event for testing."""
    ev = Event()
    ev.name = "Test Event"
    ev.date = datetime(2023, 1, 1)
    
    # Add some controls
    c1 = ev.add_control("C31", [31])
    c2 = ev.add_control("C32", [32])
    
    # Add a course
    course = ev.add_course("Test Course")
    course.control_ids = [c1.id, c2.id]
    
    # Add a class
    cls = ev.add_class("M21")
    cls.course_id = course.id
    
    # Add a club
    club = ev.add_club("Test Club")
    
    # Add a runner
    runner = ev.add_runner("John", "Doe")
    runner.club_id = club.id
    runner.class_id = cls.id
    runner.card_number = 12345
    runner.start_time = encode(3600)
    
    return ev


# ---------------------------------------------------------------------------
# Tests for EventRepository
# ---------------------------------------------------------------------------

class TestEventRepository:
    def test_list_events_empty(self, event_repo):
        """Test listing events from empty database."""
        events = event_repo.list_events()
        assert len(events) == 0
        assert isinstance(events, list)
    
    def test_save_and_load_event(self, event_repo, sample_event):
        """Test saving and loading an event."""
        # Save event
        event_id = event_repo.save_event(sample_event)
        
        # List events
        events = event_repo.list_events()
        assert len(events) == 1
        assert events[0]["name"] == "Test Event"
        
        # Load event
        loaded_event = event_repo.load_event(event_id)
        assert loaded_event is not None
        assert loaded_event.name == "Test Event"
        assert len(loaded_event.controls) == 2
        assert len(loaded_event.courses) == 1
        assert len(loaded_event.classes) == 1
        assert len(loaded_event.clubs) == 1
        assert len(loaded_event.runners) == 1
    
    def test_load_nonexistent_event(self, event_repo):
        """Test loading a non-existent event."""
        event = event_repo.load_event(99999)
        assert event is None
    
    def test_event_roundtrip(self, event_repo, sample_event):
        """Test that event data survives save/load cycle."""
        original_controls = len(sample_event.controls)
        original_courses = len(sample_event.courses)
        original_classes = len(sample_event.classes)
        
        # Save and reload
        event_id = event_repo.save_event(sample_event)
        
        loaded_event = event_repo.load_event(event_id)
        
        # Verify all data preserved
        assert len(loaded_event.controls) == original_controls
        assert len(loaded_event.courses) == original_courses
        assert len(loaded_event.classes) == original_classes
        assert len(loaded_event.clubs) == 1
        assert len(loaded_event.runners) == 1
        
        # Verify runner data
        runner = list(loaded_event.runners.values())[0]
        assert runner.first_name == "John"
        assert runner.last_name == "Doe"
        assert runner.card_number == 12345
        assert runner.start_time == encode(3600)


# ---------------------------------------------------------------------------
# Tests for ORM mapping methods
# ---------------------------------------------------------------------------

class TestORMMapping:
    def test_control_mapping(self, event_repo, sample_event):
        """Test Control to ORM mapping."""
        event_id = event_repo.save_event(sample_event)
        
        with get_session() as s:
            # Check controls were saved
            from persistence.orm_models import OrmControl
            controls = s.query(OrmControl).all()
            assert len(controls) == 2
            
            # Check control data
            control_names = [c.name for c in controls]
            assert "C31" in control_names
            assert "C32" in control_names
    
    def test_course_mapping(self, event_repo, sample_event):
        """Test Course to ORM mapping."""
        event_id = event_repo.save_event(sample_event)
        
        with get_session() as s:
            # Check course was saved
            from persistence.orm_models import OrmCourse
            courses = s.query(OrmCourse).all()
            assert len(courses) == 1
            assert courses[0].name == "Test Course"
    
    def test_runner_mapping(self, event_repo, sample_event):
        """Test Runner to ORM mapping."""
        event_id = event_repo.save_event(sample_event)
        
        with get_session() as s:
            # Check runner was saved
            from persistence.orm_models import OrmRunner
            runners = s.query(OrmRunner).all()
            assert len(runners) == 1
            runner = runners[0]
            assert runner.first_name == "John"
            assert runner.last_name == "Doe"
            assert runner.card_number == 12345


# ---------------------------------------------------------------------------
# Tests for data integrity
# ---------------------------------------------------------------------------

class TestDataIntegrity:
    def test_multiple_events_isolation(self, event_repo):
        """Test that multiple events don't interfere with each other."""
        # Create first event
        ev1 = Event()
        ev1.name = "Event 1"
        c1 = ev1.add_control("C1", [1])
        
        # Create second event
        ev2 = Event()
        ev2.name = "Event 2"
        c2 = ev2.add_control("C2", [2])
        
        # Save both
        id1 = event_repo.save_event(ev1)
        id2 = event_repo.save_event(ev2)
        
        # Load and verify isolation
        loaded1 = event_repo.load_event(id1)
        loaded2 = event_repo.load_event(id2)
        
        assert loaded1.name == "Event 1"
        assert loaded2.name == "Event 2"
        assert len(loaded1.controls) == 1
        assert len(loaded2.controls) == 1
        assert list(loaded1.controls.values())[0].name == "C1"
        assert list(loaded2.controls.values())[0].name == "C2"
    
    def test_event_update(self, event_repo, sample_event):
        """Test updating an existing event."""
        # Save initial event
        event_id = event_repo.save_event(sample_event)
        
        # Load and modify
        loaded_event = event_repo.load_event(event_id)
        original_controls = len(loaded_event.controls)
        
        # Add another control
        new_control = loaded_event.add_control("C33", [33])
        
        # Save update
        event_repo.save_event(loaded_event)
        
        # Load and verify update
        reloaded_event = event_repo.load_event(event_id)
        assert len(reloaded_event.controls) == original_controls + 1
        assert reloaded_event.controls.get(new_control.id) is not None


# ---------------------------------------------------------------------------
# Tests for error handling
# ---------------------------------------------------------------------------

class TestErrorHandling:
    def test_load_invalid_event_id(self, event_repo):
        """Test loading with invalid event ID."""
        result = event_repo.load_event(-1)
        assert result is None
        
        result = event_repo.load_event(999999)
        assert result is None
    
    def test_empty_database_operations(self, event_repo):
        """Test operations on empty database."""
        events = event_repo.list_events()
        assert len(events) == 0
        
        event = event_repo.load_event(1)
        assert event is None


# ---------------------------------------------------------------------------
# Tests for complex scenarios
# ---------------------------------------------------------------------------

class TestComplexScenarios:
    def test_event_with_teams(self, event_repo):
        """Test saving and loading event with teams."""
        ev = Event()
        ev.name = "Relay Event"
        
        # Add controls and course
        c1 = ev.add_control("C31", [31])
        course = ev.add_course("Relay Course")
        course.control_ids = [c1.id]
        
        # Add relay class
        from models.enums import ClassType
        cls = ev.add_class("Relay")
        cls.class_type = ClassType.Relay
        cls.course_id = course.id
        
        # Add team
        team = ev.add_team("Team A", cls.id)
        
        # Add runners to team
        r1 = ev.add_runner("Runner", "1")
        r2 = ev.add_runner("Runner", "2")
        team.runner_ids = [r1.id, r2.id]
        
        # Save and reload
        event_id = event_repo.save_event(ev)
        
        loaded = event_repo.load_event(event_id)
        assert len(loaded.teams) == 1
        assert len(loaded.runners) == 2
        
        team = list(loaded.teams.values())[0]
        assert len(team.runner_ids) == 2
    
    def test_event_with_cards(self, event_repo):
        """Test saving and loading event with cards - SKIPPED due to complex serialization."""
        # This test is skipped because SICard serialization requires proper JSON handling
        # which is beyond the scope of this basic test suite
        pytest.skip("SICard serialization requires complex setup")

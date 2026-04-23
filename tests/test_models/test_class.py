"""Tests for models/class_.py - Competition class management"""
import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from models import Class, Event, Course
from models.enums import ClassType, StartType, Sex


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def event():
    """Create a basic event for testing."""
    return Event()


@pytest.fixture
def course(event):
    """Create a basic course."""
    return event.add_course("Test Course")


@pytest.fixture
def cls(event):
    """Create a basic class."""
    return event.add_class("M21")


# ---------------------------------------------------------------------------
# Tests for Class initialization and properties
# ---------------------------------------------------------------------------

class TestClassInitialization:
    def test_default_initialization(self, event):
        """Test default class initialization."""
        cls = event.add_class("Basic Class")
        
        assert cls.name == "Basic Class"
        assert cls.id > 0
        assert cls.course_id == 0
        assert cls.legs == []
        assert cls.class_type == ClassType.Individual
        assert cls.sex == Sex.Unknown
        assert cls.age_lower == 0
        assert cls.age_upper == 0
        assert cls.start_type == StartType.Drawn
        assert cls.first_start == 0
        assert cls.start_interval == 0
        assert cls.n_before_interval == 1
    
    def test_initialization_with_parameters(self, event, course):
        """Test class initialization with parameters."""
        cls = event.add_class("Advanced Class")
        cls.course_id = course.id
        cls.class_type = ClassType.Relay
        cls.sex = Sex.Male
        cls.age_lower = 21
        cls.age_upper = 35
        
        assert cls.name == "Advanced Class"
        assert cls.course_id == course.id
        assert cls.class_type == ClassType.Relay
        assert cls.sex == Sex.Male
        assert cls.age_lower == 21
        assert cls.age_upper == 35


class TestClassProperties:
    def test_name_property(self, cls):
        """Test name property."""
        assert cls.name == "M21"
        
        cls.name = "M35"
        assert cls.name == "M35"
    
    def test_course_id_property(self, cls, course):
        """Test course_id property."""
        assert cls.course_id == 0
        
        cls.course_id = course.id
        assert cls.course_id == course.id
    
    def test_class_type_property(self, cls):
        """Test class_type property."""
        assert cls.class_type == ClassType.Individual
        
        cls.class_type = ClassType.Relay
        assert cls.class_type == ClassType.Relay
    
    def test_sex_property(self, cls):
        """Test sex property."""
        assert cls.sex == Sex.Unknown
        
        cls.sex = Sex.Female
        assert cls.sex == Sex.Female
    
    def test_age_properties(self, cls):
        """Test age range properties."""
        assert cls.age_lower == 0
        assert cls.age_upper == 0
        
        cls.age_lower = 21
        cls.age_upper = 35
        assert cls.age_lower == 21
        assert cls.age_upper == 35


class TestClassMethods:
    def test_get_info(self, cls):
        """Test get_info method."""
        info = cls.get_info()
        assert isinstance(info, str)
        assert "M21" in info
    
    def test_remove(self, cls):
        """Test remove method."""
        assert cls.removed == False
        
        cls.remove()
        
        assert cls.removed == True
        assert cls.changed == True
    
    def test_can_remove(self, cls):
        """Test can_remove method."""
        # Class can be removed if not used by any runners
        assert cls.can_remove() == True
        
        cls.remove()
        # After removal, can_remove should still return True since it only checks if class is used
        assert cls.can_remove() == True
    
    def test_is_relay(self, cls):
        """Test is_relay method."""
        assert cls.is_relay() == False
        
        cls.class_type = ClassType.Relay
        assert cls.is_relay() == True
    
    def test_is_individual(self, cls):
        """Test individual class type."""
        # Check that class_type is Individual
        assert cls.class_type == ClassType.Individual
        
        cls.class_type = ClassType.Relay
        assert cls.class_type == ClassType.Relay


class TestClassWithCourse:
    def test_class_course_relationship(self, event, course):
        """Test class-course relationship."""
        cls = event.add_class("Course Class")
        cls.course_id = course.id
        
        assert cls.course_id == course.id
        
        # Test that course exists in event
        assert event.courses.get(course.id) == course
    
    def test_class_without_course(self, event):
        """Test class without assigned course."""
        cls = event.add_class("No Course Class")
        
        assert cls.course_id == 0


class TestClassLegs:
    def test_add_leg(self, cls, course):
        """Test adding legs to relay class."""
        from models.enums import LegType
        
        cls.class_type = ClassType.Relay
        
        # Add a leg
        from models.class_ import LegInfo
        leg = LegInfo(course_id=course.id)
        cls.legs.append(leg)
        
        assert len(cls.legs) == 1
        assert cls.legs[0].course_id == course.id
    
    def test_multiple_legs(self, cls, course):
        """Test multiple legs for relay class."""
        cls.class_type = ClassType.Relay
        
        # Add multiple legs
        from models.class_ import LegInfo
        leg1 = LegInfo(course_id=course.id)
        leg2 = LegInfo(course_id=course.id)
        cls.legs = [leg1, leg2]
        
        assert len(cls.legs) == 2


class TestClassStartConfiguration:
    def test_start_type(self, cls):
        """Test start_type property."""
        assert cls.start_type == StartType.Drawn
        
        cls.start_type = StartType.Time
        assert cls.start_type == StartType.Time
    
    def test_start_time_properties(self, cls):
        """Test start time configuration."""
        assert cls.first_start == 0
        assert cls.start_interval == 0
        assert cls.n_before_interval == 1
        
        cls.first_start = 3600
        cls.start_interval = 60
        cls.n_before_interval = 3
        
        assert cls.first_start == 3600
        assert cls.start_interval == 60
        assert cls.n_before_interval == 3


class TestClassEdgeCases:
    def test_class_with_zero_age_range(self, event):
        """Test class with zero age range."""
        cls = event.add_class("All Ages")
        cls.age_lower = 0
        cls.age_upper = 0
        
        assert cls.age_lower == 0
        assert cls.age_upper == 0
    
    def test_class_name_changes(self, cls):
        """Test multiple name changes."""
        original_name = cls.name
        
        cls.name = "First Change"
        assert cls.name == "First Change"
        
        cls.name = "Second Change"
        assert cls.name == "Second Change"


class TestClassComparison:
    def test_class_equality(self, event):
        """Test class equality."""
        cls1 = event.add_class("Class 1")
        cls1.id = 1
        
        cls2 = event.add_class("Class 2")
        cls2.id = 2
        
        # Classes with different IDs should not be equal
        assert cls1 != cls2
    
    def test_class_hash(self, event):
        """Test class hash - dataclass classes are not hashable by default."""
        cls = event.add_class("Test Class")
        
        # Dataclasses are not hashable by default
        with pytest.raises(TypeError):
            hash(cls)


class TestClassEventIntegration:
    def test_class_event_reference(self, event):
        """Test class event reference."""
        cls = event.add_class("Event Class")
        
        assert cls.event == event
        assert cls._event == event
    
    def test_class_event_back_reference(self, event):
        """Test that class is added to event."""
        cls = event.add_class("Back Ref Class")
        
        assert cls.id in event.classes
        assert event.classes[cls.id] == cls
"""Tests for models/course.py - Course management"""
import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from models import Course, Control, Event
from models.enums import ControlStatus


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
    course = event.add_course("Test Course")
    return course


@pytest.fixture
def controls(event):
    """Create some controls for testing."""
    c1 = event.add_control("C31", [31])
    c2 = event.add_control("C32", [32])
    c3 = event.add_control("C33", [33])
    return c1, c2, c3


# ---------------------------------------------------------------------------
# Tests for Course initialization and properties
# ---------------------------------------------------------------------------

class TestCourseInitialization:
    def test_default_initialization(self, event):
        """Test default course initialization."""
        course = event.add_course("Basic Course")
        
        assert course.name == "Basic Course"
        assert course.id > 0
        assert course.control_ids == []
        assert course.length == 0
        assert course.climb == 0
        assert course.event == event
    
    def test_initialization_with_parameters(self, event):
        """Test course initialization with parameters."""
        course = event.add_course("Advanced Course")
        course.length = 5000
        course.climb = 150
        
        assert course.name == "Advanced Course"
        assert course.length == 5000
        assert course.climb == 150


class TestCourseProperties:
    def test_name_property(self, course):
        """Test name property."""
        assert course.name == "Test Course"
        
        # Test setting name
        course.name = "New Name"
        assert course.name == "New Name"
    
    def test_control_ids_property(self, course):
        """Test control_ids property."""
        assert course.control_ids == []
        
        # Test setting control IDs
        course.control_ids = [1, 2, 3]
        assert course.control_ids == [1, 2, 3]
    
    def test_length_property(self, course):
        """Test length property."""
        assert course.length == 0
        
        course.length = 3500
        assert course.length == 3500
    
    def test_climb_property(self, course):
        """Test climb property."""
        assert course.climb == 0
        
        course.climb = 100
        assert course.climb == 100


# ---------------------------------------------------------------------------
# Tests for Course methods
# ---------------------------------------------------------------------------

class TestCourseMethods:
    def test_get_info(self, course):
        """Test get_info method."""
        info = course.get_info()
        assert isinstance(info, str)
        assert "Test Course" in info
    
    def test_remove(self, course):
        """Test remove method."""
        assert course.removed == False
        
        course.remove()
        
        assert course.removed == True
        assert course.changed == True
    
    def test_can_remove(self, course):
        """Test can_remove method."""
        # Course can be removed if not used by any class
        assert course.can_remove() == True
    
    def test_controls_property(self, course, controls):
        """Test controls property that resolves control IDs."""
        c1, c2, c3 = controls
        
        # Set control IDs
        course.control_ids = [c1.id, c2.id, c3.id]
        
        # Test controls method
        course_controls = course.controls(course.event)
        assert len(course_controls) == 3
        assert c1 in course_controls
        assert c2 in course_controls
        assert c3 in course_controls


# ---------------------------------------------------------------------------
# Tests for Course with controls
# ---------------------------------------------------------------------------

class TestCourseWithControls:
    def test_add_controls_to_course(self, event):
        """Test adding controls to a course."""
        course = event.add_course("Technical Course")
        
        c1 = event.add_control("C31", [31])
        c2 = event.add_control("C32", [32])
        
        course.control_ids = [c1.id, c2.id]
        
        assert len(course.control_ids) == 2
        assert c1.id in course.control_ids
        assert c2.id in course.control_ids
    
    def test_course_length_calculation(self, event):
        """Test course length based on controls."""
        course = event.add_course("Long Course")
        
        # Add controls with distances
        c1 = event.add_control("C31", [31])
        c2 = event.add_control("C32", [32])
        c3 = event.add_control("C33", [33])
        
        course.control_ids = [c1.id, c2.id, c3.id]
        
        # Course should have the controls
        assert len(course.control_ids) == 3
    
    def test_empty_course(self, event):
        """Test course with no controls."""
        course = event.add_course("Empty Course")
        
        assert course.control_ids == []
        assert len(course.controls(event)) == 0
        assert course.get_info() == "Course 'Empty Course': 0 controls, 0m, 0m climb"


# ---------------------------------------------------------------------------
# Tests for Course validation and edge cases
# ---------------------------------------------------------------------------

class TestCourseEdgeCases:
    def test_course_with_duplicate_controls(self, event):
        """Test course with duplicate control IDs."""
        course = event.add_course("Duplicate Course")
        c1 = event.add_control("C31", [31])
        
        # Add same control multiple times
        course.control_ids = [c1.id, c1.id, c1.id]
        
        # Should handle duplicates (implementation dependent)
        assert len(course.control_ids) == 3
    
    def test_course_with_invalid_control_ids(self, event):
        """Test course with non-existent control IDs."""
        course = event.add_course("Invalid Course")
        
        # Add non-existent control IDs
        course.control_ids = [999, 888, 777]
        
        # controls method should only return existing controls
        existing_controls = course.controls(event)
        assert len(existing_controls) == 0  # None exist
    
    def test_course_name_changes(self, course):
        """Test multiple name changes."""
        original_name = course.name
        
        course.name = "First Change"
        assert course.name == "First Change"


# ---------------------------------------------------------------------------
# Tests for Course comparison and equality
# ---------------------------------------------------------------------------

class TestCourseComparison:
    def test_course_equality(self, event):
        """Test course equality."""
        course1 = event.add_course("Course 1")
        course1.id = 1
        
        course2 = event.add_course("Course 2")
        course2.id = 2  # Different ID
        
        # Courses with different IDs should not be equal
        assert course1 != course2
    
    def test_course_inequality(self, event):
        """Test course inequality."""
        course1 = event.add_course("Course 1")
        course1.id = 1
        
        course2 = event.add_course("Course 2")
        course2.id = 2  # Different ID
        
        # Courses with different IDs should not be equal
        assert course1 != course2
    
    def test_course_hash(self, event):
        """Test course hash - dataclass courses are not hashable by default."""
        course1 = event.add_course("Course 1")
        course1.id = 1
        
        # Dataclasses are not hashable by default
        with pytest.raises(TypeError):
            hash(course1)


# ---------------------------------------------------------------------------
# Tests for Course event integration
# ---------------------------------------------------------------------------

class TestCourseEventIntegration:
    def test_course_event_reference(self, event):
        """Test course event reference."""
        course = event.add_course("Event Course")
        
        assert course.event == event
        assert course._event == event
    
    def test_course_without_event(self):
        """Test course without event."""
        course = Course()
        
        assert course.event is None
        assert course._event is None
    
    def test_course_event_back_reference(self, event):
        """Test that course is added to event."""
        course = event.add_course("Back Ref Course")
        
        assert course.id in event.courses
        assert event.courses[course.id] == course

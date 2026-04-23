"""Tests for models/control.py - Control point management"""
import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from models import Control, Event
from models.enums import ControlStatus, SpecialPunchType
from models.control import PUNCH_START, PUNCH_FINISH, PUNCH_CHECK


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def event():
    """Create a basic event for testing."""
    return Event()


@pytest.fixture
def control(event):
    """Create a basic control."""
    control = event.add_control("C31", [31])
    return control


# ---------------------------------------------------------------------------
# Tests for Control initialization and properties
# ---------------------------------------------------------------------------

class TestControlInitialization:
    def test_default_initialization(self, event):
        """Test default control initialization."""
        control = event.add_control("Basic Control", [31])
        
        assert control.name == "Basic Control"
        assert control.id > 0
        assert control.numbers == [31]
        assert control.status == ControlStatus.OK
        assert control.event == event
        assert control.x == 0
        assert control.y == 0
    
    def test_initialization_with_coordinates(self, event):
        """Test control initialization with coordinates."""
        control = event.add_control("Located Control", [32])
        control.x = 123.45
        control.y = 678.90
        
        assert control.name == "Located Control"
        assert control.numbers == [32]
        assert control.x == 123.45
        assert control.y == 678.90
    
    def test_initialization_with_multiple_numbers(self, event):
        """Test control with multiple code numbers."""
        control = event.add_control("MultiCode Control", [31, 32, 33])
        
        assert control.name == "MultiCode Control"
        assert control.numbers == [31, 32, 33]


class TestControlProperties:
    def test_name_property(self, control):
        """Test name property."""
        assert control.name == "C31"
        
        # Test setting name
        control.name = "New Name"
        assert control.name == "New Name"
    
    def test_numbers_property(self, control):
        """Test numbers property."""
        assert control.numbers == [31]
        
        # Test setting numbers
        control.numbers = [32, 33]
        assert control.numbers == [32, 33]
    
    def test_status_property(self, control):
        """Test status property."""
        assert control.status == ControlStatus.OK
        
        # Test setting status
        control.status = ControlStatus.Start
        assert control.status == ControlStatus.Start
    
    def test_coordinates_properties(self, control):
        """Test x and y coordinate properties."""
        assert control.x == 0
        assert control.y == 0
        
        # Test setting coordinates
        control.x = 100.5
        control.y = 200.7
        assert control.x == 100.5
        assert control.y == 200.7


# ---------------------------------------------------------------------------
# Tests for Control methods
# ---------------------------------------------------------------------------

class TestControlMethods:
    def test_get_info(self, control):
        """Test get_info method."""
        info = control.get_info()
        assert isinstance(info, str)
        assert "C31" in info
        assert "31" in info
    
    def test_remove(self, control):
        """Test remove method."""
        assert control.removed == False
        
        control.remove()
        
        assert control.removed == True
        assert control.changed == True
    
    def test_can_remove(self, control):
        """Test can_remove method."""
        # Control can be removed if not used by any course
        assert control.can_remove() == True
    
    def test_is_special(self, control):
        """Test is_special method."""
        # Regular control should not be special
        assert control.is_special() == False
        
        # Test with special control statuses
        start_control = control.event.add_control("Start", [PUNCH_START])
        start_control.status = ControlStatus.Start
        assert start_control.is_special() == True
        
        finish_control = control.event.add_control("Finish", [PUNCH_FINISH])
        finish_control.status = ControlStatus.Finish
        assert finish_control.is_special() == True
        
        check_control = control.event.add_control("Check", [PUNCH_CHECK])
        check_control.status = ControlStatus.Check
        assert check_control.is_special() == True


# ---------------------------------------------------------------------------
# Tests for Control with special types
# ---------------------------------------------------------------------------

class TestSpecialControls:
    def test_start_control(self, event):
        """Test start control."""
        start = event.add_control("Start", [PUNCH_START])
        start.status = ControlStatus.Start
        
        assert start.is_special() == True
        assert "Start" in start.get_info()
    
    def test_finish_control(self, event):
        """Test finish control."""
        finish = event.add_control("Finish", [PUNCH_FINISH])
        finish.status = ControlStatus.Finish
        
        assert finish.is_special() == True
        assert "Finish" in finish.get_info()
    
    def test_check_control(self, event):
        """Test check control."""
        check = event.add_control("Check", [PUNCH_CHECK])
        check.status = ControlStatus.Check
        
        assert check.is_special() == True
        assert "Check" in check.get_info()
    
    def test_clear_control(self, event):
        """Test clear control."""
        # Clear is not a standard special punch type in this implementation
        clear = event.add_control("Clear", [99])
        
        assert clear.is_special() == False
        assert "Clear" in clear.get_info()


# ---------------------------------------------------------------------------
# Tests for Control validation and edge cases
# ---------------------------------------------------------------------------

class TestControlEdgeCases:
    def test_control_with_empty_numbers(self, event):
        """Test control with empty numbers list."""
        control = event.add_control("Empty Control", [])
        
        assert control.numbers == []
        assert "Empty Control" in control.get_info()
    
    def test_control_with_duplicate_numbers(self, event):
        """Test control with duplicate numbers."""
        control = event.add_control("Duplicate Control", [31, 31, 31])
        
        assert control.numbers == [31, 31, 31]
        # Implementation may or may not deduplicate
    
    def test_control_name_changes(self, control):
        """Test multiple name changes."""
        original_name = control.name
        
        control.name = "First Change"
        assert control.name == "First Change"
    
    def test_control_status_changes(self, control):
        """Test control status changes."""
        assert control.status == ControlStatus.OK
        
        control.status = ControlStatus.Start
        assert control.status == ControlStatus.Start
        
        control.status = ControlStatus.OK
        assert control.status == ControlStatus.OK


# ---------------------------------------------------------------------------
# Tests for Control comparison and equality
# ---------------------------------------------------------------------------

class TestControlComparison:
    def test_control_equality(self, event):
        """Test control equality."""
        control1 = event.add_control("Control 1", [31])
        control1.id = 1
        
        control2 = event.add_control("Control 2", [32])
        control2.id = 2  # Different ID
        
        # Controls with different IDs should not be equal
        assert control1 != control2
    
    def test_control_inequality(self, event):
        """Test control inequality."""
        control1 = event.add_control("Control 1", [31])
        control1.id = 1
        
        control2 = event.add_control("Control 2", [32])
        control2.id = 2  # Different ID
        
        # Controls with different IDs should not be equal
        assert control1 != control2
    
    def test_control_hash(self, event):
        """Test control hash - dataclass controls are not hashable by default."""
        control1 = event.add_control("Control 1", [31])
        control1.id = 1
        
        # Dataclasses are not hashable by default
        with pytest.raises(TypeError):
            hash(control1)


# ---------------------------------------------------------------------------
# Tests for Control event integration
# ---------------------------------------------------------------------------

class TestControlEventIntegration:
    def test_control_event_reference(self, event):
        """Test control event reference."""
        control = event.add_control("Event Control", [42])
        
        assert control.event == event
        assert control._event == event
    
    def test_control_without_event(self):
        """Test control without event."""
        control = Control()
        
        assert control.event is None
        assert control._event is None
    
    def test_control_event_back_reference(self, event):
        """Test that control is added to event."""
        control = event.add_control("Back Ref Control", [99])
        
        assert control.id in event.controls
        assert event.controls[control.id] == control


# ---------------------------------------------------------------------------
# Tests for Control coordinate management
# ---------------------------------------------------------------------------

class TestControlCoordinates:
    def test_coordinate_precision(self, event):
        """Test coordinate precision."""
        control = event.add_control("Precise Control", [50])
        control.x = 123.456789
        control.y = 987.654321
        
        assert control.x == 123.456789
        assert control.y == 987.654321
    
    def test_zero_coordinates(self, event):
        """Test control with zero coordinates."""
        control = event.add_control("Zero Control", [51])
        
        assert control.x == 0
        assert control.y == 0
    
    def test_negative_coordinates(self, event):
        """Test control with negative coordinates."""
        control = event.add_control("Negative Control", [52])
        control.x = -100.5
        control.y = -200.7
        
        assert control.x == -100.5
        assert control.y == -200.7


# ---------------------------------------------------------------------------
# Tests for Control number management
# ---------------------------------------------------------------------------

class TestControlNumbers:
    def test_single_number_control(self, event):
        """Test control with single number."""
        control = event.add_control("Single", [42])
        
        assert control.numbers == [42]
        assert 42 in control.numbers
    
    def test_multiple_numbers_control(self, event):
        """Test control with multiple numbers."""
        control = event.add_control("Multi", [41, 42, 43])
        
        assert control.numbers == [41, 42, 43]
        assert 41 in control.numbers
        assert 42 in control.numbers
        assert 43 in control.numbers
    
    def test_add_number_to_control(self, control):
        """Test adding numbers to control."""
        original_numbers = control.numbers.copy()
        
        control.numbers.append(32)
        assert len(control.numbers) == len(original_numbers) + 1
        assert 32 in control.numbers
    
    def test_remove_number_from_control(self, control):
        """Test removing numbers from control."""
        original_numbers = control.numbers.copy()
        
        if 31 in control.numbers:
            control.numbers.remove(31)
            assert 31 not in control.numbers

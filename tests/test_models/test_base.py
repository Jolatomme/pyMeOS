"""Tests for models/base.py - Base class functionality"""
import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from datetime import datetime, timezone
from models.base import Base
from models.event import Event


# ---------------------------------------------------------------------------
# Mock concrete implementation for testing
# ---------------------------------------------------------------------------

class TestObject(Base):
    """Concrete implementation of Base for testing."""
    
    def __init__(self, event=None, name="Test"):
        super().__init__(event)
        self.name = name
    
    def get_info(self) -> str:
        return f"TestObject: {self.name}"
    
    def remove(self) -> None:
        self._removed = True
        self.mark_changed()
    
    def can_remove(self) -> bool:
        return not self._removed


# ---------------------------------------------------------------------------
# Tests for Base class
# ---------------------------------------------------------------------------

class TestBaseInitialization:
    def test_default_initialization(self):
        """Test default Base initialization."""
        obj = TestObject()
        
        assert obj.id == 0
        assert obj.changed == False
        assert obj.removed == False
        assert obj.event is None
        assert obj.ext_id == 0
        assert isinstance(obj.modified, datetime)
    
    def test_initialization_with_event(self):
        """Test Base initialization with event."""
        event = Event()
        obj = TestObject(event=event)
        
        assert obj.event == event
        assert obj.id == 0
        assert obj.changed == False
    
    def test_initialization_with_name(self):
        """Test custom initialization."""
        obj = TestObject(name="Custom")
        assert obj.name == "Custom"


class TestBaseProperties:
    def test_id_property(self):
        """Test id property getter and setter."""
        obj = TestObject()
        
        # Test getter
        assert obj.id == 0
        
        # Test setter
        obj.id = 42
        assert obj.id == 42
    
    def test_event_property(self):
        """Test event property getter and setter."""
        obj = TestObject()
        event = Event()
        
        # Test getter
        assert obj.event is None
        
        # Test setter
        obj.event = event
        assert obj.event == event
    
    def test_modified_property(self):
        """Test modified property."""
        obj = TestObject()
        modified_time = obj.modified
        
        assert isinstance(modified_time, datetime)
        assert modified_time.tzinfo == timezone.utc
    
    def test_changed_property(self):
        """Test changed property."""
        obj = TestObject()
        assert obj.changed == False
    
    def test_removed_property(self):
        """Test removed property."""
        obj = TestObject()
        assert obj.removed == False
    
    def test_ext_id_property(self):
        """Test ext_id property getter and setter."""
        obj = TestObject()
        
        # Test getter
        assert obj.ext_id == 0
        
        # Test setter
        obj.ext_id = 123
        assert obj.ext_id == 123


class TestBaseMutationHelpers:
    def test_mark_changed(self):
        """Test mark_changed method."""
        obj = TestObject()
        original_modified = obj.modified
        
        # Mark as changed
        obj.mark_changed()
        
        assert obj.changed == True
        assert obj.modified > original_modified
    
    def test_clear_changed(self):
        """Test clear_changed method."""
        obj = TestObject()
        obj.mark_changed()
        
        assert obj.changed == True
        
        obj.clear_changed()
        
        assert obj.changed == False
    
    def test_on_changed_hook(self):
        """Test _on_changed hook."""
        class TrackingObject(TestObject):
            def __init__(self):
                super().__init__()
                self.change_count = 0
            
            def _on_changed(self):
                self.change_count += 1
        
        obj = TrackingObject()
        assert obj.change_count == 0
        
        obj.mark_changed()
        assert obj.change_count == 1
        
        obj.mark_changed()
        assert obj.change_count == 2


class TestBaseAbstractMethods:
    def test_get_info_implementation(self):
        """Test get_info method implementation."""
        obj = TestObject(name="TestObj")
        info = obj.get_info()
        
        assert isinstance(info, str)
        assert "TestObject: TestObj" == info
    
    def test_remove_implementation(self):
        """Test remove method implementation."""
        obj = TestObject()
        
        assert obj.removed == False
        assert obj.changed == False
        
        obj.remove()
        
        assert obj.removed == True
        assert obj.changed == True
    
    def test_can_remove_implementation(self):
        """Test can_remove method implementation."""
        obj = TestObject()
        
        # Should be removable when not removed
        assert obj.can_remove() == True
        
        # Should not be removable when already removed
        obj.remove()
        assert obj.can_remove() == False


class TestBaseUtilityMethods:
    def test_repr(self):
        """Test __repr__ method."""
        obj = TestObject()
        obj.id = 42
        
        repr_str = repr(obj)
        assert "TestObject" in repr_str
        assert "id=42" in repr_str
    
    def test_equality(self):
        """Test __eq__ method."""
        obj1 = TestObject()
        obj1.id = 1
        
        obj2 = TestObject()
        obj2.id = 1
        
        obj3 = TestObject()
        obj3.id = 2
        
        # Same class and ID should be equal
        assert obj1 == obj2
        
        # Different IDs should not be equal
        assert obj1 != obj3
        
        # Different classes should not be equal
        assert obj1 != "string"
        assert obj1 != 42
        assert obj1 != None
    
    def test_hash(self):
        """Test __hash__ method."""
        obj1 = TestObject()
        obj1.id = 1
        
        obj2 = TestObject()
        obj2.id = 1
        
        # Objects with same class and ID should have same hash
        assert hash(obj1) == hash(obj2)
        
        # Should be usable in sets/dicts
        obj_set = {obj1, obj2}
        assert len(obj_set) == 1  # Should deduplicate


class TestBaseEventIntegration:
    def test_event_back_reference(self):
        """Test event back-reference functionality."""
        event = Event()
        obj = TestObject(event=event)
        
        assert obj.event == event
        
        # Test that event reference is maintained
        assert obj._event == event
    
    def test_event_none_by_default(self):
        """Test that event is None by default."""
        obj = TestObject()
        assert obj.event is None
        assert obj._event is None


class TestBaseTimestamps:
    def test_modified_timestamp_on_init(self):
        """Test that modified timestamp is set on initialization."""
        before = datetime.now(timezone.utc)
        obj = TestObject()
        after = datetime.now(timezone.utc)
        
        assert before <= obj.modified <= after
    
    def test_modified_timestamp_on_change(self):
        """Test that modified timestamp updates on mark_changed."""
        obj = TestObject()
        first_modified = obj.modified
        
        # Small delay to ensure different timestamp
        import time
        time.sleep(0.001)
        
        obj.mark_changed()
        
        assert obj.modified > first_modified


class TestBaseEdgeCases:
    def test_multiple_mark_changed_calls(self):
        """Test multiple calls to mark_changed."""
        obj = TestObject()
        
        # Multiple calls should all work
        obj.mark_changed()
        obj.mark_changed()
        obj.mark_changed()
        
        assert obj.changed == True
    
    def test_clear_changed_when_not_changed(self):
        """Test clear_changed when object wasn't changed."""
        obj = TestObject()
        assert obj.changed == False
        
        # Should not raise error
        obj.clear_changed()
        assert obj.changed == False
    
    def test_remove_already_removed(self):
        """Test removing an already removed object."""
        obj = TestObject()
        obj.remove()
        
        assert obj.removed == True
        assert obj.changed == True
        
        # Removing again should still work
        obj.remove()
        assert obj.removed == True
        assert obj.changed == True

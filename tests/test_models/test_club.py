"""Tests for models/club.py - Club management"""
import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from models import Club, Event


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def event():
    """Create a basic event for testing."""
    return Event()


@pytest.fixture
def club(event):
    """Create a basic club."""
    return event.add_club("Test Club")


# ---------------------------------------------------------------------------
# Tests for Club initialization and properties
# ---------------------------------------------------------------------------

class TestClubInitialization:
    def test_default_initialization(self, event):
        """Test default club initialization."""
        club = event.add_club("Basic Club")
        
        assert club.name == "Basic Club"
        assert club.id > 0
        assert club.short_name == ""
        assert club.country == ""
        assert club.nationality_code == ""
        assert club.event == event
    
    def test_initialization_with_parameters(self, event):
        """Test club initialization with parameters."""
        # The new API only takes name parameter
        club = event.add_club("Full Club")
        club.short_name = "FC"
        club.country = "USA"
        club.nationality_code = "Northeast"
        
        assert club.name == "Full Club"
        assert club.short_name == "FC"
        assert club.country == "USA"
        assert club.nationality_code == "Northeast"


class TestClubProperties:
    def test_name_property(self, club):
        """Test name property."""
        assert club.name == "Test Club"
        
        club.name = "New Name"
        assert club.name == "New Name"
    
    def test_short_name_property(self, club):
        """Test short_name property."""
        assert club.short_name == ""
        
        club.short_name = "TC"
        assert club.short_name == "TC"
    
    def test_nationality_code_property(self, club):
        """Test nationality_code property."""
        assert club.nationality_code == ""
        
        club.nationality_code = "CAN"
        assert club.nationality_code == "CAN"
    
    def test_country_property(self, club):
        """Test country property."""
        assert club.country == ""
        
        club.country = "West"
        assert club.country == "West"


class TestClubMethods:
    def test_get_info(self, club):
        """Test get_info method."""
        info = club.get_info()
        assert isinstance(info, str)
        assert "Test Club" in info
    
    def test_remove(self, club):
        """Test remove method."""
        assert club.removed == False
        
        club.remove()
        
        assert club.removed == True
        assert club.changed == True
    
    def test_can_remove(self, club):
        """Test can_remove method."""
        # Club can be removed if not used by any runners
        assert club.can_remove() == True
        
        club.remove()
        # After removal, can_remove should still return True since it only checks if club is used
        assert club.can_remove() == True


class TestClubEdgeCases:
    def test_club_with_empty_fields(self, event):
        """Test club with empty fields."""
        club = event.add_club("")
        
        assert club.name == ""
        assert club.short_name == ""
        assert club.country == ""
        assert club.nationality_code == ""
    
    def test_club_name_changes(self, club):
        """Test multiple name changes."""
        original_name = club.name
        
        club.name = "First Change"
        assert club.name == "First Change"
        
        club.name = "Second Change"
        assert club.name == "Second Change"
    
    def test_club_short_name_changes(self, club):
        """Test short_name changes."""
        club.short_name = "TC"
        assert club.short_name == "TC"
        
        club.short_name = "TST"
        assert club.short_name == "TST"


class TestClubComparison:
    def test_club_equality(self, event):
        """Test club equality."""
        club1 = event.add_club("Club 1")
        club1.id = 1
        
        club2 = event.add_club("Club 2")
        club2.id = 2
        
        # Clubs with different IDs should not be equal
        assert club1 != club2
    
    def test_club_hash(self, event):
        """Test club hash - dataclass clubs are not hashable by default."""
        club = event.add_club("Test Club")
        
        # Dataclasses are not hashable by default
        with pytest.raises(TypeError):
            hash(club)


class TestClubEventIntegration:
    def test_club_event_reference(self, event):
        """Test club event reference."""
        club = event.add_club("Event Club")
        
        assert club.event == event
        assert club._event == event
    
    def test_club_event_back_reference(self, event):
        """Test that club is added to event."""
        club = event.add_club("Back Ref Club")
        
        assert club.id in event.clubs
        assert event.clubs[club.id] == club


class TestClubWithRunners:
    def test_club_used_by_runners(self, event):
        """Test club that has runners."""
        club = event.add_club("Runner Club")
        
        # Add a runner to the club
        runner = event.add_runner("John", "Doe", club_id=club.id)
        
        # Club should NOT be removable if it has runners
        assert club.can_remove() == False


class TestClubInfoFormats:
    def test_club_info_with_all_fields(self, event):
        """Test get_info with all fields populated."""
        club = event.add_club("Full Club")
        club.short_name = "FC"
        club.country = "USA"
        
        info = club.get_info()
        assert "Full Club" in info
        assert "USA" in info
    
    def test_club_info_with_minimal_fields(self, club):
        """Test get_info with minimal fields."""
        info = club.get_info()
        assert "Test Club" in info
        # Should still work with empty optional fields
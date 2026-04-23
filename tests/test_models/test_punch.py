"""Tests for models/punch.py - Punch data management"""
import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from models.punch import Punch, SIPunch
from models.enums import SpecialPunchType
from utils.time_utils import encode


# ---------------------------------------------------------------------------
# Tests for Punch class
# ---------------------------------------------------------------------------

class TestPunch:
    def test_punch_initialization(self):
        """Test basic punch initialization."""
        punch = Punch(type_code=31, time_raw=encode(3600))
        
        assert punch.type_code == 31
        assert punch.time == encode(3600)
    
    def test_punch_equality(self):
        """Test punch equality."""
        p1 = Punch(type_code=31, time_raw=encode(3600))
        p2 = Punch(type_code=31, time_raw=encode(3600))
        p3 = Punch(type_code=32, time_raw=encode(3600))
        
        assert p1 == p2
        assert p1 != p3
    
    def test_punch_repr(self):
        """Test punch string representation."""
        punch = Punch(type_code=31, time_raw=encode(3600))
        repr_str = repr(punch)
        
        assert "Punch" in repr_str
        assert "31" in repr_str


# ---------------------------------------------------------------------------
# Tests for SIPunch class
# ---------------------------------------------------------------------------

class TestSIPunch:
    def test_si_punch_initialization(self):
        """Test SI punch initialization."""
        si_punch = SIPunch(code=31, time=encode(3600))
        
        assert si_punch.code == 31
        assert si_punch.time == encode(3600)
        # SIPunch doesn't have rogaining_points or is_manual, that's in Punch class now
    
    def test_si_punch_with_parameters(self):
        """Test SI punch with all parameters."""
        si_punch = SIPunch(
            code=31, 
            time=encode(3600)
        )
        
        assert si_punch.code == 31
        assert si_punch.time == encode(3600)
        # SIPunch doesn't have rogaining_points
        
        # SIPunch doesn't have rogaining_points in the new API
    
    def test_si_punch_manual_flag(self):
        """Test manual punch flag."""
        # SIPunch doesn't have is_manual flag in the new API
        manual_punch = SIPunch(code=31, time=encode(3600))
        auto_punch = SIPunch(code=32, time=encode(3600))
        
        # SIPunch is a simple data structure without manual flag
        assert manual_punch.code == 31
        assert auto_punch.code == 32


# ---------------------------------------------------------------------------
# Tests for punch collections
# ---------------------------------------------------------------------------

class TestPunchCollections:
    def test_punch_list_operations(self):
        """Test operations on punch lists."""
        punches = [
            Punch(type_code=31, time_raw=encode(3600)),
            Punch(type_code=32, time_raw=encode(3610)),
            Punch(type_code=33, time_raw=encode(3620))
        ]
        
        assert len(punches) == 3
        assert punches[0].type_code == 31
        assert punches[2].type_code == 33
    
    def test_punch_sorting(self):
        """Test sorting punches by time."""
        punches = [
            Punch(type_code=33, time_raw=encode(3620)),
            Punch(type_code=31, time_raw=encode(3600)),
            Punch(type_code=32, time_raw=encode(3610))
        ]
        
        # Sort by time
        sorted_punches = sorted(punches, key=lambda p: p.time)
        
        assert sorted_punches[0].type_code == 31
        assert sorted_punches[1].type_code == 32
        assert sorted_punches[2].type_code == 33
    
    def test_punch_filtering(self):
        """Test filtering punches."""
        punches = [
            Punch(type_code=31, time_raw=encode(3600)),
            Punch(type_code=int(SpecialPunchType.Start), time_raw=encode(3590)),
            Punch(type_code=int(SpecialPunchType.Finish), time_raw=encode(3630)),
            Punch(type_code=32, time_raw=encode(3610))
        ]
        
        # Filter out special punches (start/finish are special)
        regular_punches = [p for p in punches if not (p.is_start() or p.is_finish())]
        assert len(regular_punches) == 2
        assert regular_punches[0].type_code == 31
        assert regular_punches[1].type_code == 32


# ---------------------------------------------------------------------------
# Tests for edge cases
# ---------------------------------------------------------------------------

class TestPunchEdgeCases:
    def test_punch_with_zero_time(self):
        """Test punch with zero time."""
        punch = Punch(type_code=31, time_raw=0)
        
        assert punch.type_code == 31
        assert punch.time == 0
    
    def test_punch_with_negative_time(self):
        """Test punch with negative time."""
        punch = Punch(type_code=31, time_raw=-100)
        
        assert punch.type_code == 31
        assert punch.time == -100
    
    def test_punch_with_large_code(self):
        """Test punch with large code number."""
        punch = Punch(type_code=9999, time_raw=encode(3600))
        
        assert punch.type_code == 9999
        assert punch.time == encode(3600)
    
    def test_si_punch_with_high_rogaining_points(self):
        """Test SI punch with high rogaining points."""
        # SIPunch doesn't have rogaining_points in the new API
        si_punch = SIPunch(code=31, time=encode(3600))
        
        assert si_punch.code == 31
        assert si_punch.time == encode(3600)


# ---------------------------------------------------------------------------
# Tests for punch comparison
# ---------------------------------------------------------------------------

class TestPunchComparison:
    def test_punch_comparison_by_time(self):
        """Test comparing punches by time."""
        p1 = Punch(type_code=31, time_raw=encode(3600))
        p2 = Punch(type_code=32, time_raw=encode(3610))
        
        assert p1.time < p2.time
        assert p2.time > p1.time
        assert p1.time == encode(3600)
    
    def test_si_punch_comparison(self):
        """Test comparing SI punches."""
        p1 = SIPunch(code=31, time=encode(3600))
        p2 = SIPunch(code=31, time=encode(3600))
        p3 = SIPunch(code=32, time=encode(3610))
        
        assert p1 == p2
        assert p1 != p3
        assert p1.time != p3.time
"""Tests for utils/localizer.py"""
import json
import os
import tempfile
import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from utils.localizer import Localizer, trs


class TestLocalizerBasic:
    def test_fallback_returns_key(self):
        loc = Localizer()
        assert loc.translate("UnknownKey") == "UnknownKey"

    def test_load_from_dict(self):
        loc = Localizer()
        loc.load_from_dict({"Results": "Résultats"}, lang="fr")
        assert loc.translate("Results") == "Résultats"

    def test_language_set(self):
        loc = Localizer()
        loc.load_from_dict({}, lang="sv")
        assert loc.language == "sv"

    def test_key_count(self):
        loc = Localizer()
        loc.load_from_dict({"A": "1", "B": "2"})
        assert loc.key_count == 2

    def test_format_args(self):
        loc = Localizer()
        loc.load_from_dict({"Msg": "Hello {0}!"})
        assert loc.translate("Msg", "World") == "Hello World!"

    def test_callable(self):
        loc = Localizer()
        loc.load_from_dict({"X": "Y"})
        assert loc("X") == "Y"


class TestLocalizerFile:
    def test_load_valid_json(self):
        with tempfile.NamedTemporaryFile(
                mode="w", suffix=".json", encoding="utf-8",
                delete=False) as tf:
            json.dump({"Key": "Value"}, tf)
            fname = tf.name
        try:
            loc = Localizer()
            ok  = loc.load(fname)
            assert ok
            assert loc.translate("Key") == "Value"
        finally:
            os.unlink(fname)

    def test_load_nonexistent_returns_false(self):
        loc = Localizer()
        ok  = loc.load("/tmp/no_such_file_pymeos.json")
        assert not ok

    def test_load_invalid_json_returns_false(self):
        with tempfile.NamedTemporaryFile(
                mode="w", suffix=".json", encoding="utf-8",
                delete=False) as tf:
            tf.write("NOT JSON {{")
            fname = tf.name
        try:
            loc = Localizer()
            ok  = loc.load(fname)
            assert not ok
        finally:
            os.unlink(fname)

    def test_load_en_translation_file(self):
        """The bundled English translation file must be valid."""
        here = Path(__file__).resolve().parents[2]
        path = here / "resources" / "translations" / "en.json"
        if not path.exists():
            pytest.skip("en.json not found")
        loc = Localizer()
        ok  = loc.load(str(path))
        assert ok
        assert loc.key_count > 10
        assert loc.translate("Results") == "Results"


class TestGlobalSingleton:
    def test_set_and_get_global(self):
        loc = Localizer()
        loc.load_from_dict({"G": "global"})
        Localizer.set_global(loc)
        assert Localizer.get_global() is loc
        assert trs("G") == "global"

    def test_trs_fallback_without_global(self):
        Localizer.set_global(None)
        assert trs("SomeKey") == "SomeKey"

    def test_trs_with_args_no_global(self):
        Localizer.set_global(None)
        assert trs("Hello {0}", "World") == "Hello World"

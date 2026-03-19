"""
utils/localizer.py
==================
Lightweight localiser – translates UI strings the same way MeOS's
Localizer class does (key → translated string).

Loads translations from a JSON dictionary file.  Falls back to the key
itself when no translation is found (so the app always displays something
intelligible without translations).

Usage::

    from utils.localizer import Localizer, trs

    lang = Localizer()
    lang.load("resources/translations/en.json")
    Localizer.set_global(lang)
    print(trs("Results"))   # → "Results"
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, Optional

log = logging.getLogger(__name__)

# Module-level singleton – set by Localizer.set_global()
_instance: Optional["Localizer"] = None


def trs(key: str, *args) -> str:
    """Short-hand: translate *key*, optionally format with *args*.

    >>> trs("Results")
    'Results'
    """
    if _instance is None:
        return key.format(*args) if args else key
    return _instance.translate(key, *args)


class Localizer:
    """Translates string keys to localised strings."""

    def __init__(self) -> None:
        self._table: Dict[str, str] = {}
        self._lang: str = "en"

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def load(self, path: str | Path, language: str = "") -> bool:
        """Load a JSON translation file. Returns True on success."""
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
            if not isinstance(data, dict):
                log.warning("Translation file %s has wrong format", path)
                return False
            self._table = {str(k): str(v) for k, v in data.items()}
            self._lang  = language or Path(path).stem
            log.info("Loaded %d translations from %s", len(self._table), path)
            return True
        except FileNotFoundError:
            log.warning("Translation file not found: %s", path)
            return False
        except (json.JSONDecodeError, OSError) as exc:
            log.warning("Cannot load translation file %s: %s", path, exc)
            return False

    def load_from_dict(self, data: dict, lang: str = "custom") -> None:
        """Populate translations directly from a Python dict."""
        self._table = {str(k): str(v) for k, v in data.items()}
        self._lang  = lang

    # ------------------------------------------------------------------
    # Translation
    # ------------------------------------------------------------------

    def translate(self, key: str, *args) -> str:
        """Return the translated string for *key*.

        Falls back to *key* itself if no translation exists.
        *args* are applied via ``str.format`` to the result.
        """
        text = self._table.get(key, key)
        if args:
            try:
                text = text.format(*args)
            except (IndexError, KeyError):
                pass
        return text

    def __call__(self, key: str, *args) -> str:
        return self.translate(key, *args)

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def language(self) -> str:
        return self._lang

    @property
    def key_count(self) -> int:
        return len(self._table)

    # ------------------------------------------------------------------
    # Global singleton management
    # ------------------------------------------------------------------

    @classmethod
    def set_global(cls, instance: "Optional[Localizer]") -> None:
        """Install *instance* as the global singleton used by :func:`trs`."""
        global _instance
        _instance = instance

    @classmethod
    def get_global(cls) -> "Optional[Localizer]":
        return _instance

# AGENTS.md – PyMeOS

## Key Commands

```bash
# Run app
python main.py --db sqlite:///event.db --open competition.mexml --log-level DEBUG

# Non-Qt tests (CI-safe, no display needed)
pytest tests/test_models tests/test_controllers/test_draw.py tests/test_controllers/test_result_calculator.py tests/test_io tests/test_hardware/test_si_card.py -v

# Qt-dependent tests (needs display/Xvfb)
pytest tests/test_hardware/test_si_reader.py tests/test_controllers/test_competition.py tests/test_views/ -v
```

## Architecture

- **Entry point**: `main.py`
- **MVC structure**: `models/` (domain), `controllers/` (logic), `views/` (PySide6 GUI)
- **Sub-packages**: `hardware/` (SI reader), `formats/` (IOF XML, MeOS XML, CSV), `network/` (REST API), `persistence/` (SQLAlchemy), `utils/` (time, i18n)

## Critical Details

- **Time units**: Internal times are in **tenths-of-seconds** (1 unit = 0.1s). Use `utils/time_utils.py` for encoding/formatting.
- **Qt environment tweaks**: Must happen before `QApplication` (see `main.py:29-42`)
- **Test mode for SI reader**: `SIReaderManager().open_port("TEST", test_mode=True)` — no hardware needed
- **SQLite default**: DB created in current directory unless `--db` specified

## Test Organization

- `tests/test_models/` – pure Python, always runnable
- `tests/test_controllers/test_draw.py`, `test_result_calculator.py` – pure Python
- `tests/test_hardware/test_si_reader.py`, `tests/test_controllers/test_competition.py`, `tests/test_views/` – require Qt + display/Xvfb

## Dependencies

- Runtime: PySide6>=6.7, SQLAlchemy>=2.0, pyserial, lxml, flask
- Dev: pytest, pytest-qt, pytest-cov (Qt tests need `--platform offscreen` via `qt_qapp_args` in pyproject.toml)
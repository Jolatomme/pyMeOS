# PyMeOS – Cross-Platform Orienteering Software

PyMeOS is a Python/PySide6 port of [MeOS](https://www.melin.nu/meos/) (Melin Software HB), an orienteering event management system.  The original is a Windows-only C++ application; PyMeOS runs on **Windows, macOS, and Linux**.

---

## Features

| Feature | Details |
|---|---|
| **Event management** | Create / open / save competitions in MeOS XML format |
| **Runners & teams** | Full CRUD for individual and relay entries |
| **Classes & courses** | Multi-leg relay, rogaining, and standard classes |
| **SI card reading** | SportIdent reader via `pyserial` (COM/USB), extended protocol SI5/6/8/9/10/11/SIAC |
| **Test / simulation mode** | Built-in synthetic card generator — no hardware needed |
| **Result calculation** | Mispunch detection, DNF/DNS/DQ/MAX status, places, relay team totals |
| **Start draw** | Sequential, randomised, club-separated, pursuit starts |
| **IOF XML 3.0** | Import/export EntryList, CourseData, ResultList |
| **CSV import/export** | Start lists and result sheets |
| **REST API** | Lightweight Flask server (`/api/runners`, `/api/results/<class_id>`, …) |
| **Speaker monitor** | Live leaderboard that auto-refreshes |
| **Automation** | Configurable periodic backup and live-result upload |
| **Database** | SQLite (default) or MySQL via SQLAlchemy |
| **Internationalisation** | JSON-based locale files (same key scheme as MeOS) |

---

## Architecture (MVC)

```
pymeos/
├── main.py                    # Entry point
├── models/                    # MODEL – pure-Python domain objects
│   ├── event.py               # Central registry (oEvent equivalent)
│   ├── runner.py              # Competitor (oRunner)
│   ├── team.py                # Relay team (oTeam)
│   ├── class_.py              # Competition class (oClass)
│   ├── course.py              # Map course (oCourse)
│   ├── control.py             # Control point (oControl)
│   ├── club.py                # Club / organisation (oClub)
│   ├── card.py                # SI card read-out (oCard / SICard)
│   ├── punch.py               # Single punch (oPunch / SIPunch)
│   └── enums.py               # RunnerStatus, ControlStatus, SortOrder, …
│
├── controllers/               # CONTROLLER – business logic, no Qt
│   ├── competition.py         # CompetitionController (main app controller)
│   ├── result.py              # Card evaluation, result calculation
│   ├── draw.py                # Start time assignment and draw
│   ├── speaker.py             # Live speaker timeline
│   └── automation.py         # Periodic background tasks
│
├── views/                     # VIEW – PySide6 GUI
│   ├── main_window.py         # QMainWindow + menus + tabs
│   └── tabs/
│       ├── tab_competition.py # New/open/save competition
│       ├── tab_runner.py      # Runner list + editor
│       ├── tab_team.py        # Relay team management
│       ├── tab_class.py       # Class configuration
│       ├── tab_course.py      # Course editor
│       ├── tab_control.py     # Control point editor
│       ├── tab_club.py        # Club management
│       ├── tab_si.py          # SI card reader + manual entry
│       ├── tab_results.py     # Results display
│       ├── tab_speaker.py     # Live speaker monitor
│       └── tab_auto.py        # Automation settings
│
├── hardware/                  # SI reader hardware layer
│   ├── si_reader.py           # SIReaderManager, QThread workers
│   ├── si_card.py             # CRC helpers, SI5/6/8/9 parsers
│   └── si_protocol.py        # Low-level frame building
│
├── formats/                   # File import / export
│   ├── iof30.py               # IOF XML 3.0
│   ├── xml_parser.py          # MeOS native .mexml format
│   └── csv_parser.py          # CSV entry lists and results
│
├── network/
│   └── rest_server.py         # Flask REST API server
│
├── persistence/
│   ├── database.py            # SQLAlchemy engine + session
│   ├── orm_models.py          # ORM mapped tables
│   └── event_repo.py          # EventRepository (CRUD)
│
├── utils/
│   ├── time_utils.py          # Internal time units (1 unit = 0.1 s)
│   └── localizer.py           # i18n helpers
│
└── tests/                     # pytest test suite (197+ tests)
    ├── test_models/
    ├── test_controllers/
    ├── test_hardware/
    └── test_io/
```

---

## Installation

### Requirements
- Python 3.11+
- PySide6 6.7+ (for the GUI)
- pyserial (for SI hardware)
- SQLAlchemy 2.0+
- lxml (for IOF XML)
- Flask + flask-cors (for REST server)

```bash
git clone https://github.com/yourorg/pymeos.git
cd pymeos
pip install -r requirements.txt
```

### Running

```bash
# Launch with default SQLite database
python main.py

# Custom database path
python main.py --db sqlite:///my_event.db

# MySQL
python main.py --db mysql+pymysql://user:password@localhost/meos

# Open a competition file on startup
python main.py --open competition.mexml

# Verbose logging
python main.py --log-level DEBUG
```

---

## Running the Tests

```bash
# All non-Qt tests (no display needed — works in CI)
pytest tests/test_models tests/test_controllers/test_draw.py \
       tests/test_controllers/test_result_calculator.py \
       tests/test_io tests/test_hardware/test_si_card.py -v

# Qt-dependent tests (requires PySide6 and a display or Xvfb)
pytest tests/test_hardware/test_si_reader.py \
       tests/test_controllers/test_competition.py \
       tests/test_views/ -v

# Everything with coverage
pip install pytest-cov pytest-qt
pytest --cov=. --cov-report=html
```

---

## SI Reader Usage

```python
from hardware.si_reader import SIReaderManager

mgr = SIReaderManager()

# List available serial ports
print(SIReaderManager.list_serial_ports())

# Open a real SI station
mgr.open_port("/dev/ttyUSB0")          # Linux/macOS
mgr.open_port("COM3")                  # Windows

# Simulation mode (no hardware needed)
mgr.open_port("TEST", test_mode=True)

# Connect signals
mgr.card_received.connect(on_card)     # SICard object
mgr.error.connect(on_error)            # (port, message)
```

---

## REST API

Start the server from code:

```python
from network.rest_server import RestServer
srv = RestServer()
srv.start(event, port=2009, allow_entries=True)
```

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/event` | Event metadata + statistics |
| GET | `/api/classes` | All classes |
| GET | `/api/runners?class_id=N` | All runners (optional class filter) |
| GET | `/api/runner/<id>` | Single runner |
| GET | `/api/results/<class_id>` | Sorted results for a class |
| GET | `/api/startlist/<class_id>` | Start list for a class |
| POST | `/api/entry` | Add a new entry (if enabled) |
| GET | `/api/status` | Server health check |

---

## IOF XML 3.0

```python
from formats.iof30 import import_iof30, export_result_list_to_file

# Import an entry list or course data
import_iof30("entries.xml", event)

# Export results
export_result_list_to_file(event, "results.xml")
```

---

## Time Representation

All times are stored internally as **tenth-of-seconds** (same as MeOS):

```
1 internal unit = 0.1 seconds
encode(90.0) == 900  (1 minute 30 seconds)
format_time(900) == "1:30"
parse_time("1:30") == 900
```

---

## Licence
GNU Affero General Public License v3.0 – same as the original MeOS.  
Original C++ code © 2009–2026 Melin Software HB.

# Contributing to pyMeOS

Thank you for your interest in contributing to pyMeOS! This document provides guidelines to help you get started and ensure a smooth contribution process.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Making Changes](#making-changes)
- [Code Style & Standards](#code-style--standards)
- [Testing](#testing)
- [Commit Messages](#commit-messages)
- [Pull Requests](#pull-requests)
- [Architecture & Design](#architecture--design)
- [Documentation](#documentation)
- [Reporting Issues](#reporting-issues)
- [Getting Help](#getting-help)

---

## Code of Conduct

We are committed to providing a welcoming and inclusive environment for all contributors. Please read and adhere to our [Code of Conduct](CODE_OF_CONDUCT.md).

---

## Getting Started

### Prerequisites

- Python 3.11 or later
- Git
- Basic understanding of the MVC architecture used in pyMeOS
- Familiarity with orienteering concepts is helpful but not required

### Fork & Clone

1. Fork the repository on GitHub
2. Clone your fork locally:
   ```bash
   git clone https://github.com/YOUR_USERNAME/pyMeOS.git
   cd pyMeOS
   ```
3. Add the upstream repository as a remote:
   ```bash
   git remote add upstream https://github.com/Jolatomme/pyMeOS.git
   ```

---

## Development Setup

### Environment

1. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   pip install -r requirements-dev.txt  # For development tools
   ```

3. Install pre-commit hooks (optional but recommended):
   ```bash
   pre-commit install
   ```

### Running the Application

```bash
python main.py
```

For development with verbose logging:
```bash
python main.py --log-level DEBUG
```

---

## Making Changes

### Branch Naming

Use descriptive branch names that reference the issue or feature:

```bash
git checkout -b feature/add-csv-import
git checkout -b bugfix/fix-si-reader-crash
git checkout -b docs/update-api-documentation
```

### Architecture Overview

pyMeOS follows an **MVC (Model-View-Controller)** pattern:

- **Models** (`pymeos/models/`): Pure Python domain objects representing the core business logic
- **Controllers** (`pymeos/controllers/`): Business logic and operations
- **Views** (`pymeos/views/`): PySide6 GUI components
- **Hardware** (`pymeos/hardware/`): SI card reader integration
- **Persistence** (`pymeos/persistence/`): Database operations via SQLAlchemy
- **Formats** (`pymeos/formats/`): File import/export (IOF XML, CSV, MeOS XML)
- **Network** (`pymeos/network/`): REST API via Flask

### Where to Make Changes

- **Bug fix in result calculation?** → `pymeos/controllers/result.py`
- **New runner property?** → `pymeos/models/runner.py`
- **GUI feature?** → `pymeos/views/tabs/`
- **SI reader issue?** → `pymeos/hardware/si_reader.py`
- **Database persistence?** → `pymeos/persistence/`
- **REST API endpoint?** → `pymeos/network/rest_server.py`

---

## Code Style & Standards

### Python Style

Follow **PEP 8** with these conventions:

- Line length: **100 characters**
- Use **type hints** for all function parameters and return types
- Use **docstrings** (Google style) for all public classes and methods
- Use **snake_case** for variables and functions, **PascalCase** for classes

### Type Hints Example

```python
from typing import Optional, List

def calculate_result(
    runner_id: int, 
    punches: List[int], 
    max_time: Optional[int] = None
) -> dict[str, any]:
    """
    Calculate the result for a runner based on their punches.
    
    Args:
        runner_id: The unique identifier for the runner
        punches: List of control punches in seconds
        max_time: Maximum allowed time in seconds (optional)
    
    Returns:
        A dictionary containing the result status and time
    """
    pass
```

### Docstring Example

```python
class Runner:
    """Represents a competitor in an orienteering event."""
    
    def __init__(self, runner_id: int, name: str, club: Optional[str] = None):
        """
        Initialize a new runner.
        
        Args:
            runner_id: Unique runner identifier
            name: Full name of the runner
            club: Club or organization name (optional)
        """
        self.id = runner_id
        self.name = name
        self.club = club
```

### Code Quality Tools

We recommend using:

```bash
# Format code
black pymeos/ --line-length 100

# Lint
flake8 pymeos/

# Type checking
mypy pymeos/

# Sort imports
isort pymeos/
```

---

## Testing

### Test Structure

Tests are organized in `tests/` mirroring the source structure:

```
tests/
├── test_models/          # Model unit tests
├── test_controllers/     # Controller unit tests
├── test_hardware/        # Hardware/SI reader tests
├── test_io/              # File format tests
└── test_views/           # GUI tests (optional, requires display)
```

### Writing Tests

Use **pytest** with descriptive test names:

```python
def test_runner_status_calculation_with_valid_punches():
    """Test that runner status is correctly calculated for valid punch sequences."""
    runner = Runner(1, "John Doe", "ABC Club")
    punches = [100, 200, 300, 400]
    
    result = calculate_runner_status(runner, punches)
    
    assert result.status == RunnerStatus.OK
    assert result.time == 400


def test_si_card_crc_validation_with_corrupted_data():
    """Test that corrupted SI card data fails CRC validation."""
    corrupted_data = bytes([0x02, 0xFF, 0x00, 0x01])  # Invalid checksum
    
    is_valid = verify_si_card_crc(corrupted_data)
    
    assert is_valid is False
```

### Running Tests

```bash
# Run all non-Qt tests (CI-safe)
pytest tests/test_models tests/test_controllers/test_draw.py \
       tests/test_controllers/test_result_calculator.py \
       tests/test_io tests/test_hardware/test_si_card.py -v

# Run all tests (requires display)
pytest tests/ -v

# Run with coverage
pytest --cov=pymeos --cov-report=html tests/

# Run a specific test file
pytest tests/test_models/test_runner.py -v

# Run a specific test
pytest tests/test_models/test_runner.py::test_runner_creation -v
```

### Coverage Requirements

- Aim for **80%+ code coverage** on new code
- Critical business logic (controllers, models) should have **>90% coverage**
- View code (GUI) has relaxed requirements but core functionality should be tested

### GitHub Actions CI

All pull requests run through:

1. Unit tests (pytest)
2. Code style checks (flake8, black)
3. Type checking (mypy)
4. Coverage reports

Your PR must pass all checks before merging.

---

## Commit Messages

Follow the **Conventional Commits** format:

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Type

- `feat`: A new feature
- `fix`: A bug fix
- `docs`: Documentation only
- `style`: Code style changes (formatting, missing semicolons, etc.)
- `refactor`: Code refactoring without feature changes
- `perf`: Performance improvements
- `test`: Adding or updating tests
- `ci`: CI/CD configuration changes
- `chore`: Maintenance, dependency updates

### Scope

The module or component affected:
- `runner`, `team`, `class`, `course`, `card`
- `si-reader`, `result-calc`, `draw`, `rest-api`
- `orm`, `iof30`, `csv`

### Examples

```
feat(si-reader): add support for SIAC cards

Implement SIAC protocol handling in SIReaderManager
to support new Si Air cards. Includes frame parsing
and CRC validation.

Closes #123
```

```
fix(result-calc): correct mispunch detection logic

Previously, mispunches at the first control were
not being detected. Fixed the boundary condition
in detect_mispunches().

Fixes #456
```

```
docs(api): update REST endpoint examples

Added curl examples for all /api/* endpoints.
```

---

## Pull Requests

### Before Submitting

1. **Update your branch** with the latest upstream changes:
   ```bash
   git fetch upstream
   git rebase upstream/master
   ```

2. **Run tests locally**:
   ```bash
   pytest tests/ -v
   pytest --cov=pymeos tests/
   ```

3. **Check code style**:
   ```bash
   black pymeos/ --check --line-length 100
   flake8 pymeos/
   mypy pymeos/
   ```

4. **Ensure no merge conflicts**

### PR Title & Description

Use a clear, descriptive title following the Conventional Commits format:

```
feat(runner): add bulk import from CSV
```

Provide a detailed description:

```markdown
## Description

This PR adds the ability to import runners in bulk from a CSV file.

## Motivation

Users currently must manually enter each runner. This feature allows
importing a CSV file from common online entry systems (Eventor, etc.).

## Changes

- Add `BulkImportDialog` in tab_runner.py
- Extend RunnerController with import_csv_bulk() method
- Handle duplicate bib numbers and name conflicts

## Related Issues

Closes #789

## Testing

- [x] Added unit tests for CSV parsing
- [x] Added integration tests for duplicate detection
- [x] Manual testing with Eventor sample files
- [x] Coverage: 87%

## Screenshots

[If applicable, add screenshots of new UI]

## Checklist

- [x] Code follows style guidelines
- [x] All tests pass
- [x] Documentation updated
- [x] No breaking changes
```

### Review Process

1. **Automatic checks** run (tests, linting, coverage)
2. **Code review** by maintainers
3. **Requested changes** (if any) — commit fixes and push again
4. **Approval** and merge

### Addressing Feedback

- Make requested changes in new commits (don't force push)
- Re-request review after updates
- Discuss disagreements respectfully

---

## Architecture & Design

### Model Layer

Models should:

- Be **immutable when possible** (use `__slots__` for performance)
- Contain **no business logic** (only data + getters/setters)
- Use **descriptive properties** with type hints
- Not depend on views or controllers

```python
class Runner:
    __slots__ = ('_id', '_name', '_bib', '_status', '_time')
    
    def __init__(self, runner_id: int, name: str, bib: int):
        self._id = runner_id
        self._name = name
        self._bib = bib
        self._status = RunnerStatus.OK
        self._time = 0
    
    @property
    def id(self) -> int:
        return self._id
    
    @property
    def status(self) -> RunnerStatus:
        return self._status
    
    @status.setter
    def status(self, value: RunnerStatus) -> None:
        self._status = value
```

### Controller Layer

Controllers should:

- Orchestrate **business logic** and model updates
- Be **testable without GUI** (use dependency injection)
- Emit **signals/events** for view updates
- Handle **validation** and **error cases**

```python
class RunnerController:
    def __init__(self, event: Event):
        self.event = event
    
    def create_runner(
        self, 
        name: str, 
        bib: int, 
        club_id: Optional[int] = None
    ) -> Runner:
        """Create and register a new runner."""
        if not name or not name.strip():
            raise ValueError("Runner name cannot be empty")
        
        if self.event.get_runner_by_bib(bib):
            raise ValueError(f"Bib {bib} already exists")
        
        runner = Runner(self.event.next_runner_id(), name, bib)
        self.event.register_runner(runner)
        return runner
```

### View Layer

Views should:

- Be **thin** (mostly UI rendering)
- Not contain **business logic**
- Use **controllers** to perform actions
- Update based on **model changes** (signals)

---

## Documentation

### Code Documentation

- Add **docstrings** to all public functions and classes
- Update docstrings when behavior changes
- Include **examples** in docstrings for complex functions

### API Documentation

- Document **new REST endpoints** in the README or a dedicated API doc
- Include **request/response examples**
- Document **error codes** and **status codes**

### User Documentation

- Update `README.md` if user-facing features change
- Add **screenshots** for new UI features
- Document **new configuration options**

### README Updates

If your PR adds:

- New feature → update **Features** table
- New requirement → update **Requirements** section
- New command → update **Running** section
- New endpoint → update **REST API** table

---

## Reporting Issues

### Before Creating an Issue

1. Check **existing issues** (open and closed)
2. Check **discussions** for similar questions
3. Check **recent commits** to see if it's already fixed

### Issue Template

Use clear titles and descriptions:

```markdown
## Description

[Clear description of the issue]

## Steps to Reproduce

1. [First step]
2. [Second step]
3. ...

## Expected Behavior

[What should happen]

## Actual Behavior

[What actually happens]

## Environment

- OS: [Windows/macOS/Linux]
- Python version: [e.g., 3.11.2]
- pyMeOS version: [commit SHA or release]

## Logs

[Paste error messages or logs]

## Additional Context

[Screenshots, sample data files, etc.]
```

### Issue Labels

We use labels to categorize issues:

- `bug` — Something is broken
- `enhancement` — New feature request
- `documentation` — Documentation improvements
- `good-first-issue` — Beginner-friendly issues
- `help-wanted` — Extra attention needed
- `question` — Questions or discussions
- `wontfix` — Decided not to implement

---

## Getting Help

### Resources

- **README.md** — Project overview and architecture
- **API Docs** — REST API endpoints documented inline
- **Test Suite** — Over 197 tests serve as usage examples
- **GitHub Discussions** — Ask questions and discuss ideas

### Communication

- **Issues** — Bug reports and feature requests
- **Pull Request Comments** — Code review discussion
- **GitHub Discussions** — General questions (preferred for non-bugs)

### Common Questions

**Q: How do I run just the SI card tests?**

```bash
pytest tests/test_hardware/test_si_card.py -v
```

**Q: How do I test the GUI without a display?**

Use Xvfb on Linux:

```bash
xvfb-run -a pytest tests/test_views/ -v
```

Or mock the GUI in unit tests.

**Q: What's the time format used internally?**

All times are stored as **tenth-of-seconds** (same as MeOS):

```
1 unit = 0.1 seconds
encode(90.0) == 900  (1 minute 30 seconds)
format_time(900) == "1:30"
```

**Q: How do I add a new database column?**

1. Update the ORM model in `persistence/orm_models.py`
2. Create a migration (if using Alembic)
3. Update the corresponding business model in `models/`
4. Update repository methods in `persistence/event_repo.py`
5. Add tests in `tests/test_persistence/`

---

## License

By contributing to pyMeOS, you agree that your contributions will be licensed under the **GNU Affero General Public License v3.0** — same as the project.

---

## Thank You! 🎉

Thank you for contributing to pyMeOS. Your efforts help make orienteering event management accessible to everyone!

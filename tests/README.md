# Test Workflow

This project uses `pytest` with tests under `tests/`.

## Quick Commands

- Run all tests:
  - `python -m pytest -q`
- Run only unit tests:
  - `python -m pytest -q tests/unit`
- Run only integration tests:
  - `python -m pytest -q tests/integration`
- Run by keyword:
  - `python -m pytest -q -k <keyword>`

## Markers

Markers are declared in `pytest.ini`:

- `integration`: tests that require full app/database wiring
- `slow`: tests that are slower and may be skipped for fast local loops

Example:

- Run everything except slow tests:
  - `python -m pytest -q -m "not slow"`

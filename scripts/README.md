# Scripts Organization

This folder groups operational and utility scripts by purpose.

## Structure

- `scripts/db/`: database maintenance and migration helpers
  - `check_db_structure.py`
  - `migrate_db.py`
  - `download_db.ps1`
- `scripts/diagnostics/`: one-off diagnostics and verification utilities
  - `test_rounding.py`
- `scripts/archive/`: legacy scripts kept for reference
- `scripts/`: active general-purpose scripts used by current workflows

## Rules

1. Keep project root focused on app entry points and core runtime files.
2. Put new DB scripts under `scripts/db/`.
3. Put temporary validation/debug scripts under `scripts/diagnostics/`.
4. Move obsolete scripts to `scripts/archive/` instead of root.
5. If a script is moved, update any hardcoded paths or imports accordingly.

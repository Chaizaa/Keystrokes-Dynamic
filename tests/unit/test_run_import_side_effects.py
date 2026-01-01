"""
Ensure importing the application entrypoint does not run cache-cleaning side effects.
This protects against accidental deletion when run.py is imported by tooling or tests.
"""

import importlib
import shutil
import sys
from pathlib import Path


def test_clean_cache_not_called_on_import(monkeypatch):
    calls = []

    # Patch shutil.rmtree to record calls if invoked
    def fake_rmtree(path):
        calls.append(str(path))

    monkeypatch.setattr(shutil, "rmtree", fake_rmtree)

    # Patch Path.rglob to ensure it doesn't return real filesystem dirs (defensive)
    monkeypatch.setattr(Path, "rglob", lambda self, pattern: [])

    # Import run module in isolated state
    if "run" in sys.modules:
        del sys.modules["run"]

    module = importlib.import_module("run")

    # If clean_cache had run on import, fake_rmtree would have been called
    assert calls == [], "clean_cache should not call shutil.rmtree on import"

    # Sanity: module should expose 'clean_cache' callable
    assert hasattr(module, "clean_cache") and callable(module.clean_cache)

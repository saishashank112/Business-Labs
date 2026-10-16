"""Shared test fixtures for Task 3."""

import pytest
from app.config import settings


@pytest.fixture(autouse=True)
def use_temporary_task3_db(tmp_path, monkeypatch):
    """Ensure all Task 3 tests run against an isolated temporary database, never touching real task3.db."""
    import shutil
    from pathlib import Path

    test_db = tmp_path / "task3_test.db"
    real_db = Path(__file__).parent.parent / "task3.db"
    if real_db.exists():
        shutil.copyfile(real_db, test_db)
    monkeypatch.setattr(settings, "t3_db_path", str(test_db))

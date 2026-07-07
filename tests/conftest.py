"""Shared pytest fixtures for the adhand test suite.

DB isolation: ``db.py`` does ``from config import DB_PATH`` and refers to the
name ``DB_PATH`` directly, so it reads the value bound in the ``db`` module
namespace at call time. We therefore point ``config.DB_PATH``, ``db.DB_PATH``
(and ``routes.DB_PATH``, which also imports the name) at a per-test temp file
and run a fresh ``db.init()``. Every test gets an empty, seeded database and
never touches the repo's real ``adhand.db``.
"""
import pytest

import config
import db


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    """Isolated, freshly-initialised SQLite database for one test.

    Yields the ``Path`` to the temp db. All modules that hold their own copy of
    ``DB_PATH`` are repointed before ``db.init()`` runs.
    """
    db_file = tmp_path / "adhand-test.db"
    monkeypatch.setattr(config, "DB_PATH", db_file)
    monkeypatch.setattr(db, "DB_PATH", db_file)

    # routes.py does ``from config import ... DB_PATH ...`` too; keep it in sync
    # so backup/restore endpoints (if exercised) use the temp file.
    import routes
    monkeypatch.setattr(routes, "DB_PATH", db_file, raising=False)

    db.init()
    yield db_file


@pytest.fixture
def client(temp_db):
    """FastAPI TestClient bound to the isolated temp database.

    ``temp_db`` runs first (fixture ordering), so the DB is already repointed
    and seeded before ``TestClient(app)`` triggers the lifespan, which calls
    ``db.init()`` again (idempotent) and ``scheduler.start()``.
    """
    from fastapi.testclient import TestClient

    import scheduler
    from main import app

    with TestClient(app) as c:
        yield c

    # Leave the shared APScheduler in a clean state for the next test.
    if scheduler.scheduler.running:
        scheduler.shutdown()

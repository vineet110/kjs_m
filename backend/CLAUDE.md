# Backend (FastAPI)

Project rules: `docs/prompt.md` section 3. This file: how to run and test.

1. Python: always `.venv/Scripts/python.exe` (Windows) or `.venv/bin/python`. The system Python lacks the packages.

2. Tests: `.venv/Scripts/python.exe -m pytest -q` (one file: add `tests/test_x.py`).

   i.    They need the test database: Docker container `kjs_test_db` on port 5433 (`docker start kjs_test_db`).
   ii.   Never run two pytest runs at once: they share that database and break each other.
   iii.  Tests run with `require_verified_email = true` whatever `config/app.ini` says (`tests/conftest.py`).
   iv.   Change a config value in a test: `monkeypatch.setenv("KJS__CHAT__BODY_MAX", "100")` then
         `ini.reload_now()`. Never `monkeypatch.setattr` a module constant for a tunable.

3. Migrations: `alembic upgrade head` locally. Alembic reads BOTH database URLs: set both, or it migrates Neon
   (`docs/memory.md` decision 38). Next free number: check `alembic/versions/` AND the open PRs.

4. Layout: one feature = `models/<x>.py`, `services/<x>_service.py`, `api/v1/endpoints/<x>.py`,
   `config/<x>.ini` (class in `app/core/config/ini.py`), `tests/test_<x>*.py`.

5. Config: read values with `cfg().<feature>.<key>` at the moment you use them (never copy into a module
   constant, or a live edit does nothing). Pydantic `Field(max_length=...)` is fixed at import: for a tunable
   limit, use a `field_validator` that reads `cfg()`.

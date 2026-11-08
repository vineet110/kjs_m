"""Each entry point must import on its own, in a fresh Python. The other tests can't catch an import loop:
by the time they run, the app has already imported everything in a working order. `python -m app.seed`
(used by the deploy guide to make the first admin) crashed this way once."""
import subprocess
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
MODULES = [
    "app.seed", "app.main", "app.jobs.runner",
    "app.services.auth_service", "app.services.file_service", "app.services.board_service",
    "app.services.lead_service", "app.services.assign_service", "app.services.notification_service",
]


@pytest.mark.parametrize("module", MODULES)
def test_imports_alone(module):
    r = subprocess.run([sys.executable, "-c", f"import {module}"], cwd=BACKEND, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-1500:]


def test_main_still_registers_every_job():
    code = "import app.main; from app.jobs.runner import JOBS; print(len(JOBS))"
    r = subprocess.run([sys.executable, "-c", code], cwd=BACKEND, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-1500:]
    assert int(r.stdout.strip().splitlines()[-1]) > 0

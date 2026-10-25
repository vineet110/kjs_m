"""config/*.ini: precedence, live reload, bad file keeps the last good values."""
import logging
import os
import time

import pytest

from app.core.config import ini


@pytest.fixture
def config_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(ini, "CONFIG_DIR", tmp_path)
    ini.reload_now()
    yield tmp_path
    monkeypatch.undo()
    ini.reload_now()  # back to the real files


def write(path, text):
    path.write_text(text, encoding="utf-8")
    # make sure the modified-time changes even on fast file systems
    t = time.time() + 1
    os.utime(path, (t, t))


def test_defaults_when_no_files(config_dir):
    assert ini.cfg().sla.respond_minutes == 20
    assert ini.cfg().features.configurator is False


def test_ini_value_and_live_reload(config_dir):
    write(config_dir / "sla.ini", "[sla]\nrespond_minutes = 15\n")
    assert ini.reload_now().sla.respond_minutes == 15
    write(config_dir / "sla.ini", "[sla]\nrespond_minutes = 30 ; comment\n")
    assert ini.reload_now().sla.respond_minutes == 30


def test_env_beats_ini(config_dir, monkeypatch):
    write(config_dir / "sla.ini", "[sla]\nrespond_minutes = 15\n")
    monkeypatch.setenv("KJS__SLA__RESPOND_MINUTES", "7")
    assert ini.reload_now().sla.respond_minutes == 7


def test_invalid_file_keeps_last_good(config_dir, caplog):
    write(config_dir / "sla.ini", "[sla]\nrespond_minutes = 15\n")
    ini.reload_now()
    write(config_dir / "sla.ini", "[sla]\nrespond_minutes = soon\n")
    with caplog.at_level(logging.ERROR, logger="app.config"):
        assert ini.reload_now().sla.respond_minutes == 15
    assert any("sla.ini" in getattr(r, "reason", "") for r in caplog.records)


def test_lists_and_log_levels(config_dir):
    write(config_dir / "alerts.ini", "[alerts]\nthresholds = 40, 90\n")
    write(config_dir / "logging.ini", "[logging]\nlevel = INFO\n[logging.levels]\napp.services.lead_service = DEBUG\n")
    c = ini.reload_now()
    assert c.alerts.thresholds == [40, 90]
    assert c.logging.levels == {"app.services.lead_service": "DEBUG"}


def test_real_repo_files_are_valid():
    c = ini.reload_now()
    assert c.sla.respond_minutes > 0 and c.app.timezone == "Asia/Kolkata"


async def test_public_config_endpoint_has_no_secrets(client):
    r = await client.get("/api/public/config")
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"site_name", "features"} and "koko" in body["features"]

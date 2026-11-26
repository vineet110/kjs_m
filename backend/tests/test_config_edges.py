"""Edge cases for R91 / R97.iii: odd ini files and env values never throw away the other files."""
import os
import time

from app.core.config import ini
from tests.test_config import config_dir, write  # noqa: F401 (fixture)


def write_bytes(path, data: bytes):
    path.write_bytes(data)
    t = time.time() + 1
    os.utime(path, (t, t))


def test_a_file_saved_with_a_bom_still_applies(config_dir):
    # Windows Notepad can save "UTF-8 with BOM": the first line is then not "[app]" to the parser
    write_bytes(config_dir / "app.ini", "﻿[app]\njobs_enabled = false\n".encode("utf-8"))
    assert ini.reload_now().app.jobs_enabled is False


def test_a_file_not_in_utf8_spoils_only_itself(config_dir):
    write(config_dir / "app.ini", "[app]\njobs_enabled = false\n")
    write_bytes(config_dir / "sla.ini", "[sla]\n; caf\xe9\nrespond_minutes = 15\n".encode("cp1252"))
    c = ini.reload_now()
    assert c.app.jobs_enabled is False  # the good file still applied
    assert c.sla.respond_minutes == 20  # the unreadable one: defaults on the first load


def test_a_duplicate_section_or_percent_sign_spoils_only_itself(config_dir):
    write(config_dir / "app.ini", "[app]\njobs_enabled = false\n")
    write(config_dir / "sla.ini", "[sla]\nrespond_minutes = 15\n[sla]\nresolve_minutes = 90\n")
    write(config_dir / "koko.ini", "[koko]\ndaily_limit = 15%\n")
    c = ini.reload_now()
    assert c.app.jobs_enabled is False and c.sla.respond_minutes == 20


def test_env_problems_names_odd_keys(config_dir, monkeypatch):
    for k in ("KJS__SLA", "KJS__NOPE__X", "KJS__SLA__RESPOND_MINUTES__X", "KJS____"):
        monkeypatch.setenv(k, "1")
    monkeypatch.setenv("KJS__SLA__RESPOND_MINUTES", "-5")
    problems = ini.env_problems()
    for k in ("KJS__SLA:", "KJS__NOPE__X", "KJS__SLA__RESPOND_MINUTES__X", "KJS____"):
        assert any(p.startswith(k) for p in problems), k
    assert any("sla.ini" in p and "respond_minutes" in p for p in problems)

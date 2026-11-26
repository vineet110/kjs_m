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
    assert set(body) == {"site_name", "features", "insights", "site_ui"} and "koko" in body["features"]
    # site_ui: home page display settings only (site_ui.ini)
    assert body["site_ui"]["enabled"] is True and body["site_ui"]["slide_seconds"] == 6
    # insights: only the website tracker's timings and button names (site_insights.ini), nothing private
    assert set(body["insights"]) == {"on", "send_every_seconds", "max_events_per_send", "search_pause_ms",
                                     "min_search_chars", "buttons"}


async def test_site_ui_refuses_a_bad_value_and_keeps_the_last_good_one(client, monkeypatch):
    # slide_seconds must be 3 to 30: a typo like 0 must not stop the banner
    monkeypatch.setenv("KJS__SITE_UI__SLIDE_SECONDS", "0")
    ini.reload_now()
    assert (await client.get("/api/public/config")).json()["site_ui"]["slide_seconds"] == 6


async def test_public_config_says_when_insights_are_off(client, monkeypatch):
    monkeypatch.setenv("KJS__MODULES__SITE_INSIGHTS", "off")
    ini.reload_now()
    assert (await client.get("/api/public/config")).json()["insights"]["on"] is False


def test_one_bad_file_keeps_only_that_file_and_the_others_still_apply(config_dir, caplog):
    # R91: one bad key used to throw away EVERY file (jobs_enabled went back to its default)
    write(config_dir / "app.ini", "[app]\njobs_enabled = false\n")
    write(config_dir / "sla.ini", "[sla]\nrespond_minutes = soon\n")
    with caplog.at_level(logging.ERROR, logger="app.config"):
        c = ini.reload_now()
    assert c.app.jobs_enabled is False  # the good file applied
    assert c.sla.respond_minutes == 20  # the bad file: default on the first load
    assert any("sla.ini" in getattr(r, "reason", "") for r in caplog.records)


def test_bad_file_on_reload_keeps_its_last_good_values(config_dir):
    write(config_dir / "sla.ini", "[sla]\nrespond_minutes = 15\n")
    write(config_dir / "app.ini", "[app]\nlead_rate_per_hour = 9\n")
    ini.reload_now()
    write(config_dir / "sla.ini", "[sla]\nrespond_minutes = soon\n")
    write(config_dir / "app.ini", "[app]\nlead_rate_per_hour = 7\n")
    c = ini.reload_now()
    assert c.sla.respond_minutes == 15 and c.app.lead_rate_per_hour == 7


def test_env_problems_names_misspelt_and_out_of_range_values(config_dir, monkeypatch):
    monkeypatch.setenv("KJS__APP__JOBS_ENABLE", "true")  # misspelt key
    monkeypatch.setenv("KJS__NOPE__X", "1")  # no such file
    monkeypatch.setenv("KJS__STORAGE__MAX_UPLOAD_MB", "500")  # above the max (R91.ii)
    monkeypatch.setenv("KJS__SLA__RESPOND_MINUTES", "7")  # fine
    problems = ini.env_problems()
    assert any("KJS__APP__JOBS_ENABLE:" in p for p in problems)
    assert any("KJS__NOPE__X:" in p for p in problems)
    assert any("storage.ini" in p and "max_upload_mb" in p for p in problems)
    assert not any("sla" in p.lower() for p in problems)


def test_a_file_with_a_syntax_error_keeps_only_that_file(config_dir, caplog):
    write(config_dir / "app.ini", "[app]\njobs_enabled = false\n")
    write(config_dir / "sla.ini", "[sla]\nrespond_minutes = 15\nrespond_minutes = 16\n")  # duplicate key
    with caplog.at_level(logging.ERROR, logger="app.config"):
        c = ini.reload_now()
    assert c.app.jobs_enabled is False and c.sla.respond_minutes == 20
    assert any("sla.ini" in getattr(r, "reason", "") for r in caplog.records)


def test_a_rule_between_files_broken_by_a_bad_file_still_keeps_the_good_files(config_dir):
    # notifications.ini is bad, so its default email budget (120) comes back, and a 60 s timeout < 120 + 30
    # breaks the rule. The rule is never waived: the timeout goes back to its safe value, every other good
    # setting (jobs_enabled = false) stays (R91 + review of #113)
    write(config_dir / "app.ini", "[app]\njobs_enabled = false\njob_timeout_seconds = 60\n")
    write(config_dir / "notifications.ini", "[notifications]\nemail_time_budget_seconds = soon\n")
    c = ini.reload_now()
    assert c.app.jobs_enabled is False
    assert c.app.job_timeout_seconds >= c.notifications.email_time_budget_seconds + 30


def test_a_good_file_cannot_break_the_rule_while_the_other_rule_file_is_bad(config_dir):
    # Review of #113: app.ini has a typo (keeps its last good 300 s), then the email budget is raised to 280.
    # 300 < 280 + 30: the budget must stay at its last good value, never go live with the unsafe pair
    write(config_dir / "app.ini", "[app]\njob_timeout_seconds = 300\n")
    write(config_dir / "notifications.ini", "[notifications]\nemail_time_budget_seconds = 120\n")
    ini.reload_now()
    write(config_dir / "app.ini", "[app]\njob_timeout_seconds = 300\nlead_rate_per_hour = x\n")
    write(config_dir / "notifications.ini", "[notifications]\nemail_time_budget_seconds = 280\n")
    c = ini.reload_now()
    assert c.app.job_timeout_seconds >= c.notifications.email_time_budget_seconds + 30
    assert c.notifications.email_time_budget_seconds == 120


def test_strict_validation_fails_on_any_bad_file(config_dir):
    write(config_dir / "sla.ini", "[sla]\nrespond_minutes = soon\n")
    with pytest.raises(ValueError, match="sla.ini"):
        ini._validate(ini._read_raw(), strict=True)
    write(config_dir / "sla.ini", "[sla]\nx = 1\nx = 2\n")
    with pytest.raises(ValueError, match="sla.ini"):
        ini._validate(ini._read_raw(), strict=True)


def test_env_problems_never_raises_on_a_broken_file(config_dir, monkeypatch):
    write(config_dir / "sla.ini", "[sla]\nx = 1\nx = 2\n")
    monkeypatch.setenv("KJS__SLA__RESPOND_MINUTES", "7")
    ini.env_problems()  # no exception


def test_a_percent_sign_keeps_only_that_file(config_dir):
    # ConfigParser checks % only when a value is read: that must not stop every file loading
    write(config_dir / "app.ini", "[app]\njobs_enabled = false\n")
    write(config_dir / "sla.ini", "[sla]\nrespond_minutes = 15%\n")
    c = ini.reload_now()
    assert c.app.jobs_enabled is False and c.sla.respond_minutes == 20


def test_a_rule_broken_by_good_files_is_never_waived_and_the_rest_still_applies(config_dir):
    write(config_dir / "app.ini", "[app]\nlead_rate_per_hour = 9\n")
    ini.reload_now()
    write(config_dir / "app.ini", "[app]\nlead_rate_per_hour = 7\njob_timeout_seconds = 60\n")  # 60 < 120 + 30
    write(config_dir / "sla.ini", "[sla]\nrespond_minutes = soon\n")  # bad, but not read by that rule
    c = ini.reload_now()
    # The rule's values go back to their last good ones (300 s); the other new values still apply (re-review
    # of #113: refusing everything meant all defaults on the first load, e.g. jobs back on)
    assert c.app.job_timeout_seconds == 300 and c.app.lead_rate_per_hour == 7


def test_first_load_with_two_good_files_that_disagree_keeps_the_other_settings(config_dir):
    write(config_dir / "app.ini", "[app]\njobs_enabled = false\njob_timeout_seconds = 100\n")  # 100 < 120 + 30
    c = ini.reload_now()
    assert c.app.jobs_enabled is False and c.app.job_timeout_seconds >= c.notifications.email_time_budget_seconds + 30


def test_env_values_still_win_when_their_file_is_broken(config_dir, monkeypatch):
    # Production switches jobs off with KJS__APP__JOBS_ENABLED=false: a broken app.ini must not switch them on
    monkeypatch.setenv("KJS__APP__JOBS_ENABLED", "false")
    write(config_dir / "app.ini", "[app]\nlead_rate_per_hour = 5\nlead_rate_per_hour = 6\n")  # duplicate key
    assert ini.reload_now().app.jobs_enabled is False
    write(config_dir / "app.ini", "[app]\nlead_rate_per_hour = soon\n")  # a bad value
    assert ini.reload_now().app.jobs_enabled is False


def test_a_failed_first_load_keeps_trying_but_logs_once(config_dir, monkeypatch, caplog):
    # A fresh store whose very first load fails: loaded_from_files stays False, so only `tried` stops the retry
    store = ini._Store()
    calls = []

    def failing(*a, **k):
        calls.append(1)
        raise ValueError("config/app.ini: broken")

    monkeypatch.setattr(ini, "_validate", failing)
    with caplog.at_level(logging.ERROR, logger="app.config"):
        store.load()
        store.load()
        store.load()
    assert len(calls) == 3  # with no good config yet it keeps trying (never settles for the defaults quietly)
    assert len([r for r in caplog.records if r.msg == "config.invalid"]) == 1  # but says so once


def test_a_deleted_key_goes_back_to_its_default_even_with_a_bad_env_value(config_dir, monkeypatch):
    monkeypatch.setenv("KJS__APP__TIMEZONE", "Asia/Kolkataa")  # bad: the app section always takes the fallback
    write(config_dir / "app.ini", "[app]\nlead_rate_per_hour = 9\n")
    assert ini.reload_now().app.lead_rate_per_hour == 9
    write(config_dir / "app.ini", "[app]\n")  # the line is deleted
    assert ini.reload_now().app.lead_rate_per_hour == 5  # its default, not the old 9


def test_env_values_that_only_work_together_are_both_applied(config_dir, monkeypatch):
    write(config_dir / "modules.ini", "[modules]\nsite_insights = on\nanalytics = on\n")
    monkeypatch.setenv("KJS__MODULES__ANALYTICS", "off")
    monkeypatch.setenv("KJS__MODULES__SITE_INSIGHTS", "off")
    monkeypatch.setenv("KJS__MODULES__NOPE", "off")  # an unknown area: forces the one-at-a-time path
    c = ini.reload_now()
    assert c.modules.analytics == "off" and c.modules.site_insights == "off"


def test_a_misspelt_time_zone_is_a_bad_value_not_a_crash(config_dir, monkeypatch):
    monkeypatch.setenv("KJS__APP__TIMEZONE", "Asia/Kolkataa")
    assert ini.reload_now().app.timezone == "Asia/Kolkata"
    assert any("timezone" in p for p in ini.env_problems())


def test_one_bad_env_value_drops_only_itself(config_dir, monkeypatch):
    # Re-review of #113: a bad env value must not take the good env values or the good file down with it
    monkeypatch.setenv("KJS__APP__JOBS_ENABLED", "false")
    monkeypatch.setenv("KJS__APP__LEAD_RATE_PER_HOUR", "0")  # out of range
    monkeypatch.setenv("KJS__APP__TIMEZONE", "Asia/Kolkataa")  # misspelt
    write(config_dir / "app.ini", "[app]\nkoko_rate_per_hour = 7\n")
    c = ini.reload_now()
    assert c.app.jobs_enabled is False and c.app.koko_rate_per_hour == 7
    assert c.app.lead_rate_per_hour == 5 and c.app.timezone == "Asia/Kolkata"  # the bad ones keep their defaults


def test_a_misspelt_module_env_key_does_not_switch_every_area_on(config_dir, monkeypatch):
    monkeypatch.setenv("KJS__MODULES__CHAT", "off")
    monkeypatch.setenv("KJS__MODULES__CHATT", "off")  # misspelt: modules refuse unknown areas
    assert ini.reload_now().modules.chat == "off"


def test_a_bad_app_ini_on_a_fresh_start_never_switches_jobs_on(config_dir):
    # Last review of #113: the defaults are what a bad file falls back to on a first load
    write(config_dir / "app.ini", "[app]\njobs_enabled = false\nlead_rate_per_hour = x\n")
    assert ini.reload_now().app.jobs_enabled is False

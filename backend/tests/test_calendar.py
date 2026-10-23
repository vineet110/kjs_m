from datetime import date

import pytest

from app.services.calendar_service import CalendarService
from tests.conftest import HDR, login, make_user

SAT, SUN, MON = date(2026, 10, 17), date(2026, 10, 18), date(2026, 10, 19)
DIWALI = date(2026, 11, 9)  # example holiday for the test only; real list comes from KJS (I4)


def test_sunday_is_off():
    assert not CalendarService.is_working_day(SUN, [])


def test_saturday_is_working():
    assert CalendarService.is_working_day(SAT, [])


def test_holiday_is_off():
    assert not CalendarService.is_working_day(DIWALI, {DIWALI})


def test_add_working_days_skips_sunday():
    # Sat + 1 working day = Mon (Sunday skipped)
    assert CalendarService.add_working_days(SAT, 1, []) == MON


def test_add_working_days_skips_holiday():
    # Sat 7 Nov + 2 working days: Sun 8 off, Mon 9 holiday -> Tue 10, Wed 11
    assert CalendarService.add_working_days(date(2026, 11, 7), 2, {DIWALI}) == date(2026, 11, 11)


def test_add_zero_days_is_same_day():
    assert CalendarService.add_working_days(MON, 0, []) == MON


def test_negative_days_rejected():
    with pytest.raises(ValueError):
        CalendarService.add_working_days(MON, -1, [])


def test_working_days_between_one_week():
    # Mon 19 Oct .. Sun 25 Oct = 6 working days (Mon–Sat)
    assert CalendarService.working_days_between(MON, date(2026, 10, 25), []) == 6
    assert CalendarService.working_days_between(MON, date(2026, 10, 25), {date(2026, 10, 20)}) == 5
    assert CalendarService.working_days_between(MON, SAT, []) == 0  # end before start


async def test_admin_manages_holidays(client):
    await make_user("admin@kjsindia.com", role="admin")
    await login(client, "admin@kjsindia.com")
    r = await client.post("/api/v1/admin/holidays", headers=HDR, json={"day": "2026-11-09", "name": "Test holiday"})
    assert r.status_code == 201
    dup = await client.post("/api/v1/admin/holidays", headers=HDR, json={"day": "2026-11-09", "name": "Again"})
    assert dup.status_code == 409
    listed = (await client.get("/api/v1/admin/holidays?year=2026")).json()
    assert [h["day"] for h in listed] == ["2026-11-09"]
    assert (await client.delete(f"/api/v1/admin/holidays/{listed[0]['id']}", headers=HDR)).status_code == 204


async def test_employee_cannot_edit_holidays(client):
    await make_user("e@kjsindia.com")
    await login(client, "e@kjsindia.com")
    r = await client.post("/api/v1/admin/holidays", headers=HDR, json={"day": "2026-11-09", "name": "X"})
    assert r.status_code == 403

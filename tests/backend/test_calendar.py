from datetime import date
from backend.app.services.calendar_service import CalendarService

def test_sunday_is_off():
    # 2026-10-18 is Sunday
    sun = date(2026, 10, 18)
    assert not CalendarService.is_working_day(sun, [])

def test_saturday_is_working():
    # 2026-10-17 is Saturday
    sat = date(2026, 10, 17)
    assert CalendarService.is_working_day(sat, [])

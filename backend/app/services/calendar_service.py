from datetime import date, timedelta

class CalendarService:
    @staticmethod
    def is_working_day(target_date: date, holidays: list[date]) -> bool:
        # Mon=0 to Sat=5 are working days. Sunday=6 is off.
        if target_date.weekday() == 6:
            return False
        if target_date in holidays:
            return False
        return True

    @staticmethod
    def add_working_days(start_date: date, num_days: int, holidays: list[date]) -> date:
        current = start_date
        added = 0
        while added < num_days:
            current += timedelta(days=1)
            if CalendarService.is_working_day(current, holidays):
                added += 1
        return current

import time
from apscheduler.schedulers.blocking import BlockingScheduler

scheduler = BlockingScheduler()

def daily_auto_assign():
    print("[09:00 IST Cron] Triggering daily auto-assignment job")

def check_deadlines_15m():
    print("[15m Cron] Checking order board step deadline alerts (50%, 85%, 100%)")

scheduler.add_job(daily_auto_assign, 'cron', hour=9, minute=0, day_of_week='mon-sat')
scheduler.add_job(check_deadlines_15m, 'interval', minutes=15)

if __name__ == "__main__":
    print("APScheduler initialized for KJS India Platform.")
    scheduler.start()

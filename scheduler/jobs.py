import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from apscheduler.schedulers.blocking import BlockingScheduler
from main import run_pipeline

def start_scheduler():
    print("Running pipeline once immediately...")
    run_pipeline()
    print("Scheduling daily runs at 06:30...")
    scheduler = BlockingScheduler()
    scheduler.add_job(run_pipeline, "cron", hour=6, minute=30)
    scheduler.start()

if __name__ == "__main__":
    start_scheduler()

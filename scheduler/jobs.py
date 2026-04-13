# scheduler/jobs.py
from apscheduler.schedulers.blocking import BlockingScheduler
from main import run_pipeline

scheduler = BlockingScheduler()
scheduler.add_job(run_pipeline, "cron", hour=6, minute=30)  # runs daily at market open
scheduler.start()
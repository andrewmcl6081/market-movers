import pytz
import logging
from datetime import datetime, date, timezone
from apscheduler.triggers.cron import CronTrigger
from apscheduler.schedulers.background import BackgroundScheduler

from app.config import get_config
from app.services.report_generator import ReportGenerator
from app.services.market_data_service import MarketDataService

logger = logging.getLogger(__name__)

class ReportScheduler:
  def __init__(self):
    self.config = get_config()
    self.scheduler = BackgroundScheduler()
    self.report_generator = ReportGenerator()
    self.timezone = pytz.timezone(self.config.TIMEZONE)
  
  def start(self):
    """Start the scheduler"""
    
    try:
      hour, minute = map(int, self.config.REPORT_TIME.split(':'))
      
      # Schedule daily report generation
      self.scheduler.add_job(
        func=self._run_daily_report,
        trigger=CronTrigger(
          hour=hour,
          minute=minute,
          timezone=self.timezone
        ),
        id="daily_report",
        name="Generate Daily Market Report",
        replace_existing=True
      )
      
      if not self.scheduler.running:
        self.scheduler.start()
        logger.info(f"Scheduler started. Daily report scheduled at {self.config.REPORT_TIME} {self.config.TIMEZONE}")
      else:
        logger.info("Scheduler already running — start() skipped.")
    except Exception as e:
      logger.error(f"Failed to start scheduler: {e}")
      raise
      
  def _run_daily_report(self):
    """Run the daily report generation"""
    
    try:
      logger.info("Starting scheduled daily report generation")
      report_date = datetime.now(timezone.utc).date()
      
      # Generate and send report
      success = self.report_generator.generate_and_send_report(report_date)
      
      if success:
        logger.info(f"Daily report for {report_date} completed successfully")
      else:
        logger.info(f"Daily report for {report_date} failed")
    except Exception as e:
      logger.error(f"Error in scheduled report generation: {e}")
  
  def _check_market_status(self):
    """Check market status and log it"""
    
    try:
      service = MarketDataService()
      status = service.get_market_status()
      logger.info(f"Market status: {status}")
    except Exception as e:
      logger.error(f"Error checking market status: {e}")
  
  def shutdown(self):
    """Shutdown the scheduler"""
    
    if self.scheduler.running:
      self.scheduler.shutdown()
      logger.info("Scheduler shutdown complete")
  
  def get_jobs(self):
    """Get list of scheduled jobs"""
    
    return [
      {
        "id": job.id,
        "name": job.name,
        "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
        "trigger": str(job.trigger)
      } for job in self.scheduler.get_jobs()
    ]
  
  def trigger_job(self, job_id: str):
    """Manually trigger a job"""
    job = self.scheduler.get_job(job_id)
    if job:
      job.func()
      return True
    return False
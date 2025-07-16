import logging
from datetime import date, datetime
from sqlalchemy.orm import Session
from typing import Dict, List, Optional

from app.config import get_config
from app.db.connection import get_db
from app.db.models import DailyReport, MarketMover, IndexSummary, IndexConstituent
from app.services.index_service import MarketDataService
from app.services.news_service import NewsService
from app.services.email_service import EmailService
from app.services.sentiment_service import get_sentiment_model

logger = logging.getLogger(__name__)

class ReportGenerator:
  def __init__(self):
    self.config = get_config()
    self.market_service = MarketDataService()
    self.news_service = NewsService()
    self.email_service = EmailService()
  
  def generate_and_send_report(self, report_date: date) -> bool:
    """Generate and send the daily report"""
    
    start_time = datetime.now()
    db = next(get_db())
    
    try:
      logger.info(f"Starting report generation for {report_date}")
      if db.query(DailyReport).filter_by(report_date=report_date).first():
        logger.info(f"Report for {report_date} already exists")
        return True
      
      # Update constituents if needed
      constituents_count = self.market_service.ensure_constituents_present(db)
      
      # Get index summary
      index_summary = self.market_service.get_or_fetch_index_summary(db, report_date)
      if not index_summary:
        logger.error("Could not fetch index summary")
        return False
      
      # Fetch daily prices for all constituents
      symbols = [c.symbol for c in db.query(IndexConstituent).filter_by(is_active=True).all()]
      prices = self.market_service.fetch_daily_prices(db, symbols, report_date)
      logger.info(f"Fetched prices for {len(prices)} stocks")
      
      # Identify top movers
      gainers, losers = self.market_service.identify_top_movers(db, report_date)
      logger.info(f"Identified {len(gainers)} gainers and {len(losers)} losers")
      
      # Fetch news for all movers
      news_count = self.news_service.fetch_bulk_news_for_movers(db, report_date, gainers + losers)
      
      # Analyze sentiment
      self.news_service.analyze_sentiment_for_date(db, report_date)
      
      # Generate HTML content
      html_content = None
      
      report = DailyReport(
        report_date=report_date,
        index_close=index_summary["current_price"],
        index_change_pct=index_summary["percent_change"],
        index_change_points=index_summary["change"],
        html_content=html_content,
        email_sent=False,
        constituents_processed=constituents_count,
        news_articles_analyzed=news_count,
        generation_time_seconds=(datetime.now() - start_time).total_seconds()
      )
      db.add(report)
      db.commit()
      
      email_sent = self.email_service.send_report(html_content, report_date)
      if email_sent:
        report.email_sent = True
        report.email_sent_at = datetime.now()
        report.recipients = self.config.EMAIL_RECIPIENTS
        db.commit()
      
      logger.info(f"Report generation completed in {report.generation_time_seconds:.2f} seconds")
      return True
    except Exception as e:
      logger.error(f"Error generating report: {e}")
      db.rollback()
      
      self.email_service.send_error_notification(str(e), report_date)
      return False
    finally:
      db.close()
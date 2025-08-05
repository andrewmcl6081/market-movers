import logging
from datetime import date, datetime
from sqlalchemy.orm import Session
from typing import Dict, List, Optional

from app.config import get_config
from app.db.connection import get_db
from app.db.models import DailyReport, MarketMover, IndexSummary, IndexConstituent
from app.services.market_data_service import MarketDataService
from app.services.news_service import NewsService
from app.services.email_service import EmailService
from app.services.sentiment_service import get_sentiment_model
from app.utils.ec2 import delayed_termination

logger = logging.getLogger(__name__)

class ReportGenerator:
  def __init__(self):
    self.config = get_config()
    self.market_service = MarketDataService()
    self.news_service = NewsService(get_sentiment_model())
    self.email_service = EmailService()
  
  def generate_and_send_report(self, report_date: date) -> bool:
    """Generate and send the daily report"""
    
    start_time = datetime.now()
    db = next(get_db())
    
    try:
      logger.info(f"Starting report generation for {report_date}")
      
      if self.config.TEST_MODE:
        logger.warning(f"Running in TEST MODE - processing only {self.config.TEST_STOCK_COUNT} stocks")
        
      if not self.market_service.check_s3_data_exists(report_date):
        logger.warning(f"No S3 data available for {report_date}. Skipping report generation.")
        return False
      
      if db.query(DailyReport).filter_by(report_date=report_date).first():
        logger.info(f"Report for {report_date} already exists")
        return True
      
      try:
        constituents_count = self.market_service.update_sp500_constituents(db, report_date)
        logger.info(f"Updated {constituents_count} constituents from S3")
      except ValueError as e:
        logger.error(f"Failed to load constituents from S3: {e}")
        return False
      
      # Get index summary
      index_summary = self.market_service.get_or_fetch_index_summary(db, report_date)
      if not index_summary:
        logger.error("Could not fetch index summary")
        return False
      logger.info(f"Index summary: {index_summary}")
      
      all_constituents = db.query(IndexConstituent).filter_by(is_active=True).all()
      
      if self.config.TEST_MODE:
        symbols = [c.symbol for c in all_constituents[:self.config.TEST_STOCK_COUNT]]
        logger.info(f"Test mode: Processing {len(symbols)} stocks: {', '.join(symbols)}")
      else:
        symbols = [c.symbol for c in all_constituents]
      
      # Fetch daily prices for all constituents
      prices = self.market_service.fetch_daily_prices(db, symbols, report_date)
      logger.info(f"Fetched prices for {len(prices)} stocks")
      
      # Identify top movers
      gainers, losers = self.market_service.identify_top_movers(db, report_date)
      logger.info(f"Identified {len(gainers)} gainers and {len(losers)} losers")
      
      if not (gainers or losers):
        logger.warning("No movers found, aborting report generation")
        return False
      
      # Fetch news for all movers
      news_count = self.news_service.fetch_bulk_news_for_movers(db, report_date, gainers + losers)
      logger.info(f"Fetched {news_count} news articles")
      
      # Analyze sentiment
      self.news_service.analyze_sentiment_for_date(db, report_date)
      logger.info("Completed sentiment analysis")
      
      # Generate HTML content
      html_content = self.generate_html_report(
        report_date=report_date,
        index_summary=index_summary,
        gainers=gainers,
        losers=losers,
        db=db
      ) 
      
      # Get recipient count for the report
      recipients = self.email_service.get_active_recipients(db)
      logger.info(f"Retrieved {len(recipients)} recipients")
      
      report = DailyReport(
        report_date=report_date,
        index_close=index_summary["current_price"],
        index_change_pct=index_summary["percent_change"],
        index_change_points=index_summary["change"],
        html_content=html_content,
        email_sent=False,
        constituents_processed=constituents_count,
        news_articles_analyzed=news_count,
        generation_time_seconds=(datetime.now() - start_time).total_seconds(),
        recipients=recipients
      )
      db.add(report)
      db.commit()
      
      if not self.config.TEST_MODE:
        email_sent = self.email_service.send_report(html_content, report_date, db)
        if email_sent:
          report.email_sent = True
          report.email_sent_at = datetime.now()
          db.commit()
      else:
        logger.info("Test mode: Skipping email send")
      
      if self.config.ENVIRONMENT == "production":
        logger.info("Report finished successfully — scheduling instance termination")
        delayed_termination(region=self.config.AWS_REGION, delay=30)
      
      return True
    except Exception as e:
      logger.error(f"Error generating report: {e}")
      db.rollback()
      
      if not self.config.TEST_MODE:
        self.email_service.send_error_notification(str(e), report_date)
      return False
    finally:
      db.close()
    
  def generate_html_report(self, report_date: date, index_summary: Dict, gainers: List[Dict], losers: List[Dict], db: Session):
    """Generate HTML content for the report"""
    
    html = f"""
    <html>
    <body>
        <h1>Market Movers Daily Report - {report_date.strftime('%B %d, %Y')}</h1>
        
        <h2>S&P 500 Summary</h2>
        <p>Close: {index_summary['current_price']:,.2f}</p>
        <p>Change: {index_summary['change']:+.2f} ({index_summary['percent_change']:+.2f}%)</p>
        
        <h2>Top Gainers</h2>
        <ul>
        {"".join(f"<li>{g['symbol']} - {g['company_name']}: {g['percent_change']:+.2f}%</li>" for g in gainers)}
        </ul>
        
        <h2>Top Losers</h2>
        <ul>
        {"".join(f"<li>{l['symbol']} - {l['company_name']}: {l['percent_change']:+.2f}%</li>" for l in losers)}
        </ul>
    </body>
    </html>
    """
    
    return html
import os
import logging
from datetime import date, datetime, timezone
from sqlalchemy.orm import Session
from typing import Dict, List
from jinja2 import Environment, FileSystemLoader, select_autoescape

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
    
    template_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
    self.jinja_env = Environment(loader=FileSystemLoader(template_dir), autoescape=select_autoescape(["html", "xml"]))
  
  def generate_and_send_report(self, report_date: date) -> bool:
    """Generate and send the daily report"""
    
    start_time = datetime.now(timezone.utc)
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
        generation_time_seconds=(datetime.now(timezone.utc) - start_time).total_seconds(),
        recipients=recipients
      )
      db.add(report)
      db.commit()
      
      if not self.config.TEST_MODE:
        email_sent = self.email_service.send_report(html_content, report_date, db)
        if email_sent:
          report.email_sent = True
          report.email_sent_at = datetime.now(timezone.utc)
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
    
  def generate_html_report(self, report_date: date, index_summary: Dict, gainers: List[Dict], losers: List[Dict], db: Session) -> str:
    """Generate HTML content for the report"""
  
    movers = db.query(MarketMover).filter_by(date=report_date).all()
    
    gainers_with_headlines = []
    losers_with_headlines = []
    
    for gainer in gainers:
      mover_data = next((m for m in movers if m.symbol == gainer["symbol"] and m.mover_type == "gainer"), None)
      gainer_dict = gainer.copy()
      if mover_data:
        gainer_dict["positive_headline"] = mover_data.positive_headline
        gainer_dict["positive_headline_url"] = mover_data.positive_headline_url
      gainers_with_headlines.append(gainer_dict)
    
    for loser in losers:
      mover_data = next((m for m in movers if m.symbol == loser["symbol"] and m.mover_type == "loser"), None)
      loser_dict = loser.copy()
      if mover_data:
        loser_dict["negative_headline"] = mover_data.negative_headline
        loser_dict["negative_headline_url"] = mover_data.negative_headline_url
      losers_with_headlines.append(loser_dict)
    
    market_insights = self.generate_market_insights(index_summary, gainers, losers)
    
    template = self.jinja_env.get_template("email/daily_report.html")
    
    context = {
      "report_date": report_date,
      "index_summary": index_summary,
      "gainers": gainers_with_headlines,
      "losers": losers_with_headlines,
      "market_insights": market_insights,
      "current_year": datetime.now(timezone.utc).year,
      "unsubscribe_url": f"{self.config.API_V1_STR}/subscriptions/unsubscribe",
      "preferences_url": f"{self.config.API_V1_STR}/subscriptions/preferences"
    }
    
    return template.render(**context)
  
  def generate_market_insights(self, index_summary: Dict, gainers: List[Dict], losers: List[Dict]) -> str:
    total_gainer_impact = sum(g.get("index_points_contribution", 0) for g in gainers)
    total_loser_impact = sum(l.get("index_points_contribution", 0) for l in losers)
    net_top_movers_impact = total_gainer_impact + total_loser_impact
    
    if index_summary["percent_change"] > 1:
      sentiment = "strongly positive"
    elif index_summary["percent_change"] > 0:
      sentiment = "positive"
    elif index_summary["percent_change"] < -1:
      sentiment = "strongly negative"
    elif index_summary["percent_change"] < 0:
      sentiment = "negative"
    else:
      sentiment = "flat"
    
    insights = f"The market showed {sentiment} momentum today."
    
    if gainers and losers:
      insights += f"Top gainers contributed {total_gainer_impact:+.2f} points while top losers pulled the index down by {total_loser_impact:.2f} points, "
      insights += f"for a net impact of {net_top_movers_impact:+.2f} points from the day's biggest movers. "
    
    if gainers and losers:
      avg_gainer_move = sum(g["percent_change"] for g in gainers) / len(gainers)
      avg_loser_move = sum(abs(l["percent_change"]) for l in losers) / len(losers)
      
      if avg_gainer_move > 3 or avg_loser_move > 3:
        insights += "Large individual stock movements indicate heightened market volatility. "
      elif avg_gainer_move < 1.5 and avg_loser_move < 1.5:
        insights += "Relatively modest individual stock movements suggest a calm trading session. "
        
    if abs(index_summary["percent_change"]) < 0.5 and (total_gainer_impact + abs(total_loser_impact)) > 10:
      insights += "Despite the modest index change, significant underlying stock movements were observed. "
    
    return insights.strip()
    
    
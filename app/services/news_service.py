import logging
from typing import List, Dict
from app.config import get_config
from sqlalchemy.orm import Session
from datetime import datetime, date, timedelta
from app.db.models import MarketMover, NewsArticle
from app.services.sentiment_service import SentimentModel
from app.services.finnhub_client import get_finnhub_client

logger = logging.getLogger(__name__)

class NewsService:
  def __init__(self, sentiment_model: SentimentModel):
    self.config = get_config()
    self.client = get_finnhub_client()
    self.sentiment_model = sentiment_model
  
  def fetch_stock_news(self, db: Session, symbol: str, target_date: date) -> List[Dict]:
    try:
      mover = db.query(MarketMover).filter_by(symbol=symbol, date=target_date).first()
      if not mover:
        logger.warning(f"No market mover found for {symbol} on {target_date}")
        return []
      
      from_date = (target_date - timedelta(hours=self.config.NEWS_LOOKBACK_HOURS)).isoformat()
      to_date = target_date.isoformat()
      
      articles = self.client.company_news(symbol=symbol, _from=from_date, to=to_date)
      logger.info(f"Finnhub returned {len(articles)} articles for {symbol} from {from_date} to {to_date}")
      
      for article in articles:
        url = article.get("url")
        existing = db.query(NewsArticle).filter_by(symbol=symbol, url=url).first()
        
        if not existing:
          news_article = NewsArticle(
            market_mover_id=mover.id,
            symbol=symbol,
            date=target_date,
            headline=article.get("headline", "")[:500],
            summary=article.get("summary", ""),
            url=url,
            source=article.get("source", ""),
            published_at=datetime.fromtimestamp(article.get("datetime")).astimezone() if article.get("datetime") else None
          )
          db.add(news_article)
      
      db.commit()
      return articles
    
    except Exception as e:
      logger.error(f"Error fetching news for {symbol} via Finnhub: {e}")
      return []
  
  def fetch_bulk_news_for_movers(self, db: Session, report_date: date, movers: List[Dict]) -> int:
    """Fetch news for all market movers"""
    
    total_articles = 0
    for mover in movers:
      articles = self.fetch_stock_news(db, mover["symbol"], report_date)
      total_articles += len(articles)
    
    return total_articles
  
  def analyze_sentiment_for_date(self, db: Session, target_date: date):
    try:
      # Fetch all news articles for that date
      articles = db.query(NewsArticle).filter_by(date=target_date).all()
      
      # Run sentiment analysis on articles that haven't been analyzed yet
      for article in articles:
        if article.sentiment_score is None:
          text = f"{article.headline or ''}. {article.summary or ''}"
          result = self.sentiment_model.pipeline(text, truncation=True, max_length=512)[0]
          article.sentiment_label = result["label"].lower()
          article.sentiment_score = result["score"]
      
      db.commit()
      
      # Fetch all market movers for the date
      movers = db.query(MarketMover).filter_by(date=target_date).all()
      
      for mover in movers:
        # Filter articles for this stock symbol
        mover_articles = [a for a in articles if a.symbol == mover.symbol]
        
        if not mover_articles:
          continue
        
        # Determine stock movement direction
        direction = "positive" if mover.percent_change > 0 else "negative" if mover.percent_change < 0 else None
        if direction is None:
          continue
        
        # Filter for directionally-aligned articles
        aligned_articles = [
          a for a in mover_articles if a.sentiment_label == direction
        ]
        
        # Sort by sentiment score and take top 3
        top_articles = sorted(aligned_articles, key=lambda a: a.sentiment_score, reverse=True)[:3]
        
        for a in mover_articles:
          a.is_top_headline = False
        
        for article in top_articles:
          article.is_top_headline = True
        
        if top_articles:
          best = top_articles[0]
          if direction == "positive":
            mover.positive_headline = best.headline
            mover.positive_headline_score = best.sentiment_score
            mover.positive_headline_url = best.url
          elif direction == "negative":
            mover.negative_headline = best.headline
            mover.negative_headline_score = best.sentiment_score
            mover.negative_headline_url = best.url
      
      db.commit()
      logger.info(f"Completed sentiment analysis for {len(articles)} articles")
    
    except Exception as e:
      logger.error(f"Error in sentiment analysis: {e}")
      db.rollback()
    
from sqlalchemy import Column, Integer, String, Float, DateTime, Text, Date, Boolean, JSON, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.db.base import Base

class IndexConstituent(Base):
  __tablename__ = "index_constituents"
  
  id = Column(Integer, primary_key=True, index=True)
  symbol = Column(String(10), unique=True, nullable=False, index=True)
  company_name = Column(String(255))
  weight = Column(Float)
  added_date = Column(Date)
  is_active = Column(Boolean, default=True)
  updated_at = Column(DateTime, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))
  
  daily_prices = relationship("DailyPrice", back_populates="constituent", cascade="all, delete-orphan")
  market_moves = relationship("MarketMover", back_populates="constituent", cascade="all, delete-orphan")

class DailyPrice(Base):
  __tablename__ = "daily_prices"
  
  id = Column(Integer, primary_key=True, index=True)
  constituent_id = Column(Integer, ForeignKey("index_constituents.id"), nullable=False)
  symbol = Column(String(10), nullable=False, index=True)
  date = Column(Date, nullable=False, index=True)
  
  # Price data
  current_price = Column(Float)
  change = Column(Float)
  percent_change = Column(Float)
  high = Column(Float)
  low = Column(Float)
  open = Column(Float)
  previous_close = Column(Float)
  created_at = Column(DateTime, default=datetime.now(timezone.utc))
  
  # Relationships
  constituent = relationship("IndexConstituent", back_populates="daily_prices")
  
  # Unique constraint on symbol + date
  __table_args__ = (
    UniqueConstraint('symbol', 'date', name='_symbol_date_uc'),
  )

class IndexSummary(Base):
  __tablename__ = "index_summaries"
  
  id = Column(Integer, primary_key=True)
  date = Column(Date, unique=True, nullable=False)
  current_price = Column(Float)
  change = Column(Float)
  percent_change = Column(Float)
  high = Column(Float)
  low = Column(Float)
  open = Column(Float)
  previous_close = Column(Float)

class MarketMover(Base):
  """Top movers for each day"""
  __tablename__ = "market_movers"
  
  id = Column(Integer, primary_key=True, index=True)
  date = Column(Date, nullable=False, index=True)
  constituent_id = Column(Integer, ForeignKey("index_constituents.id"), nullable=False)
  symbol = Column(String(10), nullable=False)
  company_name = Column(String(255))
  
  # Movement data
  percent_change = Column(Float, nullable=False)
  index_points_contribution = Column(Float)
  close_price = Column(Float)
  
  # Ranking
  rank = Column(Integer)
  mover_type = Column(String(10))
  
  # News sentiment
  positive_headline = Column(Text)
  positive_headline_score = Column(Float)
  positive_headline_url = Column(Text)
  
  negative_headline = Column(Text)
  negative_headline_score = Column(Float)
  negative_headline_url = Column(Text)
  
  # Metadata
  created_at = Column(DateTime, default=datetime.now(timezone.utc))
  
  # Relationships
  constituent = relationship("IndexConstituent", back_populates="market_moves")
  news_articles = relationship("NewsArticle", back_populates="market_mover", cascade="all, delete-orphan")
  
  # Unique constraint - only one entry per stock per day
  __table_args__ = (
    UniqueConstraint('symbol', 'date', name='_symbol_date_mover_uc'),
  )

class DailyReport(Base):
  """Generated daily reports"""
  __tablename__ = "daily_reports"
  
  id = Column(Integer, primary_key=True, index=True)
  report_date = Column(Date, unique=True, nullable=False, index=True)
  
  # Market summary
  index_close = Column(Float)
  index_change_pct = Column(Float)
  index_change_points = Column(Float)
  total_volume = Column(Integer)
  
  # Report content
  html_content = Column(Text)
  pdf_path = Column(String(255))
  
  # Delivery status
  email_sent = Column(Boolean, default=False)
  email_sent_at = Column(DateTime)
  recipients = Column(JSON)
  
  # Generation metadata
  generated_at = Column(DateTime, default=datetime.now(timezone.utc))
  generation_time_seconds = Column(Float)
  
  # Data quality
  constituents_processed = Column(Integer)
  news_articles_analyzed = Column(Integer)
  
  # Relationships
  # Link to market moves for this day (indirect through date)
  @property
  def market_movers(self):
    """Get market movers for this report date"""
    from db.connection import SessionLocal
    session = SessionLocal()
    movers = session.query(MarketMover).filter_by(date=self.report_date).all()
    session.close()
    return movers

class NewsArticle(Base):
  """News articles for sentiment analysis"""
  __tablename__ = "news_articles"
  
  id = Column(Integer, primary_key=True, index=True)
  market_mover_id = Column(Integer, ForeignKey("market_movers.id"), nullable=False)
  symbol = Column(String(10), nullable=False, index=True)
  date = Column(Date, nullable=False, index=True)
  
  # Article data
  headline = Column(Text, nullable=False)
  summary = Column(Text)
  url = Column(Text)
  source = Column(String(100))
  published_at = Column(DateTime)
  
  # Sentiment analysis
  sentiment_label = Column(String(20))
  sentiment_score = Column(Float)
  is_top_headline = Column(Boolean, default=False)
  
  created_at = Column(DateTime, default=datetime.now(timezone.utc))
  
  # Relationships
  market_mover = relationship("MarketMover", back_populates="news_articles")

class UserSubscription(Base):
  """User email subscriptions for daily reports"""
  __tablename__ = "user_subscriptions"
  
  id = Column(Integer, primary_key=True, index=True)
  email = Column(String(255), unique=True, nullable=False, index=True)
  send_daily_report = Column(Boolean, default=True)
  
  subscribed_at = Column(DateTime, default=datetime.now(timezone.utc))
  unsubscribed_at = Column(DateTime)
  
  last_email_sent = Column(DateTime)
  total_emails_sent = Column(Integer, default=0)
  
  timezone = Column(String(50), default="America/New_York")
  
  updated_at = Column(DateTime, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))
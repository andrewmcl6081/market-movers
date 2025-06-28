import os
import json
import logging
import finnhub
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, date
from typing import List, Dict, Optional, Tuple

from db.models import IndexConstituent, DailyPrice, MarketMover
from config import get_config

logger = logging.getLogger(__name__)

class MarketDataService:
  def __init__(self):
    self.config = get_config()
    self.client = finnhub.Client(api_key=self.config.FINNHUB_API_KEY)
    self.sp500_top_constituents = self._load_top_constituents()
  
  def _load_top_constituents(self) -> List[Dict]:
    """Load top 50 S&P companies from local JSON file"""
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(project_root, "market_data", "sp500_top_50.json")
    with open(path, "r") as f:
      return json.load(f)
  
  def update_sp500_constituents(self, db: Session) -> int:
    try:
      db.query(IndexConstituent).update({"is_active": False})
      updated_count = 0
      
      for constituent in self.sp500_top_constituents:
        self._update_constituent(
          db,
          constituent["company"],
          constituent["symbol"],
          constituent["weight"]
        )
        updated_count += 1
      
      db.commit()
      logger.info(f"Updated {updated_count} S&P 500 constituents")
      return updated_count
    except Exception as e:
      logger.error(f"Error updating constituents: {e}")
      db.rollback()
      return 0
  
  def _update_constituent(self, db: Session, company: str, symbol: str, weight: float):
    existing = db.query(IndexConstituent).filter_by(symbol=symbol).first()
    
    if existing:
      existing.is_active = True
      existing.company_name = company
      existing.weight = weight
      existing.updated_at = datetime.utcnow()
    else:
      new_constituent = IndexConstituent(
        symbol=symbol,
        company_name=company,
        weight=weight,
        is_active=True,
        added_date=date.today()
      )
      db.add(new_constituent)
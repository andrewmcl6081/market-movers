import os
import json
import logging
import finnhub
from sqlalchemy.orm import Session
from datetime import datetime, date
from typing import List, Dict, Optional, Tuple

from db.models import IndexConstituent, DailyPrice, IndexSummary, MarketMover
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
  
  def get_index_level(self, db: Session, target_date: date) -> Optional[float]:
    """Fetch S&P 500 index level (current close price) from DB"""
    summary = db.query(IndexSummary).filter_by(date=target_date).first()
    return summary.current_price if summary else None
  
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
  
  def fetch_daily_prices(self, db: Session, symbols: List[str], target_date: date) -> Dict[str, Dict]:
    """Fetch daily prices for given symbols"""
    prices = {}
    
    for symbol in symbols:
      # Get current price
      try:
        quote = self.client.quote(symbol)
        
        if quote and quote.get("c") is not None:
          prices[symbol] = {
            "current_price": quote.get("c"),
            "change": quote.get("d"),
            "percent_change": quote.get("dp"),
            "high": quote.get("h"),
            "low": quote.get("l"),
            "open": quote.get("o"),
            "previous_close": quote.get("pc")
          }
          
          # Check if exists and store in DB
          existing = db.query(DailyPrice).filter_by(symbol=symbol, date=target_date).first()
          
          if not existing:
            # Get constituent ID
            constituent = db.query(IndexConstituent).filter_by(symbol=symbol).first()
            if constituent:
              daily_price = DailyPrice(
                constituent_id=constituent.id,
                symbol=symbol,
                date=target_date,
                current_price=quote.get("c"),
                change=quote.get("d"),
                percent_change=quote.get("dp"),
                high=quote.get("h"),
                low=quote.get("l"),
                open=quote.get("o"),
                previous_close=quote.get("pc")
              )
              db.add(daily_price)
      except Exception as e:
        logger.error(f"Error fetching price for {symbol}: {e}")
        continue
    
    try:
      db.commit()
    except Exception as e:
      logger.error(f"Error saving prices: {e}")
      db.rollback
    
    return prices

  def calculate_index_impact(self, percent_change: float, weight: float, index_level: float) -> float:
    """Calculate how many index points a stock's move contributed"""
    index_contribution_pct = (weight * percent_change) / 100
    index_points = (index_contribution_pct * index_level) / 100
    return round(index_points, 2)
  
  def get_index_summary(self, db: Session, target_date: date) -> Optional[Dict]:
    try:
      spy_quote = self.client.quote("SPY")
      
      if spy_quote and spy_quote.get("c") is not None:
        summary = IndexSummary(
          date=target_date,
          current_price=spy_quote["c"],
          change=spy_quote["d"],
          percent_change=spy_quote["dp"],
          high=spy_quote["h"],
          low=spy_quote["l"],
          open=spy_quote["o"],
          previous_close=spy_quote["pc"]
        )
        db.add(summary)
        db.commit()
        
        return {
          "current_price": summary.current_price,
          "change": summary.change,
          "percent_change": summary.percent_change,
          "high": summary.high,
          "low": summary.low,
          "open": summary.open,
          "previous_close": summary.previous_close
        }
      else:
        logger.warning("SPY quote missing or incomplete. Skipping index summary.")
        return None
    except Exception as e:
      logger.error(f"Error fetching SPY quote from Finnhub: {e}")
      db.rollback()
      return None

  def identify_top_movers(self, db: Session, target_date: date) -> Tuple[List[Dict], List[Dict]]:
    """Identify top 5 gainers and losers by index impact"""
    
    try:
      index_level = self.get_index_level(db, target_date)
      if index_level is None:
        raise ValueError("Index level not available for date")
      
      # Get all active constituents
      constituents = db.query(IndexConstituent).filter_by(is_active=True).all()
      if not constituents:
        logger.warning("No active constituents found. Attempting to update")
        self.update_sp500_constituents(db)
        constituents = db.query(IndexConstituent).filter_by(is_active=True).all()
      
      prices = {
        p.symbol: p
        for p in db.query(DailyPrice)
        .filter(DailyPrice.date == target_date, DailyPrice.symbol.in_([c.symbol for c in constituents]))
      }
      
      movers = []
      for c in constituents:
        price = prices.get(c.symbol)
        if not price or price.percent_change is None:
          continue
        
        if abs(price.percent_change) > 0.5:
          impact = self.calculate_index_impact(
            percent_change=price.percent_change,
            weight=c.weight,
            index_level=index_level
          )
        
          movers.append({
            "symbol": c.symbol,
            "company_name": c.company_name,
            "percent_change": price.percent_change,
            "close_price": price.current_price,
            "index_points_contribution": impact,
            "constituent_id": c.id
          })
      
      # Sort by absolute index impact
      movers.sort(key=lambda m: abs(m["index_points_contribution"]), reverse=True)
      
      gainers = [m for m in movers if m["percent_change"] > 0][:5]
      losers = [m for m in movers if m["percent_change"] < 0][:5]
      
      for rank, gainer in enumerate(gainers, 1):
        db.add(MarketMover(
          date=target_date,
          constituent_id=gainer["constituent_id"],
          symbol=gainer["symbol"],
          company_name=gainer["company_name"],
          percent_change=gainer["percent_change"],
          index_points_contribution=gainer["index_points_contribution"],
          close_price=gainer["close_price"],
          rank=rank,
          mover_type="gainer"
        ))
      
      for rank, loser in enumerate(losers, 1):
        db.add(MarketMover(
          date=target_date,
          constituent_id=loser["constituent_id"],
          symbol=loser["symbol"],
          company_name=loser["company_name"],
          percent_change=loser["percent_change"],
          index_points_contribution=loser["index_points_contribution"],
          close_price=loser["close_price"],
          rank=-rank,
          mover_type="loser"
        ))
      
      db.commit()
      logger.info(f"Identified {len(gainers)} gainers and {len(losers)} losers")
      return gainers, losers
    except Exception as e:
      logger.error(f"Error identifying top movers: {e}")
      return [], []
  
  def get_stock_fundamentals(self, symbol: str) -> Dict:
    try:
      profile = self.client.company_profile2(symbol=symbol)
      if profile:
        return {
          "market_cap": profile.get("marketCapitalization", 0) * 1_000_000,
          "name": profile.get("name"),
          "industry": profile.get("finnhubIndustry"),
          "logo": profile.get("logo"),
          "weburl": profile.get("weburl")
        }
    except Exception as e:
      logger.error(f"Error fetching fundamentals for {symbol}: {e}")
    
    return {}
  
  def get_market_status(self) -> Dict:
    try:
      status = self.client.market_status(exchange="US")
      return {
        "is_open": status.get("isOpen", False),
        "session": status.get("session", "closed"),
        "timezone": status.get("timezone", "America/New_York")
      }
    except Exception as e:
      logger.error(f"Error checking market status: {e}")
      return {
        "is_open": False,
        "session": "unknown",
        "error": str(e)
      }
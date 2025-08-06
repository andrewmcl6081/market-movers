import os
import json
import boto3
import logging
from sqlalchemy import insert
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime, date, timezone
from botocore.exceptions import ClientError
from typing import List, Dict, Optional, Tuple, Any

from app.db.models import IndexConstituent, DailyPrice, IndexSummary, MarketMover
from app.services.finnhub_client import get_finnhub_client
from app.config import get_config

logger = logging.getLogger(__name__)

class MarketDataService:
  def __init__(self):
    self.config = get_config()
    self.client = get_finnhub_client()
    self.s3_client = self.create_s3_client()
  
  def create_s3_client(self):
    """Create S3 client with appropriate credentials based on environment"""
    
    if self.config.ENVIRONMENT in ("test", "development"):
      logger.info("Creating S3 client using local AWS profile/credentials")
      
      profile_name = self.config.AWS_PROFILE
      
      try:
        session = boto3.Session(profile_name=profile_name)
        s3_client = session.client("s3")
        logger.info(f"Successfully created S3 client using profile: {profile_name}")
        
        return s3_client
      except Exception as e:
        logger.warning(f"Failed to use AWS profile {profile_name}: {e}")
        logger.info("Falling back to default credential chain")
        
        return boto3.client("s3")
    else:
      logger.info("Creating S3 client using IAM role (EC2 instance profile)")
      return boto3.client("s3", region_name=self.config.AWS_REGION)
  
  def check_s3_data_exists(self, target_date: date) -> bool:
    """Check if S3 data exists for a specific date"""
    
    date_str = target_date.strftime("%Y-%m-%d")
    s3_key = f"sp500-data/{date_str}/sp500_data.json"
    
    try:
      self.s3_client.head_object(Bucket=self.config.S3_BUCKET, Key=s3_key)
    except ClientError as e:
      code = e.response.get("Error", {}).get("Code", "")

      if code == "404":
        logger.warning(f"No S3 data found for {date_str}")
        return False
      
      logger.error(f"Error checking S3 data existence for {date_str}: {e}")
      raise
    else:
      logger.info(f"S3 data exists for {date_str}")
      return True
  
  def load_top_constituents_s3(self, target_date: date) -> list[dict]:
    """Fetch S&P 500 data from s3 for the given date"""
    
    date_str = target_date.strftime("%Y-%m-%d")
    bucket = self.config.S3_BUCKET
    key = f"sp500-data/{date_str}/sp500_data.json"
    
    logger.info(f"Fetching S&P 500 data from s3://{bucket}/{key}")
    
    try:
      response = self.s3_client.get_object(Bucket=bucket, Key=key)
      payload = json.loads(response["Body"].read().decode())
      entries = payload.get("data", [])[:50]
      
      return [
        {"company": c["company"], "symbol": c["symbol"], "weight": c["weight"]}
        for c in entries
      ]
    except Exception as e:
      logger.exception(f"Error loading S&P 500 constituents for {date_str}")
      raise RuntimeError(f"Failed to fetch S&P data for {date_str}") from e
  
  def ensure_constituents_present(self, db: Session) -> None:
    """
    Ensure there's at least one active IndexConstituent in the database;
    If not, fetch and insert them from S3
    """
    
    today = date.today()
    try:
      active_count = db.query(IndexConstituent).filter_by(is_active=True).count()
      
      if active_count == 0:
        logger.info("No active constituents found: updating S&P 500 constituents")
        self.update_sp500_constituents(db, today)
    except Exception:
      logger.exception("Error ensuring constituents present")
      raise
  
  def update_sp500_constituents(self, db: Session, target_date: date) -> int:
    """
    Fetch the top S&P 500 constituents from S3, deactivate all existing entries,
    upsert the new list, and return how many were processed.
    """
    
    logger.info(f"Loading S&P 500 constituents from S3 for {target_date}")
    
    try:
      new_list = self.load_top_constituents_s3(target_date)
      self.upsert_all_constituents(db, new_list)
      
      # Deactivate all current constituents
      symbols = [item["symbol"] for item in new_list]
      db.query(IndexConstituent).filter(IndexConstituent.symbol.notin_(symbols)).update({"is_active": False}, synchronize_session="fetch")
      db.commit()
      
      logger.info(f"Constituent upsert complete ({len(new_list)} items)")
      return len(new_list)
    except Exception:
      try:
        db.rollback()
      except Exception:
        logger.warning("Rollback failed after constituent-update error", exc_info=True)
      logger.exception(f"Error updating S&P 500 constituents for {target_date}")
      raise
    
  def upsert_all_constituents(self, db: Session, items: List[Dict[str, Any]]) -> None:
    """Activate and update an existing IndexConstituent by symbol, or insert if missing"""
    
    if not items:
      logger.debug("No constituent items to upsert, skipping.")
      return
    
    logger.debug(f"Preparing batch upsert of {len(items)} constituents")
    
    insert_data = [
      {
        "symbol": item["symbol"],
        "company_name": item["company"],
        "weight": item["weight"],
        "is_active": True,
        "added_date": date.today(),
        "updated_at": datetime.now(timezone.utc),
      }
      for item in items
    ]
    
    statement = insert(IndexConstituent).values(insert_data)
    update_statement = statement.on_conflict_do_update(
      index_elements=["symbol"],
      set_={
        "company_name": statement.excluded.company_name,
        "weight": statement.excluded.weight,
        "is_active": True,
        "updated_at": statement.excluded.updated_at,
      },
    )
    
    try:
      db.execute(update_statement)
      logger.info(f"Successfully upserted {len(items)} constituents.")
    except SQLAlchemyError:
      logger.exception("Database error during batch upsert of constituents.")
      raise
  
  def get_index_level(self, db: Session, target_date: date) -> Optional[float]:
    """Fetch S&P 500 index level (current close price) from DB"""
    
    try:
      summary = db.query(IndexSummary).filter_by(date=target_date).one_or_none()
      
      if summary:
        price = summary.current_price
        logger.debug(f"Index level for {target_date}: {price}")
        return price
      
      logger.warning(f"No IndexSummary record found for date {target_date}")
      return None
    except Exception:
      logger.exception(f"Error fetching index level for date {target_date}")
      try:
        db.rollback()
      except Exception:
        logger.warning(f"Rollback failed after querying index level for {target_date}")
      raise
  
  def fetch_daily_prices(self, db: Session, symbols: List[str], target_date: date) -> Dict[str, Dict]:
    """Fetch daily prices for given symbols"""
    
    prices: Dict[str, Dict] = {}
    total = len(symbols)
    logger.info(f"Starting price fetch for {total} symbols on {target_date}")
    
    for idx, symbol in enumerate(symbols, start=1):
      try:
        if idx % 10 == 0:
          logger.info(f"[{idx}/{total}] Processed symbol: {symbol}")
        
        quote = self.client.quote(symbol)
        if not quote or quote.get("c") is None:
          logger.warning(f"No valid quote for {symbol}; skipping")
          continue
        
        price_data = {
          "current_price":  quote["c"],
          "change":         quote["d"],
          "percent_change": quote["dp"],
          "high":           quote["h"],
          "low":            quote["l"],
          "open":           quote["o"],
          "previous_close": quote["pc"]
        }
        prices[symbol] = price_data
        
        existing = db.query(DailyPrice).filter_by(symbol=symbol, date=target_date).one_or_none()
        if existing:
          continue
        
        constituent = db.query(IndexConstituent).filter_by(symbol=symbol).one_or_none()
        if not constituent:
          logger.warning(f"No constituent entry for {symbol}; cannot persist price")
          continue
        
        db.add(DailyPrice(
          constituent_id=constituent.id,
          symbol=symbol,
          date=target_date,
          current_price=quote["c"],
          change=quote["d"],
          percent_change=quote["dp"],
          high=quote["h"],
          low=quote["l"],
          open=quote["o"],
          previous_close=quote["pc"]
        ))
      except Exception:
        logger.exception(f"Error processing price for {symbol}")
        
    try:
      db.commit()
      logger.info(f"Committed {len(prices)} price records to DB")
    except Exception:
      logger.exception("Failed to commit DailyPrice records")
      db.rollback()
      raise
    
    return prices

  def calculate_index_impact(self, percent_change: float, weight: float, index_level: float) -> float:
    """Calculate how many index points a stock's move contributed"""
    
    index_contribution_pct = (weight * percent_change) / 100
    index_points = (index_contribution_pct * index_level) / 100
    return round(index_points, 2)
  
  def get_or_fetch_index_summary(self, db: Session, target_date: date) -> Dict:
    """Get index summary from DB or fetch from Finnhub"""
    
    try:
      logger.debug(f"Looking up IndexSummary for {target_date}")
      summary = db.query(IndexSummary).filter_by(date=target_date).one_or_none()
      
      if summary:
        logger.info(f"Found existing summary for {target_date}: price={summary.current_price}, pct_change={summary.percent_change}")
        return {
          "current_price":    summary.current_price,
          "change":           summary.change,
          "percent_change":   summary.percent_change,
          "high":             summary.high,
          "low":              summary.low,
          "open":             summary.open,
          "previous_close":   summary.previous_close,
        }
      
      logger.info(f"No summary for {target_date}; fetching SPY quote")
      spy_quote = self.client.quote("SPY")
      if not spy_quote or spy_quote.get("c") is None:
        logger.error(f"Invalid SPY quote for {target_date}: {spy_quote}")
        raise RuntimeError(f"SPY quote missing or incomplete for {target_date}")
      
      new_summary = IndexSummary(
        date=           target_date,
        current_price=  spy_quote["c"]  * 10,
        change=         spy_quote["d"]  * 10,
        percent_change= spy_quote["dp"],
        high=           spy_quote["h"]  * 10,
        low=            spy_quote["l"]  * 10,
        open=           spy_quote["o"]  * 10,
        previous_close= spy_quote["pc"] * 10,
      )
      db.add(new_summary)
      db.commit()
      logger.info(f"Saved summary for {target_date}")
      
      return {
        "current_price":    new_summary.current_price,
        "change":           new_summary.change,
        "percent_change":   new_summary.percent_change,
        "high":             new_summary.high,
        "low":              new_summary.low,
        "open":             new_summary.open,
        "previous_close":   new_summary.previous_close,
      }
    except Exception:
      logger.exception(f"Failed to get or fetch index summary for {target_date}")
      try:
        db.rollback()
      except Exception:
        logger.warning(f"Rollback failed after error fetching summary for {target_date}")
      raise

  def identify_top_movers(self, db: Session, target_date: date) -> Tuple[List[Dict], List[Dict]]:
    """Identify top 5 gainers and losers by index impact"""

    try:
      logger.info(f"Starting top-movers calculation for {target_date}")
      index_level = self.get_index_level(db, target_date)
      if index_level is None:
        message = f"Index level not available for {target_date}"
        logger.error(message)
        raise ValueError(message)
      
      constituents = db.query(IndexConstituent).filter_by(is_active=True).all()
      if not constituents:
        logger.warning(f"No active constituents for {target_date}; triggering update")
        self.update_sp500_constituents(db, target_date)
        constituents = db.query(IndexConstituent).filter_by(is_active=True).all()
      
      symbols = [c.symbol for c in constituents]
      records = db.query(DailyPrice).filter(DailyPrice.date == target_date, DailyPrice.symbol.in_(symbols)).all()
      prices = {r.symbol: r for r in records}
      logger.info(f"Fetched prices for {len(prices)}/{len(symbols)} symbols")
      
      movers = []
      for c in constituents:
        p = prices.get(c.symbol)
        
        if not p or p.percent_change is None:
          logger.debug(f"Skipping {c.symbol}: missing data")
          continue
        
        impact = self.calculate_index_impact(
          percent_change=p.percent_change,
          weight=c.weight,
          index_level=index_level
        )
        
        mover = {
          "symbol": c.symbol,
          "company_name": c.company_name,
          "percent_change": p.percent_change,
          "close_price": p.current_price,
          "index_points_contribution": impact,
          "constituent_id": c.id
        }
        movers.append(mover)
      
      movers.sort(key=lambda m: abs(m["index_points_contribution"]), reverse=True)
      gainers = [m for m in movers if m["percent_change"] > 0][:5]
      losers  = [m for m in movers if m["percent_change"] < 0][:5]
      
      for rank, g in enumerate(gainers, start=1):
        db.add(MarketMover(
          date=target_date,
          constituent_id=g["constituent_id"],
          symbol=g["symbol"],
          company_name=g["company_name"],
          percent_change=g["percent_change"],
          index_points_contribution=g["index_points_contribution"],
          close_price=g["close_price"],
          rank=rank,
          mover_type="gainer"
        ))
      
      for rank, l in enumerate(losers, start=1):
        db.add(MarketMover(
          date=target_date,
          constituent_id=l["constituent_id"],
          symbol=l["symbol"],
          company_name=l["company_name"],
          percent_change=l["percent_change"],
          index_points_contribution=l["index_points_contribution"],
          close_price=l["close_price"],
          rank=-rank,
          mover_type="loser"
        ))
      
      db.commit()
      logger.info(f"Identified {len(gainers)} gainers and {len(losers)} losers for {target_date}")
      if gainers:
        tg = gainers[0]
        logger.info(f"Top gainer: {tg['symbol']} +{tg['percent_change']:.2f}%")
      if losers:
        tl = losers[0]
        logger.info(f"Top loser: {tl['symbol']} {tl['percent_change']:.2f}%")

      return gainers, losers
    except Exception as err:
      logger.exception(f"Error identifying top movers for {target_date}: {err}")
      try:
        db.rollback()
        logger.debug(f"Rolled back transaction for {target_date}")
      except Exception as rb:
        logger.error(f"Rollback failed for {target_date}: {rb}")
      return [], []
  
  def get_stock_fundamentals(self, symbol: str) -> Dict:
    try:
      logger.info(f"Fetching fundamentals for {symbol}")
      profile = self.client.company_profile2(symbol=symbol)
      if not profile:
        logger.warning(f"No fundamentals data returned for {symbol}")
        return {}
      
      fundamentals = {
        "market_cap": profile.get("marketCapitalization", 0) * 1_000_000,
        "name":       profile.get("name", ""),
        "industry":   profile.get("finnhubIndustry", ""),
        "logo":       profile.get("logo", ""),
        "weburl":     profile.get("weburl", "")
      }
      logger.debug(f"Fetched fundamentals for {symbol}: {fundamentals}")
      return fundamentals
    except Exception:
      logger.exception(f"Error fetching fundamentals for {symbol}")
      return {}
  
  def get_market_status(self) -> Dict[str, Any]:
    """
    Check whether the US market is open, returning session info.
    On error, logs the exception and returns a default “closed” status with an error message.
    """
    try:
      logger.info("Checking market status")
      status = self.client.market_status(exchange="US")

      is_open = status.get("isOpen", False)
      session = status.get("session", "closed")
      tz      = status.get("timezone", "America/New_York")

      logger.info(f"Market status: {session} (open: {is_open})")
      return {
        "is_open":      is_open,
        "session":      session,
        "timezone":     tz
      }
    except Exception as err:
      logger.exception("Error checking market status")
      return {
        "is_open": False,
        "session": "unknown",
        "error": str(err)
      }
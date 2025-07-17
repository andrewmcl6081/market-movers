from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import date, datetime
from typing import List, Optional
from pydantic import BaseModel

from app.db.connection import get_db
from app.db.models import IndexConstituent, DailyPrice, IndexSummary
from app.services.market_data_service import MarketDataService
from app.schemas.index_summary import ConstituentResponse, PriceResponse, IndexResponse, MarketStatusResponse

router = APIRouter()

@router.get("/status", response_model=MarketStatusResponse)
async def get_market_status():
  """Get current market status"""
  service = MarketDataService()
  status = service.get_market_status()
  
  return MarketStatusResponse(
    is_open=status.get("is_open", False),
    session=status.get("session", "closed"),
    timezone=status.get("timezone", "America/New_York")
  )

@router.get("/constituents", response_model=List[ConstituentResponse])
async def get_constituents(active_only: bool = True, db: Session = Depends(get_db)):
  """Get S&P 500 top 50 constituents"""
  
  query = db.query(IndexConstituent)
  
  if active_only:
    query = query.filter_by(is_active=True)
  
  constituents = query.order_by(IndexConstituent.weight.desc()).all()
  
  return [
    ConstituentResponse(
      symbol=c.symbol,
      company_name=c.company_name,
      sector=c.sector,
      weight=c.weight,
      is_active=c.is_active
    ) for c in constituents
  ]

@router.get("/prices/{symbol}", response_model=PriceResponse)
async def get_stock_price(symbol: str, price_date: Optional[date] = None, db: Session = Depends(get_db)):
  """Get price data for a specific stock"""
  
  if not price_date:
    price_date = date.today()
    
  price = db.query(DailyPrice).filter_by(symbol=symbol.upper(), date=price_date).first()
  
  if not price:
    # Try to fetch fresh data
    service = MarketDataService()
    prices = service.fetch_daily_prices(db, [symbol.upper()], price_date)
    
    if symbol.upper() not in prices:
      raise HTTPException(status_code=404, detail=f"No price data found for {symbol} on {price_date}")
    
    # Fetch again from DB
    price = db.query(DailyPrice).filter_by(symbol=symbol.upper(), date=price_date).first()
  
  return PriceResponse(
    symbol=price.symbol,
    date=price.date,
    current_price=price.current_price,
    change=price.change,
    percent_change=price.percent_change,
    high=price.high,
    low=price.low,
    open=price.open,
    previous_close=price.previous_close
  )

@router.get("/index", response_model=IndexResponse)
async def get_index_data(index_date: Optional[date] = None, db: Session = Depends(get_db)):
  """Get S&P 500 index data"""
  
  if not index_date:
    index_date = date.today()
  
  service = MarketDataService()
  index_data = service.get_or_fetch_index_summary(db, index_date)
  
  if not index_data:
    raise HTTPException(status_code=404, detail=f"No index data found for {index_date}")
  
  return IndexResponse(
    date=index_date,
    **index_data
  )
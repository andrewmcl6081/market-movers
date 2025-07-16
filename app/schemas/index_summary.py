from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel

class ConstituentResponse(BaseModel):
  symbol: str
  company_name: str
  sector: Optional[str] = None
  weight: float
  is_active: bool
  
class PriceResponse(BaseModel):
  symbol: str
  date: date
  current_price: float
  change: float
  percent_change: float
  high: float
  low: float
  open: float
  previous_close: float

class IndexResponse(BaseModel):
  date: date
  current_price: float
  change: float
  percent_change: float
  high: float
  low: float
  open: float
  previous_close: float

class MarketStatusResponse(BaseModel):
  is_open: bool
  session: str
  timezone: str
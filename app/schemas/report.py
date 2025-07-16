from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel

class ReportSummaryResponse(BaseModel):
  report_date: date
  generated_at: datetime
  index_close: float
  index_change_pct: float
  index_change_points: float
  email_sent: bool
  constituents_processed: int
  news_articles_analyzed: int

class MoverResponse(BaseModel):
  symbol: str
  company_name: str
  percent_change: float
  close_price: float
  index_points_contribution: float
  rank: int
  mover_type: str
  positive_headline: Optional[str] = None
  negative_headline: Optional[str] = None

class IndexSummaryResponse(BaseModel):
  date: date
  current_price: float
  change: float
  percent_change: float
  high: float
  low: float
  open: float
  previous_close: float
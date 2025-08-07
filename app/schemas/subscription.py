from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr

class SubscriptionCreate(BaseModel):
  email: EmailStr
  timezone: str = "America/New_York"

class SubscriptionResponse(BaseModel):
  id: int
  email: str
  send_daily_report: bool
  subscribed_at: datetime
  timezone: str
  last_email_sent: Optional[datetime] = None
  total_emails_sent: int
  
  class Config:
    from_attributes = True
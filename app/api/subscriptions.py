from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import EmailStr
from datetime import datetime, timezone
from typing import List

from app.db.connection import get_db
from app.utils.db import db_safe_execute
from app.db.models import UserSubscription
from app.schemas.subscription import SubscriptionCreate, SubscriptionResponse

router = APIRouter()

@router.post("/subscribe", response_model=SubscriptionResponse)
async def subscribe(subscription: SubscriptionCreate, db: Session = Depends(get_db)):
  """Subscribe to daily reports"""
  
  def perform_subscription():
    existing = db.query(UserSubscription).filter_by(email=subscription.email).first()
    
    if existing:
      if existing.send_daily_report:
        raise HTTPException(status_code=400, detail="Email already subscribed")

      # Reactivate subscription
      existing.send_daily_report = True
      existing.unsubscribed_at = None
      existing.timezone = subscription.timezone
      return existing
    
    # Create new subscription
    new_sub = UserSubscription(
      email=subscription.email,
      timezone=subscription.timezone,
      send_daily_report=True
    )
    db.add(new_sub)
    db.flush()
    db.refresh(new_sub)
    return new_sub
  
  return db_safe_execute(db, perform_subscription)

@router.post("/unsubscribe")
async def unsubscribe(email: EmailStr, db: Session = Depends(get_db)):
  """Unsubscribe from daily reports"""
  
  def perform_unsubscribe():
    subscription = db.query(UserSubscription).filter_by(email=email).first()
    
    if not subscription:
      raise HTTPException(status_code=404, detail="Subscription not found")
    
    subscription.send_daily_report = False
    subscription.unsubscribed_at = datetime.now(timezone.utc)
    
    return {"message": "Successfully unsubscribed"}
  
  return db_safe_execute(db, perform_unsubscribe)

@router.get("/subscribers", response_model=List[SubscriptionResponse])
async def list_subscribers(active_only: bool = True, db: Session = Depends(get_db)):
  """List all subscribers"""
  
  def get_subscribers():
    query = db.query(UserSubscription)
    if active_only:
      query = query.filter_by(send_daily_report=True)
    return query.all()
  
  return db_safe_execute(db, get_subscribers, commit=False)

@router.get("/subscriber/{email}", response_model=SubscriptionResponse)
async def get_subscriber(email: EmailStr, db: Session = Depends(get_db)):
  """Get subscriber details"""
  
  def fetch_subscription():
    subscription = db.query(UserSubscription).filter_by(email=email).first()
    if not subscription:
      raise HTTPException(status_code=404, detail="Subscription not found")
    return subscription
  
  return db_safe_execute(db, fetch_subscription, commit=False)

@router.put("/subscriber/{email}/timezone")
async def update_timezone(email: EmailStr, timezone: str, db: Session = Depends(get_db)):
  """Update subscriber timezone"""
  
  def perform_update():
    subscription = db.query(UserSubscription).filter_by(email=email).first()
    
    if not subscription:
      raise HTTPException(status_code=404, detail="Subscription not found")
    
    subscription.timezone = timezone
    subscription.updated_at = datetime.now(timezone.utc)
    
    return {
      "message": "Timezone updated successfully",
      "timezone": timezone
    }
  
  return db_safe_execute(db, perform_update)
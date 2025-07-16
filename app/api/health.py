from sqlalchemy import text
from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends
from datetime import datetime, timezone

from app.db.connection import get_db
from app.services.sentiment_model import get_sentiment_model
from app.services.finnhub_client import get_finnhub_client

router = APIRouter()

@router.get("/")
async def health_check():
  """Basic health check"""
  
  return {
    "status": "healthy",
    "timestamp": datetime.now(timezone.utc).isoformat(),
    "service": "Market Movers Daily"
  }

@router.get("/database")
async def database_health(db: Session = Depends(get_db)):
  """Check database connectivity"""
  
  try:
    result = db.execute(text("SELECT 1"))
    return {
      "status": "healthy",
      "database": "connected",
      "timestamp": datetime.now(timezone.utc).isoformat()
    }
  except Exception as e:
    return {
      "status": "unhealthy",
      "database": "disconnected",
      "error": str(e),
      "timestamp": datetime.now(timezone.utc).isoformat()
    }
  
@router.get("/services")
async def services_health():
  """Check all services statuses"""
  
  services_status = {}
  
  # Check sentiment model
  try:
    model = get_sentiment_model()
    services_status["sentiment_model"] = model.get_status()
  except Exception as e:
    services_status["sentiment_model"] = {
      "status": "error",
      "error": str(e)
    }
  
  # Check Finnhub API
  try:
    client = get_finnhub_client()
    client.market_status(exchange="US")
    services_status["finnhub_api"] = {
      "status": "connected",
      "initialized": True
    }
  except Exception as e:
    services_status["finnhub_api"] = {
      "status": "error",
      "error": str(e)
    }
  
  overall_status = all(
    s.get("status") != "error" and s.get("initialized", True) for s in services_status.values()
  )
  
  return {
    "status": "healthy" if overall_status else "degraded",
    "services": services_status,
    "timestamp": datetime.now(timezone.utc).isoformat()
  }
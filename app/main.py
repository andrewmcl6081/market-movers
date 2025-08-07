import logging
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from datetime import datetime, timezone, date
from typing import Optional

from app.config import get_config
from app.logging_config import setup_logging
from app.db.connection import get_db, init_db
from app.db.models import DailyReport
from app.api import health, reports, market_data, subscriptions
from app.services.report_scheduler import ReportScheduler
from app.services.report_generator import ReportGenerator
from app.db.models import UserSubscription

setup_logging()
logger = logging.getLogger(__name__)

config = get_config()

scheduler = ReportScheduler()

@asynccontextmanager
async def lifespan(app: FastAPI):
  """Manage application lifecycle"""
  
  logger.info("Starting Market Movers Daily API...")
  
  if config.ENVIRONMENT in ("development", "test"):
    init_db()
  
  scheduler.start()
  logger.info("Report scheduler started")
  
  yield
  
  logger.info("Shutting down...")
  scheduler.shutdown()
  logger.info("Scheduler stopped")

app = FastAPI(
  title=config.PROJECT_NAME,
  version="1.0.0",
  description="Market Movers Daily - S&P 500 Top Movers Analysis & Reporting",
  lifespan=lifespan
)

app.add_middleware(
  CORSMiddleware,
  allow_origins=["*"],
  allow_credentials=True,
  allow_methods=["*"],
  allow_headers=["*"],
)

app.include_router(health.router, prefix="/api/v1/health", tags=["health"])
app.include_router(reports.router, prefix="/api/v1/reports", tags=["reports"])
app.include_router(market_data.router, prefix="/api/v1/market", tags=["market"])
app.include_router(subscriptions.router, prefix="/api/v1/subscriptions", tags=["subscriptions"])

@app.get("/")
async def root():
  return {
    "message": "Market Movers Daily API",
    "version": "1.0.0",
    "docs": "/docs",
    "health": "/api/v1/health"
  }

@app.post("/api/v1/reports/generate-now")
async def generate_report_now(background_tasks: BackgroundTasks, target_date: Optional[date] = None, db: Session = Depends(get_db)):
  if not target_date:
    target_date = datetime.now(timezone.utc).date()
  
  existing = db.query(DailyReport).filter_by(report_date=target_date).first()
  if existing:
    return {
      "message": "Report already exists",
      "report_date": target_date,
      "generated_at": existing.generated_at
    }
  
  background_tasks.add_task(
    ReportGenerator().generate_and_send_report,
    target_date
  )
  
  return {
    "message": "Report generation started",
    "report_date": target_date,
    "status": "processing"
  }

if __name__ == "__main__":
  uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=config.ENVIRONMENT == "development")
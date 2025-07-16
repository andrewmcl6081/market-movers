from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from datetime import date
from typing import List, Optional

from app.db.connection import get_db
from app.db.models import DailyReport, MarketMover, IndexSummary
from app.schemas.report import ReportSummaryResponse, MoverResponse

router = APIRouter()

@router.get("/latest", response_model=ReportSummaryResponse)
async def get_latest_report(db: Session = Depends(get_db)):
  """Get the most recent report"""
  
  report = db.query(DailyReport).order_by(DailyReport.report_date.desc()).first()
  
  if not report:
    raise HTTPException(status_code=404, detail="No reports found")
  
  return ReportSummaryResponse(
    report_date=report.report_date,
    generated_at=report.generated_at,
    index_close=report.index_close,
    index_change_pct=report.index_change_pct,
    index_change_points=report.index_change_points,
    email_sent=report.email_sent,
    constituents_processed=report.constituents_processed,
    news_articles_analyzed=report.news_articles_analyzed
  )

@router.get("/{report_date}", response_model=ReportSummaryResponse)
async def get_report_by_date(report_date: date, db: Session = Depends(get_db)):
  """Get report for specific date"""
  
  report = db.query(DailyReport).filter_by(report_date=report_date).first()
  
  if not report:
    raise HTTPException(status_code=404, detail=f"No report found for {report_date}")
  
  return ReportSummaryResponse(
    report_date=report.report_date,
    generated_at=report.generated_at,
    index_close=report.index_close,
    index_change_pct=report.index_change_pct,
    index_change_points=report.index_change_points,
    email_sent=report.email_sent,
    constituents_processed=report.constituents_processed,
    news_articles_analyzed=report.news_articles_analyzed
  )

@router.get("/{report_date}/html", response_class=HTMLResponse)
async def get_report_html(report_date: date, db: Session = Depends(get_db)):
  """Get report HTML content"""
  
  report = db.query(DailyReport).filter_by(report_date=report_date).first()
  
  if not report:
    raise HTTPException(status_code=404, detail=f"No report found {report_date}")
  
  if not report.html_content:
    raise HTTPException(status_code=404, detail="HTML content not available for this report")
  
  return HTMLResponse(content=report.html_content)

@router.get("/{report_date}/movers", response_model=List[MoverResponse])
async def get_report_movers(report_date: date, mover_type: Optional[str] = None, db: Session = Depends(get_db)):
  """Get market movers for a specific day"""
  
  query = db.query(MarketMover).filter_by(date=report_date)
  
  if mover_type:
    query = query.filter_by(mover_type=mover_type)
  
  movers = query.order_by(MarketMover.rank).all()
  
  if not movers:
    raise HTTPException(status_code=404, detail=f"No movers found for {report_date}")
  
  return [
    MoverResponse(
      symbol=m.symbol,
      company_name=m.company_name,
      percent_change=m.percent_change,
      close_price=m.close_price,
      index_points_contribution=m.index_points_contribution,
      rank=m.rank,
      mover_type=m.mover_type,
      positive_headline=m.positive_headline,
      negative_headline=m.negative_headline
    ) for m in movers
  ]

@router.get("/", response_model=List[ReportSummaryResponse])
async def list_reports(start_date: Optional[date] = None, end_date: Optional[date] = None, limit: int = 30, db: Session = Depends(get_db)):
  """List available reports"""
  
  query = db.query(DailyReport)
  
  if start_date:
    query = query.filter(DailyReport.report_date >= start_date)
  if end_date:
    query = query.filter(DailyReport.report_date <= end_date)
  
  reports = query.order_by(DailyReport.report_date.desc()).limit(limit).all()
  
  if not reports:
    raise HTTPException(status_code=404, detail="No reports available for the given date range")
  
  return [
    ReportSummaryResponse(
      report_date=r.report_date,
      generated_at=r.generated_at,
      index_close=r.index_close,
      index_change_pct=r.index_change_pct,
      index_change_points=r.index_change_points,
      email_sent=r.email_sent,
      constituents_processed=r.constituents_processed,
      news_articles_analyzed=r.news_articles_analyzed
    ) for r in reports
  ]
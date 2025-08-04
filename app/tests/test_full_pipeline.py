import os
import pytest
import logging
from datetime import date
from sqlalchemy import text
from app.db.models import Base, IndexConstituent, DailyPrice, IndexSummary, MarketMover, NewsArticle, DailyReport
from app.db.connection import get_engine, get_session_local
from app.services.report_generator import ReportGenerator

logger = logging.getLogger(__name__)

class TestPipeline:
  @pytest.fixture(scope="class")
  def db_engine(self):
    engine = get_engine()
    
    # logger.info("Clearing database before pipeline test...")
    # Base.metadata.drop_all(bind=engine)
    # Base.metadata.create_all(bind=engine)
    
    return engine
  
  @pytest.fixture(scope="class")
  def db_session(self, db_engine):
    SessionLocal = get_session_local(db_engine)
    session = SessionLocal()
    yield session
    session.close()
  
  @pytest.fixture(scope="class")
  def report_date(self):
    return date.today()
  
  @pytest.fixture(scope="class", autouse=True)
  def run_pipeline(self, db_engine, report_date):
    logger.info(f"Starting full pipeline test for {report_date}")
    logger.info(f"Test mode: Processing {os.getenv('TEST_STOCK_COUNT', '10')} stocks")
    
    generator = ReportGenerator()
    success = generator.generate_and_send_report(report_date)
    
    assert success, "Report generation failed"
    
    SessionLocal = get_session_local(db_engine)
    session = SessionLocal()
    try:
      stats = {
        "constituents": session.query(IndexConstituent).count(),
        "prices": session.query(DailyPrice).filter_by(date=report_date).count(),
        "movers": session.query(MarketMover).filter_by(date=report_date).count(),
        "news": session.query(NewsArticle).filter_by(date=report_date).count(),
        "reports": session.query(DailyReport).count()
      }
      logger.info(f"Pipeline stats: {stats}")
    finally:
      session.close()
    
    return success
  
  def test_constituents_loaded(self, db_session):
    count = db_session.query(IndexConstituent).filter_by(is_active=True).count()
    logger.info(f"Constituents loaded: {count}")
    assert count == 50, f"Expected 50 constituents, got {count}"
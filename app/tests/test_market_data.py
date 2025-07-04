import pytest
import finnhub
from datetime import date
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from db.models import Base, IndexConstituent, DailyPrice, IndexSummary
from services.market_data import MarketDataService

@pytest.fixture
def sqlite_session():
  engine = create_engine("sqlite:///:memory:")
  Session = sessionmaker(bind=engine)
  Base.metadata.create_all(engine)
  session = Session()
  try:
    yield session
  finally:
    session.close()
    engine.dispose()

@pytest.fixture
def sample_constituent(sqlite_session):
  stock = IndexConstituent(
    symbol="AAPL",
    company_name="Apple Inc.",
    weight=6.5,
    is_active=True
  )
  sqlite_session.add(stock)
  sqlite_session.commit()
  return stock

def test_update_sp500_constituents(sqlite_session):
  service = MarketDataService()
  updated_count = service.update_sp500_constituents(sqlite_session)
  
  print(f"\nUpdated {updated_count} constituents.")
  
  all_constituents = sqlite_session.query(IndexConstituent).all()
  print("\nConstituents in DB:")
  
  for c in all_constituents:
    print(f" - Symbol: {c.symbol}, Name: {c.company_name}, Weight: {c.weight}, Active: {c.is_active}")
  
  assert updated_count == 50
  assert len(all_constituents) == 50
  assert all(c.is_active for c in all_constituents)

def test_fetch_daily_prices(sqlite_session, monkeypatch, sample_constituent):
  service = MarketDataService()
  
  fake_quote = {
    "c": 180.0,
    "d": 2.0,
    "dp": 1.1,
    "h": 182.0,
    "l": 179.0,
    "o": 180.5,
    "pc": 178.0
  }
  
  monkeypatch.setattr(service.client, "quote", lambda symbol: fake_quote)
  
  target_date = date.today()
  result = service.fetch_daily_prices(sqlite_session, ["AAPL"], target_date)
  
  assert "AAPL" in result
  assert result["AAPL"]["current_price"] == 180.0
  assert result["AAPL"]["percent_change"] == 1.1
  
  # Confirm price was stored in DB
  db_price = sqlite_session.query(DailyPrice).filter_by(symbol="AAPL", date=target_date).first()
  assert db_price is not None
  assert db_price.current_price == 180.0
  assert db_price.percent_change == 1.1
  
def test_calculate_index_impact():
  service = MarketDataService()
  
  # Inputs: AAPL moved +1.5%, has 6% index weight, index level = 5000
  result = service.calculate_index_impact("AAPL", price_change_pct=1.5, weight=6.0, index_level=5000.0)
  
  # Expected: (6 * 1.5) / 100 = 0.09%, 0.09% * 5000 = 4.5 points
  assert result == 4.5
  
def test_get_index_summary_and_index_level(sqlite_session, monkeypatch):
  service = MarketDataService()
  target_date = date.today()
  
  # Mock Finnhub quote for SPY
  spy_quote = {
    "c": 500.0,
    "d": 4.0,
    "dp": 0.8,
    "h": 505.0,
    "l": 495.0,
    "o": 498.0,
    "pc": 496.0
  }
  monkeypatch.setattr(service.client, "quote", lambda symbol: spy_quote)
  
  summary = service.get_index_summary(sqlite_session, target_date)
  assert summary["current_price"] == 500.0
  assert summary["change"] == 4.0
  assert summary["percent_change"] == 0.8
  
  # Confirm it saved to DB
  saved = sqlite_session.query(IndexSummary).filter_by(date=target_date).first()
  assert saved is not None
  assert saved.current_price == 500.0
  
  # Run get_index_level and confirm it reads from DB
  index_level = service.get_index_level(sqlite_session, target_date)
  assert index_level == 500.0
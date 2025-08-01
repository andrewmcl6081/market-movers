import pytest
from datetime import date
from app.db.models import IndexConstituent, DailyPrice, IndexSummary
from app.services.market_data_service import MarketDataService

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
  
def test_identify_top_movers(sqlite_session):
  service = MarketDataService()
  target_date = date.today()
  
  index_summary = IndexSummary(
    date=target_date,
    current_price=5000.0,
    change=50.0,
    percent_change=1.0,
    high=5050.0,
    low=4950.0,
    open=4980.0,
    previous_close=4950.0
  )
  sqlite_session.add(index_summary)
  
  constituents = [
    IndexConstituent(symbol="AAPL", company_name="Apple", weight=6.5, is_active=True),
    IndexConstituent(symbol="MSFT", company_name="Microsoft", weight=6.0, is_active=True),
    IndexConstituent(symbol="TSLA", company_name="Tesla", weight=4.0, is_active=True)
  ]
  sqlite_session.add_all(constituents)
  sqlite_session.commit()
  
  daily_prices = [
    DailyPrice(symbol="AAPL", constituent_id=constituents[0].id, date=target_date, current_price=200.0, percent_change=2.0),
    DailyPrice(symbol="MSFT", constituent_id=constituents[1].id, date=target_date, current_price=300.0, percent_change=-1.5),
    DailyPrice(symbol="TSLA", constituent_id=constituents[2].id, date=target_date, current_price=180.0, percent_change=0.5),
  ]
  sqlite_session.add_all(daily_prices)
  sqlite_session.commit()
  
  gainers, losers = service.identify_top_movers(sqlite_session, target_date)
  
  print("\nGainers:")
  for g in gainers:
    print(g)
  
  print("\nLosers:")
  for l in losers:
    print(l)
  
  assert len(gainers) == 2
  assert len(losers) == 1
  
  assert gainers[0]["symbol"] == "AAPL"
  assert losers[0]["symbol"] == "MSFT"

def test_get_market_status_real():
  service = MarketDataService()
  status = service.get_market_status()
  
  print("\nMarket Status:", status)
  
  assert isinstance(status, dict)
  assert "is_open" in status
  assert "session" in status
  assert "timezone" in status
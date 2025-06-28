import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from db.models import Base, IndexConstituent
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
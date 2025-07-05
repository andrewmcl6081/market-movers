import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db.models import Base

@pytest.fixture(scope="function")
def sqlite_session():
  engine = create_engine("sqlite:///:memory:")
  Session = sessionmaker(bind=engine)
  
  Base.metadata.bind = None
  Base.metadata.drop_all(bind=engine)
  Base.metadata.create_all(bind=engine)
  
  session = Session()
  try:
    yield session
  finally:
    session.close()
    engine.dispose()
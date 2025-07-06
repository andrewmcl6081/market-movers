import os
import pytest
from pathlib import Path
from dotenv import load_dotenv
from app.db.models import Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

def pytest_configure(config):
  root_dir = Path(__file__).resolve().parents[2]
  env_path = root_dir / ".env.test"
  
  load_dotenv(dotenv_path=env_path, override=True)

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
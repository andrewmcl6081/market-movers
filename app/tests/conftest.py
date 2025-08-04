import os
import pytest
import logging
from pathlib import Path
from dotenv import load_dotenv

logging.basicConfig(
  level=logging.INFO,
  format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def pytest_configure(config):
  root_dir = Path(__file__).resolve().parents[2]
  env_test_path = root_dir / ".env.test"
  
  if env_test_path.exists():
    load_dotenv(dotenv_path=env_test_path, override=True)
    print(f"Loaded test environment from {env_test_path}")
  else:
    print(f"No .env.test found at {env_test_path}, using .env")
    env_path = root_dir / ".env"
    if env_path.exists():
      load_dotenv(dotenv_path=env_path, override=True)
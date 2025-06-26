from functools import lru_cache
import json
from pathlib import Path
from typing import List, Dict

_DATA_FILE = Path(__file__).parent / "sp500_top.json"

@lru_cache(maxsize=1)
def load_sp500_defaults() -> List[Dict]:
  with _DATA_FILE.open("r", encoding="utf-8") as fh:
    return json.load(fh)
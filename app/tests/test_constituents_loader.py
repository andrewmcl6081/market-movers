from market_data.constituents_loader import load_sp500_defaults

def test_loader_returns_list_of_dicts():
  data = load_sp500_defaults()
  second_call = load_sp500_defaults()
  
  assert data is second_call, "lru_cache is not working - got a new object"
  assert isinstance(data, list) and data, "No rows were returned"
  
  required_keys = {"symbol", "name", "weight", "sector"}
  for row in data:
    assert required_keys.issubset(row), f"Row missing keys: {row}"
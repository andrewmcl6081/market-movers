import pytest
from datetime import date, datetime
from app.db.models import MarketMover, NewsArticle
from app.services.news_service import NewsService
from app.services.sentiment_service import get_sentiment_model

@pytest.fixture
def sample_mover(sqlite_session):
  mover = MarketMover(
    date=date.today(),
    constituent_id=1,
    symbol="AAPL",
    company_name="Apple Inc.",
    percent_change=2.5,
    rank=1,
    mover_type="gainer"
  )
  sqlite_session.add(mover)
  sqlite_session.commit()
  return mover

def test_fetch_stock_news(sqlite_session, sample_mover, monkeypatch):
  service = NewsService(get_sentiment_model())
  
  fake_articles = [
    {
      "headline": "Apple hits all-time high",
      "summary": "Apple stock surged today after earnings.",
      "url": "http://news.com/apple1",
      "source": "Reuters",
      "datetime": datetime.now().isoformat()
    },
    {
      "headline": "iPhone sales beat expectations",
      "summary": "Strong iPhone sales lifted Apple stock.",
      "url": "http://news.com/apple2",
      "source": "Bloomberg",
      "datetime": datetime.now().isoformat()
    }
  ]
  
  monkeypatch.setattr(service.client, "company_news", lambda symbol, _from, to: fake_articles)
  
  articles = service.fetch_stock_news(sqlite_session, symbol="AAPL", target_date=date.today())
  for article in articles:
    print(article)
  
  assert len(articles) == 2
  
  stored = sqlite_session.query(NewsArticle).filter_by(symbol="AAPL").all()
  assert len(stored) == 2
  assert stored[0].headline == "Apple hits all-time high"
  assert stored[1].url == "http://news.com/apple2"

def test_analyze_sentiment_with_real_pipeline(sqlite_session):
  from app.services.news_service import NewsService
  from app.services.sentiment_service import get_sentiment_model
  from app.db.models import MarketMover, NewsArticle
  
  target_date = date.today()
  symbol = "AAPL"
  
  mover = MarketMover(
    date=target_date,
    constituent_id=1,
    symbol=symbol,
    company_name="Apple Inc.",
    percent_change=3.0,
    mover_type="gainer",
    rank=1
  )
  sqlite_session.add(mover)
  
  headlines = [
    "Apple stock surges after strong earnings report",
    "iPhone sales exceed Wall Street expectations",
    "Tim Cook praises innovation during quarterly call",
    "Market reacts positively to Apple product launch"
  ]
  
  for i, headline in enumerate(headlines):
    sqlite_session.add(NewsArticle(
      market_mover_id=1,
      symbol=symbol,
      date=target_date,
      headline=headline,
      summary="",
      url=f"http://news.com/apple{i+1}"
    ))
  sqlite_session.commit()
  
  service = NewsService(get_sentiment_model())
  service.analyze_sentiment_for_date(sqlite_session, target_date)
  
  top_articles = sqlite_session.query(NewsArticle).filter_by(symbol=symbol, is_top_headline=True).all()
  all_articles = sqlite_session.query(NewsArticle).filter_by(symbol=symbol).all()
  updated_mover = sqlite_session.query(MarketMover).filter_by(symbol=symbol).first()
  
  print("\nTop Articles\n")
  for article in top_articles:
    print(f"\n{article}")
  
  print("\nAll Articles\n")
  for article in all_articles:
    print(f"\n{article}")
  
  assert len(top_articles) <= 3
  assert all(a.sentiment_label is not None for a in all_articles)
  assert all(a.sentiment_score is not None for a in all_articles)
  assert updated_mover.positive_headline is not None
  assert updated_mover.positive_headline_score is not None
  assert updated_mover.positive_headline_url is not None
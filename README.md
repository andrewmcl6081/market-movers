# Market Movers Daily  
**Daily AI-Powered Insights on S&P 500 Top Movers**  

Market Movers Daily is an automated financial intelligence platform that tracks S&P 500 market movements, identifies the day’s top gainers and losers, analyzes news sentiment, and delivers clean, data-rich reports to email subscribers every market day.  

---

## Key Features  

- **Automated Daily Reports**  
  Runs on a scheduled basis after market close, generating fresh insights without manual intervention.  

- **Top Movers Detection**  
  Identifies the most impactful gainers and losers in the S&P 500 based on index points contribution, not just percentage change.  

- **Real-Time Market Data**  
  Pulls daily prices and index summaries from the Finnhub API, using fresh market close data to ensure accuracy.  

- **News Sentiment Analysis**  
  Retrieves relevant articles for each market mover, runs them through a FinBERT sentiment model, and highlights directionally aligned top headlines.  

- **Cloud-Native Data Pipeline**  
  - S&P 500 constituent and price data stored in Amazon S3  
  - PostgreSQL database (AWS RDS) for historical tracking and report storage  
  - Designed to run seamlessly in containerized environments (Docker + AWS EC2)  

- **Automated Email Delivery**  
  Generates rich HTML reports and sends them directly to active subscribers using SendGrid.  

- **Admin & Subscriber Management**  
  Tracks user subscriptions, email delivery history, and allows controlled test runs with configurable stock limits.  

---

## Technical Overview  

- **Backend Framework:** FastAPI  
- **Database:** PostgreSQL with SQLAlchemy ORM  
- **Task Scheduling:** APScheduler for daily job triggers  
- **Data Sources:** Finnhub API for market and news data  
- **Sentiment Analysis:** FinBERT (Hugging Face Transformers)  
- **Cloud Infrastructure:**  
  - AWS S3 for raw market data storage  
  - AWS RDS for persistent database storage  
  - AWS EC2 for containerized API and job execution  
- **Email Service:** SendGrid API for automated report delivery  

---

## How It Works  

1. **Market Data Collection**  
   - Checks for new daily S&P 500 data in S3 (populated via a separate data ingestion pipeline).  
   - Updates the list of active index constituents and stores their daily price movements in the database.  

2. **Top Movers Calculation**  
   - Determines index points contribution for each constituent.  
   - Selects top gainers and losers based on actual index impact.  

3. **News & Sentiment Analysis**  
   - Fetches recent company news for movers.  
   - Runs sentiment classification and picks top positive/negative headlines aligned with the stock’s movement.  

4. **Report Generation**  
   - Produces a structured HTML report containing:  
     - S&P 500 daily summary (close, change, % change)  
     - Lists of top gainers and losers with stats  
     - Relevant news headlines and sentiment scores  

5. **Delivery**  
   - Stores the report in the database.  
   - Sends it via email to all active subscribers.  

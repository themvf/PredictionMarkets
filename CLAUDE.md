# PredictionMarkets - Agentic AI Framework

## Project Overview
Prediction market monitoring/analysis platform using Kalshi + Polymarket APIs.
No automated trading — monitoring, analysis, and intelligence reports only.

## Key Architecture
- Custom agent framework: BaseAgent -> Discovery, Collection, Analyzer, Alert, Insight
- SQLite database for persistence (data/prediction_markets.db)
- LLM layer: OpenAI GPT-4o for market matching, analysis, reports
- Streamlit multi-page dashboard deployed to Streamlit Cloud

## API Notes
- Kalshi: RSA-PSS signature auth, rate limit 0.06s between calls
- Polymarket: Gamma API (no auth) + CLOB API (no auth for reads)
- All changes must be pushed to GitHub for Streamlit Cloud deployment

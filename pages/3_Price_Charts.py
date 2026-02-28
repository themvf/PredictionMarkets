"""Price Charts — Plotly time series and volume charts."""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from pathlib import Path
import sys

PROJECT_DIR = Path(__file__).resolve().parent.parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from streamlit_app import init_config, init_database, init_queries

st.set_page_config(page_title="Price Charts", page_icon="📈", layout="wide")

config = init_config()
db = init_database(config)
queries = init_queries(db)

st.title("Price Charts")

# Market selector with category filter
col_cat, col_market = st.columns([1, 3])
with col_cat:
    categories = queries.get_distinct_categories()
    chart_category = st.selectbox("Category", ["All"] + categories)

cat_filter = None if chart_category == "All" else chart_category
markets = queries.get_all_markets(category=cat_filter)
if not markets:
    st.info("No markets available. Run agents to populate data.")
    st.stop()

market_options = {
    f"[{m['platform'][0].upper()}] {m['title']}": m["id"]
    for m in markets[:100]
}

with col_market:
    selected = st.selectbox("Select Market", list(market_options.keys()))
market_id = market_options[selected]
market = queries.get_market_by_id(market_id)

# Fetch price history
history = queries.get_price_history(market_id, limit=500)

if not history:
    st.warning("No price history for this market. Data will appear after the Collection Agent runs.")
    st.stop()

df = pd.DataFrame(history)
df["timestamp"] = pd.to_datetime(df["timestamp"])
df = df.sort_values("timestamp")

# Price chart with volume subplot
fig = make_subplots(
    rows=2, cols=1,
    shared_xaxes=True,
    vertical_spacing=0.08,
    row_heights=[0.7, 0.3],
    subplot_titles=("Yes Price", "Volume"),
)

# Yes price line
fig.add_trace(
    go.Scatter(
        x=df["timestamp"],
        y=df["yes_price"],
        mode="lines+markers",
        name="Yes Price",
        line=dict(color="#2196F3", width=2),
        marker=dict(size=4),
    ),
    row=1, col=1,
)

# No price line
if "no_price" in df.columns and df["no_price"].notna().any():
    fig.add_trace(
        go.Scatter(
            x=df["timestamp"],
            y=df["no_price"],
            mode="lines",
            name="No Price",
            line=dict(color="#FF5722", width=2, dash="dash"),
        ),
        row=1, col=1,
    )

# Bid/ask spread
if "best_bid" in df.columns and df["best_bid"].notna().any():
    fig.add_trace(
        go.Scatter(
            x=df["timestamp"],
            y=df["best_bid"],
            mode="lines",
            name="Best Bid",
            line=dict(color="#4CAF50", width=1, dash="dot"),
        ),
        row=1, col=1,
    )
if "best_ask" in df.columns and df["best_ask"].notna().any():
    fig.add_trace(
        go.Scatter(
            x=df["timestamp"],
            y=df["best_ask"],
            mode="lines",
            name="Best Ask",
            line=dict(color="#F44336", width=1, dash="dot"),
        ),
        row=1, col=1,
    )

# Volume bars
if "volume" in df.columns and df["volume"].notna().any():
    fig.add_trace(
        go.Bar(
            x=df["timestamp"],
            y=df["volume"],
            name="Volume",
            marker_color="#9C27B0",
            opacity=0.6,
        ),
        row=2, col=1,
    )

fig.update_layout(
    height=600,
    title=f"{market['title']} ({market['platform'].title()})",
    showlegend=True,
    legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01),
)
fig.update_yaxes(title_text="Price ($)", row=1, col=1)
fig.update_yaxes(title_text="Volume", row=2, col=1)

st.plotly_chart(fig, use_container_width=True)

# Cross-platform overlay
st.divider()
st.subheader("Cross-Platform Overlay")

pairs = queries.get_all_pairs()
matching_pairs = [
    p for p in pairs
    if p.get("kalshi_market_id") == market_id or p.get("polymarket_market_id") == market_id
]

if matching_pairs:
    pair = matching_pairs[0]
    other_id = (
        pair["polymarket_market_id"]
        if pair["kalshi_market_id"] == market_id
        else pair["kalshi_market_id"]
    )
    other_history = queries.get_price_history(other_id, limit=500)

    if other_history:
        other_market = queries.get_market_by_id(other_id)
        df_other = pd.DataFrame(other_history)
        df_other["timestamp"] = pd.to_datetime(df_other["timestamp"])
        df_other = df_other.sort_values("timestamp")

        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(
            x=df["timestamp"], y=df["yes_price"],
            mode="lines", name=f"{market['platform'].title()}",
            line=dict(color="#2196F3", width=2),
        ))
        fig2.add_trace(go.Scatter(
            x=df_other["timestamp"], y=df_other["yes_price"],
            mode="lines", name=f"{other_market['platform'].title()}",
            line=dict(color="#FF9800", width=2),
        ))
        fig2.update_layout(
            title="Cross-Platform Price Overlay",
            yaxis_title="Yes Price ($)",
            height=400,
        )
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("No price history for the matched market yet.")
else:
    st.info("No cross-platform match found for this market.")

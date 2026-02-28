"""Whale Tracker -- monitor large trades on Polymarket."""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from pathlib import Path
import sys
from datetime import datetime

PROJECT_DIR = Path(__file__).resolve().parent.parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from streamlit_app import init_config, init_database, init_queries, get_context

st.set_page_config(page_title="Whale Tracker", page_icon="🐋", layout="wide")

config = init_config()
db = init_database(config)
queries = init_queries(db)

st.title("Whale Tracker")
st.markdown("Monitor large trades (>$5,000) on Polymarket in real-time.")

# Controls
col1, col2, col3 = st.columns(3)
with col1:
    min_size = st.number_input("Min Trade Size ($)", 1000, 1000000, 5000, 1000)
with col2:
    side_filter = st.selectbox("Side", ["All", "BUY", "SELL"])
with col3:
    limit = st.number_input("Show Last", 25, 500, 100)

# Live fetch
if st.button("Fetch Live Whale Trades", type="primary"):
    with st.spinner("Fetching large trades from Polymarket..."):
        try:
            context = get_context()
            from agents.whale_agent import WhaleAgent
            agent = WhaleAgent()
            result = agent.run(context)
            if result.error:
                st.error(f"Error: {result.error}")
            else:
                st.success(result.summary)
            st.rerun()
        except Exception as e:
            st.error(f"Failed: {e}")

st.divider()

# Quick stats
col1, col2, col3 = st.columns(3)
whale_24h = queries.get_whale_trade_count_since(24)
col1.metric("Whale Trades (24h)", whale_24h)

side_param = None if side_filter == "All" else side_filter
trades = queries.get_whale_trades(
    limit=limit,
    min_size=min_size,
    side=side_param,
)

col2.metric("Showing", len(trades))

if not trades:
    st.info("No whale trades found. Click 'Fetch Live Whale Trades' or run the Whale Agent.")
    st.stop()

# Total volume of displayed trades
total_vol = sum(t.get("usdc_size", 0) or 0 for t in trades)
col3.metric("Total Volume", f"${total_vol:,.0f}")

# Trade feed
st.subheader("Recent Whale Activity")
for trade in trades:
    side = trade.get("side", "TRADE")
    usdc = trade.get("usdc_size", 0) or 0
    price = trade.get("price", 0) or 0

    with st.container(border=True):
        col_side, col_detail, col_amount, col_who = st.columns([0.5, 3, 1.5, 2])

        with col_side:
            emoji = "🟢" if side == "BUY" else "🔴"
            st.markdown(f"### {emoji}")

        with col_detail:
            st.markdown(f"**{trade.get('market_title', 'Unknown')}**")
            outcome = trade.get("outcome", "")
            price_str = f"@ ${price:.2f}" if price else ""
            st.caption(f"{side} {outcome} {price_str}")

        with col_amount:
            st.metric("Size", f"${usdc:,.0f}")

        with col_who:
            name = trade.get("user_name") or (trade["proxy_wallet"][:12] + "...")
            badge = " ✅" if trade.get("verified_badge") else ""
            st.markdown(f"**{name}{badge}**")
            ts = trade.get("trade_timestamp")
            if ts:
                try:
                    dt = datetime.fromtimestamp(int(ts))
                    st.caption(dt.strftime("%Y-%m-%d %H:%M"))
                except (ValueError, TypeError):
                    pass

# Volume chart
st.divider()
st.subheader("Whale Trade Volume Over Time")
if trades:
    df = pd.DataFrame(trades)
    if "trade_timestamp" in df.columns and df["trade_timestamp"].notna().any():
        df["time"] = pd.to_datetime(df["trade_timestamp"], unit="s", errors="coerce")
        df = df.dropna(subset=["time"])
        if not df.empty:
            df_grouped = df.set_index("time").resample("1h")["usdc_size"].sum().reset_index()
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=df_grouped["time"],
                y=df_grouped["usdc_size"],
                marker_color="#9C27B0",
                opacity=0.7,
            ))
            fig.update_layout(
                title="Hourly Whale Volume",
                yaxis_title="USD Volume",
                xaxis_title="Time",
                height=350,
            )
            st.plotly_chart(fig, use_container_width=True)

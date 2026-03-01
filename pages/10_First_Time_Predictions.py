"""First-Time Predictions -- track debut trades by new traders."""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from pathlib import Path
import sys
from datetime import datetime, timezone

PROJECT_DIR = Path(__file__).resolve().parent.parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from streamlit_app import init_config, init_database, init_queries

st.set_page_config(
    page_title="First-Time Predictions",
    page_icon="🆕",
    layout="wide",
)

config = init_config()
db = init_database(config)
queries = init_queries(db)

st.title("First-Time Predictions")
st.markdown(
    "Track traders making their **debut prediction** with large bets "
    "(>$5K) in **Politics**, **Tech**, or **Finance** markets."
)

# ── Sidebar filters ──────────────────────────────────────────
with st.sidebar:
    st.subheader("Filters")

    all_categories = ["Politics", "Tech", "Finance", "Crypto", "Sports",
                      "Culture", "Climate & Science", "World", "Other"]
    selected_categories = st.multiselect(
        "Categories",
        all_categories,
        default=["Politics", "Tech", "Finance"],
    )

    min_size = st.slider(
        "Min Trade Size ($)",
        min_value=1000,
        max_value=100000,
        value=5000,
        step=1000,
        format="$%d",
    )

    limit = st.slider("Max Results", 25, 500, 100)

# ── Fetch data ───────────────────────────────────────────────
if not selected_categories:
    st.warning("Select at least one category.")
    st.stop()

trades = queries.get_first_time_trades(
    categories=selected_categories,
    min_size=min_size,
    limit=limit,
)

# ── Summary metrics ──────────────────────────────────────────
col1, col2, col3 = st.columns(3)
col1.metric("First-Time Traders", len(trades))

total_vol = sum(t.get("usdc_size", 0) or 0 for t in trades)
col2.metric("Total Volume", f"${total_vol:,.0f}")

avg_size = total_vol / len(trades) if trades else 0
col3.metric("Avg First Bet", f"${avg_size:,.0f}")

st.divider()

if not trades:
    st.info(
        "No first-time predictions found matching your filters. "
        "Try lowering the min trade size or adding more categories."
    )
    st.stop()

# ── Trade feed ───────────────────────────────────────────────
st.subheader("Debut Predictions")

for trade in trades:
    side = trade.get("side", "TRADE")
    usdc = trade.get("usdc_size", 0) or 0
    price = trade.get("price", 0) or 0
    category = trade.get("category", "")
    subcategory = trade.get("subcategory", "")

    with st.container(border=True):
        col_side, col_detail, col_amount, col_who = st.columns([0.5, 3, 1.5, 2])

        with col_side:
            emoji = "🟢" if side == "BUY" else "🔴"
            st.markdown(f"### {emoji}")

        with col_detail:
            title = trade.get("market_title") or trade.get("market_name") or "Unknown"
            st.markdown(f"**{title}**")
            cat_badge = f"`{category}`" if category else ""
            sub_badge = f" / `{subcategory}`" if subcategory else ""
            outcome = trade.get("outcome", "")
            price_str = f"@ ${price:.2f}" if price else ""
            st.caption(f"{side} {outcome} {price_str}  {cat_badge}{sub_badge}")

        with col_amount:
            st.metric("Size", f"${usdc:,.0f}")

        with col_who:
            name = trade.get("user_name") or (trade["proxy_wallet"][:12] + "...")
            badge = " ✅" if trade.get("verified_badge") else ""
            st.markdown(f"**{name}{badge}**")
            ts = trade.get("trade_timestamp")
            if ts:
                try:
                    dt = datetime.fromtimestamp(int(ts), tz=timezone.utc)
                    st.caption(f"Debut: {dt.strftime('%Y-%m-%d %H:%M UTC')}")
                except (ValueError, TypeError):
                    pass

# ── Volume chart ─────────────────────────────────────────────
st.divider()
st.subheader("First-Time Prediction Volume Over Time")

df = pd.DataFrame(trades)
if "trade_timestamp" in df.columns and df["trade_timestamp"].notna().any():
    df["time"] = pd.to_datetime(df["trade_timestamp"], unit="s", errors="coerce")
    df = df.dropna(subset=["time"])
    if not df.empty:
        df_grouped = (
            df.set_index("time")
            .resample("1D")["usdc_size"]
            .sum()
            .reset_index()
        )
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=df_grouped["time"],
            y=df_grouped["usdc_size"],
            marker_color="#FF6F00",
            opacity=0.8,
        ))
        fig.update_layout(
            title="Daily First-Time Trader Volume",
            yaxis_title="USD Volume",
            xaxis_title="Date",
            height=350,
        )
        st.plotly_chart(fig, use_container_width=True)

        # Category breakdown
        if "category" in df.columns:
            cat_vol = df.groupby("category")["usdc_size"].sum().sort_values(ascending=True)
            fig2 = go.Figure()
            fig2.add_trace(go.Bar(
                x=cat_vol.values,
                y=cat_vol.index,
                orientation="h",
                marker_color=["#1E88E5", "#43A047", "#E53935", "#8E24AA",
                               "#FB8C00", "#00ACC1", "#6D4C41", "#546E7A", "#78909C"][:len(cat_vol)],
            ))
            fig2.update_layout(
                title="Volume by Category",
                xaxis_title="USD Volume",
                height=300,
            )
            st.plotly_chart(fig2, use_container_width=True)

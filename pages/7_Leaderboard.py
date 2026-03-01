"""Trader Leaderboard -- top Polymarket traders by PNL and volume."""

import streamlit as st
import pandas as pd
from pathlib import Path
import sys

PROJECT_DIR = Path(__file__).resolve().parent.parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from streamlit_app import init_config, init_database, init_queries, get_context

st.set_page_config(page_title="Trader Leaderboard", page_icon="🏆", layout="wide")

config = init_config()
db = init_database(config)
queries = init_queries(db)

st.title("Trader Leaderboard")
st.markdown("Top Polymarket traders ranked by profit/loss and trading volume.")

# Controls
col1, col2, col3 = st.columns(3)
with col1:
    category = st.selectbox(
        "Category",
        ["OVERALL", "POLITICS", "SPORTS", "CRYPTO", "CULTURE",
         "WEATHER", "ECONOMICS", "TECH", "FINANCE"],
    )
with col2:
    time_period = st.selectbox("Time Period", ["ALL", "MONTH", "WEEK", "DAY"])
with col3:
    order_by = st.selectbox("Order By", ["PNL", "VOL"])

# Live fetch button
col_refresh, col_status = st.columns([1, 3])
with col_refresh:
    if st.button("Fetch Live Leaderboard", type="primary"):
        with st.spinner("Fetching from Polymarket Data API..."):
            try:
                context = get_context()
                client = context.get("polymarket_client")
                if client:
                    leaders = client.get_leaderboard(
                        category=category,
                        time_period=time_period,
                        order_by=order_by,
                        limit=50,
                    )
                    from db.models import Trader
                    traders_to_upsert = [
                        Trader(
                            proxy_wallet=entry.get("proxyWallet", ""),
                            user_name=entry.get("userName", ""),
                            profile_image=entry.get("profileImage", ""),
                            x_username=entry.get("xUsername", ""),
                            verified_badge=bool(entry.get("verifiedBadge")),
                            total_pnl=entry.get("pnl"),
                            total_volume=entry.get("vol"),
                        )
                        for entry in leaders
                        if entry.get("proxyWallet")
                    ]
                    queries.upsert_traders_batch(traders_to_upsert)
                    st.success(f"Fetched {len(traders_to_upsert)} traders.")
                    st.rerun()
                else:
                    st.error("Polymarket client not available.")
            except Exception as e:
                st.error(f"Failed: {e}")

st.divider()

# Display from database
sort_col = "total_pnl" if order_by == "PNL" else "total_volume"
traders = queries.get_top_traders(order_by=sort_col, limit=50)

if not traders:
    st.info("No traders in database yet. Click 'Fetch Live Leaderboard' or run the Trader Agent.")
    st.stop()

st.metric("Traders Tracked", len(traders))

for i, trader in enumerate(traders):
    rank = i + 1
    with st.container(border=True):
        col_rank, col_name, col_pnl, col_vol, col_action = st.columns([0.5, 3, 1.5, 1.5, 1])

        with col_rank:
            medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(rank, f"#{rank}")
            st.markdown(f"### {medal}")

        with col_name:
            name = trader.get("user_name") or trader["proxy_wallet"][:12] + "..."
            badge = " ✅" if trader.get("verified_badge") else ""
            st.markdown(f"**{name}{badge}**")
            x_user = trader.get("x_username")
            if x_user:
                st.caption(f"@{x_user}")

        with col_pnl:
            pnl = trader.get("total_pnl", 0) or 0
            st.metric("P&L", f"${pnl:,.2f}")

        with col_vol:
            vol = trader.get("total_volume", 0) or 0
            st.metric("Volume", f"${vol:,.0f}")

        with col_action:
            if st.button("Profile", key=f"profile_{trader['id']}"):
                st.session_state["selected_trader_wallet"] = trader["proxy_wallet"]
                st.switch_page("pages/9_Trader_Profile.py")

# Search
st.divider()
st.subheader("Search Traders")
search = st.text_input("Search by username")
if search:
    results = queries.search_traders(search)
    if results:
        for t in results:
            name = t.get("user_name") or t["proxy_wallet"][:12] + "..."
            pnl = t.get("total_pnl", 0) or 0
            st.markdown(f"**{name}** -- P&L: ${pnl:,.2f}")
    else:
        st.info("No traders found.")

"""Trader Watchlist -- quick access to traders you're tracking."""

import streamlit as st
from pathlib import Path
import sys

PROJECT_DIR = Path(__file__).resolve().parent.parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from streamlit_app import init_config, init_database, init_queries

st.set_page_config(page_title="Watchlist", page_icon="⭐", layout="wide")

config = init_config()
db = init_database(config)
queries = init_queries(db)

st.title("Trader Watchlist")
st.markdown("Traders you're tracking. Add traders from the **Leaderboard** or **Trader Profile** pages.")

# Fetch watchlist
watchlist = queries.get_watchlist()

if not watchlist:
    st.info("Your watchlist is empty. Add traders from the Leaderboard or Trader Profile pages.")
    st.stop()

st.metric("Watching", len(watchlist))
st.divider()

for trader in watchlist:
    with st.container(border=True):
        col_name, col_pnl, col_vol, col_profile, col_remove = st.columns(
            [3, 1.5, 1.5, 1, 1]
        )

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

        with col_profile:
            if st.button("Profile", key=f"wl_profile_{trader['id']}"):
                st.session_state["selected_trader_wallet"] = trader["proxy_wallet"]
                st.switch_page("pages/9_Trader_Profile.py")

        with col_remove:
            if st.button("Remove", key=f"wl_remove_{trader['id']}"):
                queries.remove_from_watchlist(trader["id"])
                st.rerun()

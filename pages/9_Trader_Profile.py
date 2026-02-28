"""Trader Profile -- detailed view of a single trader's positions and activity."""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from pathlib import Path
import sys

PROJECT_DIR = Path(__file__).resolve().parent.parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from streamlit_app import init_config, init_database, init_queries, get_context

st.set_page_config(page_title="Trader Profile", page_icon="👤", layout="wide")

config = init_config()
db = init_database(config)
queries = init_queries(db)

st.title("Trader Profile")

# Wallet input (from session state or manual)
default_wallet = st.session_state.get("selected_trader_wallet", "")
wallet = st.text_input("Trader Wallet Address", value=default_wallet,
                        placeholder="0x...")

if not wallet:
    st.info("Enter a trader's Polymarket wallet address or navigate here from the Leaderboard.")
    st.stop()

# Lookup or fetch trader
trader = queries.get_trader_by_wallet(wallet)

if not trader:
    st.warning(f"Trader {wallet[:16]}... not in local database.")
    if st.button("Fetch from Polymarket"):
        with st.spinner("Fetching trader data..."):
            try:
                context = get_context()
                client = context.get("polymarket_client")
                if client:
                    positions = client.get_positions(user=wallet, limit=100)
                    from db.models import Trader, TraderPosition
                    new_trader = Trader(proxy_wallet=wallet)
                    trader_id = queries.upsert_trader(new_trader)

                    for p in positions:
                        pos = TraderPosition(
                            trader_id=trader_id,
                            proxy_wallet=wallet,
                            condition_id=p.get("conditionId", ""),
                            market_title=p.get("title", ""),
                            outcome=p.get("outcome", ""),
                            size=p.get("size"),
                            avg_price=p.get("avgPrice"),
                            initial_value=p.get("initialValue"),
                            current_value=p.get("currentValue"),
                            cash_pnl=p.get("cashPnl"),
                            percent_pnl=p.get("percentPnl"),
                            realized_pnl=p.get("realizedPnl"),
                            cur_price=p.get("curPrice"),
                            redeemable=bool(p.get("redeemable")),
                            event_slug=p.get("eventSlug", ""),
                        )
                        queries.insert_trader_position(pos)

                    # Also fetch portfolio value (targeted update, not full upsert)
                    try:
                        val_data = client.get_portfolio_value(wallet)
                        portfolio_val = val_data.get("value") if isinstance(val_data, dict) else None
                        if portfolio_val is not None:
                            queries.update_portfolio_value(wallet, float(portfolio_val))
                    except Exception:
                        pass

                    st.success(f"Fetched {len(positions)} positions.")
                    st.rerun()
            except Exception as e:
                st.error(f"Failed: {e}")
    st.stop()

# Display trader header
st.divider()
col1, col2, col3, col4 = st.columns(4)

name = trader.get("user_name") or wallet[:16] + "..."
badge = " ✅" if trader.get("verified_badge") else ""

with col1:
    st.subheader(f"{name}{badge}")
    x_user = trader.get("x_username")
    if x_user:
        st.markdown(f"[@{x_user}](https://x.com/{x_user})")

with col2:
    pnl = trader.get("total_pnl", 0) or 0
    st.metric("Total P&L", f"${pnl:,.2f}")

with col3:
    vol = trader.get("total_volume", 0) or 0
    st.metric("Total Volume", f"${vol:,.0f}")

with col4:
    pv = trader.get("portfolio_value", 0) or 0
    st.metric("Portfolio Value", f"${pv:,.2f}")

# Refresh positions button
if st.button("Refresh Positions"):
    with st.spinner("Fetching latest positions..."):
        try:
            context = get_context()
            client = context.get("polymarket_client")
            if client:
                positions = client.get_positions(user=wallet, limit=200)
                from db.models import TraderPosition
                for p in positions:
                    pos = TraderPosition(
                        trader_id=trader["id"],
                        proxy_wallet=wallet,
                        condition_id=p.get("conditionId", ""),
                        market_title=p.get("title", ""),
                        outcome=p.get("outcome", ""),
                        size=p.get("size"),
                        avg_price=p.get("avgPrice"),
                        initial_value=p.get("initialValue"),
                        current_value=p.get("currentValue"),
                        cash_pnl=p.get("cashPnl"),
                        percent_pnl=p.get("percentPnl"),
                        realized_pnl=p.get("realizedPnl"),
                        cur_price=p.get("curPrice"),
                        redeemable=bool(p.get("redeemable")),
                        event_slug=p.get("eventSlug", ""),
                    )
                    queries.insert_trader_position(pos)
                st.success(f"Refreshed {len(positions)} positions.")
                st.rerun()
        except Exception as e:
            st.error(f"Failed: {e}")

st.divider()

# Positions table
st.subheader("Current Positions")
positions = queries.get_latest_trader_positions(trader["id"])

if positions:
    df = pd.DataFrame(positions)
    display_cols = ["market_title", "outcome", "size", "avg_price",
                    "cur_price", "current_value", "cash_pnl", "percent_pnl"]
    available = [c for c in display_cols if c in df.columns]
    df_display = df[available].copy()

    # Format
    for col in ["avg_price", "cur_price"]:
        if col in df_display.columns:
            df_display[col] = df_display[col].apply(
                lambda x: f"${x:.3f}" if pd.notna(x) else "N/A"
            )
    for col in ["current_value", "cash_pnl"]:
        if col in df_display.columns:
            df_display[col] = df_display[col].apply(
                lambda x: f"${x:,.2f}" if pd.notna(x) else "N/A"
            )
    if "percent_pnl" in df_display.columns:
        df_display["percent_pnl"] = df_display["percent_pnl"].apply(
            lambda x: f"{x:.1%}" if pd.notna(x) else "N/A"
        )

    st.dataframe(df_display, use_container_width=True, hide_index=True)

    # PnL breakdown chart
    if "cash_pnl" in df.columns:
        pnl_df = df[df["cash_pnl"].notna()].sort_values("cash_pnl", ascending=False)
        if not pnl_df.empty:
            fig = go.Figure()
            colors = ["#4CAF50" if v >= 0 else "#F44336" for v in pnl_df["cash_pnl"]]
            fig.add_trace(go.Bar(
                x=pnl_df["market_title"].str[:40],
                y=pnl_df["cash_pnl"],
                marker_color=colors,
            ))
            fig.update_layout(
                title="P&L by Position",
                yaxis_title="Cash P&L ($)",
                height=400,
            )
            st.plotly_chart(fig, use_container_width=True)
else:
    st.info("No positions found. Click 'Refresh Positions' to fetch from Polymarket.")

# Recent trades
st.divider()
st.subheader("Recent Trades")
trades = queries.get_whale_trades_by_trader(trader["id"], limit=50)
if trades:
    for trade in trades[:20]:
        side_emoji = "🟢" if trade.get("side") == "BUY" else "🔴"
        usdc = trade.get("usdc_size", 0) or 0
        st.markdown(
            f"{side_emoji} **{trade.get('side', 'TRADE')}** "
            f"${usdc:,.0f} -- {trade.get('market_title', 'Unknown')} "
            f"({trade.get('outcome', '')})"
        )
else:
    st.info("No trade history in local database for this trader.")

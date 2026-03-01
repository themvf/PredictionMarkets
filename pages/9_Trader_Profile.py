"""Trader Profile -- detailed view of a single trader's positions and activity."""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from pathlib import Path
from datetime import datetime, timezone
import sys

PROJECT_DIR = Path(__file__).resolve().parent.parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from streamlit_app import init_config, init_database, init_queries, get_context
from utils.categories import normalize_category
import math

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

# Action buttons
col_refresh, col_watchlist, _spacer = st.columns([1, 1, 4])
with col_watchlist:
    watched = queries.is_on_watchlist(trader["id"])
    wl_label = "★ On Watchlist" if watched else "☆ Add to Watchlist"
    if st.button(wl_label, key=f"watchlist_btn_{trader['id']}"):
        if watched:
            queries.remove_from_watchlist(trader["id"])
        else:
            queries.add_to_watchlist(trader["id"])
        st.rerun()

with col_refresh:
    refresh_clicked = st.button("Refresh Positions")

if refresh_clicked:
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

# ── Trade History ─────────────────────────────────────────
st.divider()
st.subheader("Trade History")

history_key = f"trade_history_{wallet}"

if st.button("Load Trade History", type="primary"):
    with st.spinner("Fetching last 100 trades from Polymarket..."):
        try:
            context = get_context()
            client = context.get("polymarket_client")
            if not client:
                st.error("Polymarket client not available.")
            else:
                # Fetch trades and current positions from the API
                raw_trades = client.get_trades(user=wallet, limit=100)
                raw_positions = client.get_positions(user=wallet, limit=200)

                # Build position lookup: conditionId → {pnl, redeemable, size}
                pos_map: dict = {}
                for p in raw_positions:
                    cid = p.get("conditionId", "")
                    if cid:
                        try:
                            pnl_val = float(p.get("cashPnl") or 0)
                            if math.isnan(pnl_val):
                                pnl_val = None
                        except (ValueError, TypeError):
                            pnl_val = None
                        pos_map[cid] = {
                            "cash_pnl": pnl_val,
                            "redeemable": bool(p.get("redeemable")),
                            "size": float(p.get("size") or 0),
                        }

                # Build category lookup from our markets DB
                all_markets = queries.get_all_markets(platform="polymarket")
                cat_map = {
                    m["platform_id"]: m.get("category", "")
                    for m in all_markets
                }

                # Build table rows
                history_rows = []
                for t in raw_trades:
                    cid = t.get("conditionId", "")
                    pos = pos_map.get(cid, {})

                    # Determine status
                    if pos.get("redeemable"):
                        status = "Resolved"
                    elif pos.get("size", 0) > 0:
                        status = "Open"
                    else:
                        status = "Closed"

                    # Parse timestamp
                    ts = t.get("timestamp")
                    date_str = ""
                    if ts:
                        try:
                            dt = datetime.fromtimestamp(
                                int(float(ts)), tz=timezone.utc,
                            )
                            date_str = dt.strftime("%Y-%m-%d %H:%M")
                        except (ValueError, TypeError):
                            date_str = str(ts)

                    # Calculate USDC value
                    raw_usdc = t.get("usdcSize") or t.get("cashSize")
                    if raw_usdc is not None:
                        usdc = float(raw_usdc)
                    else:
                        price = float(t.get("price") or 0)
                        size = float(t.get("size") or 0)
                        usdc = price * size if price and size else 0

                    # Category: DB lookup first, fall back to title inference
                    title = t.get("title", "Unknown")
                    category = cat_map.get(cid, "")
                    if not category:
                        category = normalize_category("", title)

                    history_rows.append({
                        "Date": date_str,
                        "Status": status,
                        "Category": category,
                        "Event": title,
                        "Side": t.get("side", ""),
                        "Size ($)": usdc,
                        "Position P&L": pos.get("cash_pnl"),
                    })

                st.session_state[history_key] = history_rows
                st.rerun()
        except Exception as e:
            st.error(f"Failed to load trade history: {e}")

# Display cached trade history
if history_key in st.session_state:
    rows = st.session_state[history_key]
    if rows:
        df = pd.DataFrame(rows)

        # Format currency columns for display
        df["Size ($)"] = df["Size ($)"].apply(
            lambda x: f"${x:,.0f}" if x is not None else "—"
        )
        df["Position P&L"] = df["Position P&L"].apply(
            lambda x: f"${x:,.2f}" if x is not None and not (isinstance(x, float) and math.isnan(x)) else "—"
        )

        st.dataframe(df, use_container_width=True, hide_index=True)
        st.caption(f"Showing {len(rows)} most recent trades. "
                   "P&L is per position (not per individual trade).")
    else:
        st.info("No trades found for this trader on Polymarket.")
else:
    # Fallback: show whale trades from local DB
    trades = queries.get_whale_trades_by_trader(trader["id"], limit=50)
    if trades:
        st.caption(
            "Showing large trades from database. "
            "Click **Load Trade History** for the full last 100 trades."
        )
        for trade in trades[:20]:
            side_emoji = "🟢" if trade.get("side") == "BUY" else "🔴"
            usdc = trade.get("usdc_size", 0) or 0
            st.markdown(
                f"{side_emoji} **{trade.get('side', 'TRADE')}** "
                f"${usdc:,.0f} -- {trade.get('market_title', 'Unknown')} "
                f"({trade.get('outcome', '')})"
            )
    else:
        st.info(
            "No trade history available. "
            "Click **Load Trade History** to fetch from Polymarket."
        )

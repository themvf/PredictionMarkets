"""Alerts — recent alerts table with filters and acknowledge controls."""

import streamlit as st
import pandas as pd
import json
from pathlib import Path
import sys

PROJECT_DIR = Path(__file__).resolve().parent.parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from streamlit_app import init_config, init_database, init_queries

st.set_page_config(page_title="Alerts", page_icon="🚨", layout="wide")

config = init_config()
db = init_database(config)
queries = init_queries(db)

st.title("Alerts")

# Filters
col1, col2, col3 = st.columns(3)
with col1:
    type_filter = st.selectbox(
        "Alert Type",
        ["All", "price_move", "volume_spike", "arbitrage", "closing_soon", "keyword", "whale_trade"],
    )
with col2:
    ack_filter = st.selectbox(
        "Status",
        ["Unacknowledged", "Acknowledged", "All"],
    )
with col3:
    limit = st.number_input("Limit", 10, 500, 100)

# Map filters
alert_type = None if type_filter == "All" else type_filter
acknowledged = None
if ack_filter == "Unacknowledged":
    acknowledged = False
elif ack_filter == "Acknowledged":
    acknowledged = True

alerts = queries.get_alerts(alert_type=alert_type, acknowledged=acknowledged, limit=limit)

if not alerts:
    st.info("No alerts found. Alerts will appear after agents monitor market activity.")
    st.stop()

# Alert counts summary
col1, col2, col3, col4 = st.columns(4)
type_counts = {}
severity_counts = {}
for a in alerts:
    t = a.get("alert_type", "unknown")
    s = a.get("severity", "info")
    type_counts[t] = type_counts.get(t, 0) + 1
    severity_counts[s] = severity_counts.get(s, 0) + 1

col1.metric("Total Alerts", len(alerts))
col2.metric("Critical", severity_counts.get("critical", 0))
col3.metric("Warning", severity_counts.get("warning", 0))
col4.metric("Info", severity_counts.get("info", 0))

st.divider()

# Alert cards
for alert in alerts:
    severity = alert.get("severity", "info")
    icon = {
        "critical": "🔴",
        "warning": "🟡",
        "info": "🔵",
    }.get(severity, "⚪")

    type_icon = {
        "price_move": "📊",
        "volume_spike": "📈",
        "arbitrage": "🔄",
        "closing_soon": "⏰",
        "keyword": "🔍",
        "whale_trade": "🐋",
    }.get(alert.get("alert_type", ""), "📋")

    with st.container(border=True):
        col_main, col_action = st.columns([5, 1])
        with col_main:
            st.markdown(f"{icon} {type_icon} **{alert['title']}**")
            st.caption(f"{alert.get('alert_type', '').replace('_', ' ').title()} | {alert.get('triggered_at', '')}")
            st.markdown(alert.get("message", ""))

            # Expandable data
            data_str = alert.get("data")
            if data_str:
                with st.expander("Details"):
                    try:
                        data = json.loads(data_str)
                        st.json(data)
                    except (json.JSONDecodeError, TypeError):
                        st.text(str(data_str))

        with col_action:
            if not alert.get("acknowledged"):
                if st.button("Ack", key=f"ack_{alert['id']}"):
                    queries.acknowledge_alert(alert["id"])
                    st.rerun()
            else:
                st.caption("Acknowledged")

# Alert rule configuration
st.divider()
st.subheader("Alert Rules Configuration")

with st.form("alert_rules"):
    col1, col2 = st.columns(2)
    with col1:
        price_threshold = st.number_input(
            "Price move threshold ($)",
            0.01, 1.0, config.alerts.price_move_threshold, 0.01,
        )
        volume_spike = st.number_input(
            "Volume spike threshold (%)",
            0.10, 5.0, config.alerts.volume_spike_pct, 0.05,
        )
    with col2:
        arb_threshold = st.number_input(
            "Arbitrage gap threshold ($)",
            0.01, 1.0, config.alerts.arbitrage_gap_threshold, 0.01,
        )
        close_hours = st.number_input(
            "Close warning (hours)",
            1, 168, config.alerts.close_hours_threshold,
        )

    keywords = st.text_input(
        "Keyword watchlist (comma-separated)",
        ", ".join(config.alerts.keywords),
    )

    submitted = st.form_submit_button("Save Rules")
    if submitted:
        config.alerts.price_move_threshold = price_threshold
        config.alerts.volume_spike_pct = volume_spike
        config.alerts.arbitrage_gap_threshold = arb_threshold
        config.alerts.close_hours_threshold = close_hours
        config.alerts.keywords = [k.strip() for k in keywords.split(",") if k.strip()]
        st.success("Alert rules updated for this session.")

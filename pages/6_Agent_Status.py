"""Agent Status — monitoring dashboard for all agents."""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from pathlib import Path
import sys

PROJECT_DIR = Path(__file__).resolve().parent.parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from streamlit_app import init_config, init_database, init_queries, get_context, init_registry, init_slack_notifier

st.set_page_config(page_title="Agent Status", page_icon="🤖", layout="wide")

config = init_config()
db = init_database(config)
queries = init_queries(db)

st.title("Agent Status")
st.markdown("Monitor and control the 7 AI agents powering the platform.")

AGENT_INFO = {
    "discovery": {
        "description": "Scans Kalshi & Polymarket for active markets, normalizes data, matches cross-platform equivalents",
        "schedule": "Every 30 min",
        "uses_llm": True,
    },
    "collection": {
        "description": "Fetches current prices, volumes, and orderbook snapshots for all tracked markets",
        "schedule": "Every 5 min",
        "uses_llm": False,
    },
    "analyzer": {
        "description": "Compares matched pairs, calculates price gaps, GPT-4o qualitative analysis",
        "schedule": "Every 15 min",
        "uses_llm": True,
    },
    "alert": {
        "description": "Rule-based monitoring: price moves, volume spikes, arbitrage gaps, closing soon, keywords",
        "schedule": "Every 5 min",
        "uses_llm": False,
    },
    "insight": {
        "description": "Generates natural language market intelligence briefings using GPT-4o",
        "schedule": "Every 60 min",
        "uses_llm": True,
    },
    "trader": {
        "description": "Fetches Polymarket leaderboard data, upserts trader profiles across categories and time periods",
        "schedule": "Every 30 min",
        "uses_llm": False,
    },
    "whale": {
        "description": "Monitors large Polymarket trades, stores whale activity, generates whale alerts",
        "schedule": "Every 5 min",
        "uses_llm": False,
    },
}

# Agent cards
for agent_name, info in AGENT_INFO.items():
    latest = queries.get_latest_agent_run(agent_name)

    with st.container(border=True):
        col1, col2, col3, col4 = st.columns([3, 1, 1, 1])

        with col1:
            llm_badge = " 🧠" if info["uses_llm"] else ""
            st.markdown(f"### {agent_name.title()} Agent{llm_badge}")
            st.caption(info["description"])

        with col2:
            if latest:
                status = latest.get("status", "unknown")
                status_color = {
                    "success": "green",
                    "error": "red",
                    "running": "orange",
                }.get(status, "gray")
                st.markdown(f":{status_color}[**{status.upper()}**]")
            else:
                st.markdown(":gray[**NEVER RUN**]")

        with col3:
            if latest:
                duration = latest.get("duration_seconds", 0)
                st.metric("Duration", f"{duration:.1f}s")
                items = latest.get("items_processed", 0)
                st.caption(f"{items} items")
            else:
                st.metric("Duration", "N/A")

        with col4:
            if latest:
                st.caption(f"Last: {latest.get('started_at', 'N/A')[:16]}")
            st.caption(f"Schedule: {info['schedule']}")

            if st.button(f"Run Now", key=f"run_{agent_name}"):
                with st.spinner(f"Running {agent_name} agent..."):
                    try:
                        context = get_context()
                        registry = init_registry()
                        pre_run_alerts = queries.get_alerts(limit=50)
                        pre_run_ids = {a["id"] for a in pre_run_alerts}
                        result = registry.run_one(agent_name, context)
                        if result.error:
                            st.error(f"Error: {result.error}")
                        else:
                            st.success(result.summary)
                        # Slack notification
                        notifier = init_slack_notifier(config)
                        if notifier.enabled:
                            new_alerts = [
                                a for a in queries.get_alerts(limit=50)
                                if a["id"] not in pre_run_ids
                            ]
                            notifier.notify_agent_run(result, new_alerts)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed: {e}")

        # Show last error if any
        if latest and latest.get("error"):
            st.error(f"Last error: {latest['error']}")

        # Summary
        if latest and latest.get("summary"):
            st.caption(f"Summary: {latest['summary']}")

st.divider()

# Run history chart
st.subheader("Agent Run History")

agent_filter = st.selectbox("Filter Agent", ["All"] + list(AGENT_INFO.keys()))
agent_name_filter = None if agent_filter == "All" else agent_filter
logs = queries.get_agent_logs(agent_name=agent_name_filter, limit=100)

if logs:
    df = pd.DataFrame(logs)
    df["started_at"] = pd.to_datetime(df["started_at"])

    # Duration over time chart
    fig = go.Figure()
    for name in df["agent_name"].unique():
        agent_df = df[df["agent_name"] == name]
        colors = [
            "#4CAF50" if s == "success" else "#F44336"
            for s in agent_df["status"]
        ]
        fig.add_trace(go.Bar(
            x=agent_df["started_at"],
            y=agent_df["duration_seconds"],
            name=name.title(),
            marker_color=colors,
            text=agent_df["status"],
        ))

    fig.update_layout(
        title="Agent Run Duration Over Time",
        xaxis_title="Time",
        yaxis_title="Duration (seconds)",
        barmode="group",
        height=400,
    )
    st.plotly_chart(fig, use_container_width=True)

    # Run history table
    st.subheader("Run Log")
    display_df = df[["agent_name", "status", "started_at", "duration_seconds",
                      "items_processed", "summary", "error"]].copy()
    display_df.columns = ["Agent", "Status", "Started", "Duration (s)",
                          "Items", "Summary", "Error"]
    st.dataframe(display_df, use_container_width=True, hide_index=True)
else:
    st.info("No agent run history yet. Use the 'Run Now' buttons above to trigger agents.")

# Run all agents
st.divider()
if st.button("Run All Agents", type="primary"):
    with st.spinner("Running all agents sequentially..."):
        try:
            context = get_context()
            registry = init_registry()
            notifier = init_slack_notifier(config)
            pre_run_alerts = queries.get_alerts(limit=200)
            pre_run_ids = {a["id"] for a in pre_run_alerts}
            results = registry.run_all(context)
            for r in results:
                if r.error:
                    st.error(f"{r.agent_name}: {r.error}")
                else:
                    st.success(f"{r.agent_name}: {r.summary}")
                # Slack notification per agent
                if notifier.enabled:
                    new_alerts = [
                        a for a in queries.get_alerts(limit=200)
                        if a["id"] not in pre_run_ids
                    ]
                    notifier.notify_agent_run(r, new_alerts)
                    pre_run_ids.update(a["id"] for a in new_alerts)
            st.rerun()
        except Exception as e:
            st.error(f"Failed: {e}")

"""AI Insights — GPT-4o market intelligence briefings."""

import streamlit as st
from pathlib import Path
import sys

PROJECT_DIR = Path(__file__).resolve().parent.parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from streamlit_app import init_config, init_database, init_queries, get_context

st.set_page_config(page_title="AI Insights", page_icon="🧠", layout="wide")

config = init_config()
db = init_database(config)
queries = init_queries(db)

st.title("AI Insights")
st.markdown("GPT-4o powered market intelligence reports and analysis.")

# On-demand generation
col1, col2 = st.columns(2)
with col1:
    if st.button("Generate Market Briefing", type="primary"):
        with st.spinner("Generating market intelligence briefing with GPT-4o..."):
            try:
                context = get_context()
                from agents.insight_agent import InsightAgent
                agent = InsightAgent()
                result = agent.run(context)
                if result.error:
                    st.error(f"Error: {result.error}")
                else:
                    st.success(result.summary)
                    st.rerun()
            except Exception as e:
                st.error(f"Failed to generate briefing: {e}")

with col2:
    if st.button("Generate Alert Summary"):
        with st.spinner("Summarizing alerts with GPT-4o..."):
            try:
                context = get_context()
                from agents.insight_agent import InsightAgent
                agent = InsightAgent()
                summary = agent.generate_alert_summary(context)
                st.markdown(summary)
            except Exception as e:
                st.error(f"Failed to generate summary: {e}")

st.divider()

# Report type filter
report_type = st.selectbox(
    "Report Type",
    ["All", "briefing", "alert_summary", "deep_dive"],
)

report_filter = None if report_type == "All" else report_type
insights = queries.get_insights(report_type=report_filter, limit=20)

if not insights:
    st.info("No AI insights generated yet. Click 'Generate Market Briefing' to create the first report.")
    st.stop()

# Display insights
for insight in insights:
    with st.container(border=True):
        col_header, col_meta = st.columns([3, 1])
        with col_header:
            st.subheader(insight.get("title", "Untitled Report"))
        with col_meta:
            st.caption(f"Type: {insight.get('report_type', 'N/A')}")
            st.caption(f"Created: {insight.get('created_at', 'N/A')}")
            st.caption(f"Markets: {insight.get('markets_covered', 0)}")
            st.caption(f"Model: {insight.get('model_used', 'N/A')}")

        # Render markdown content
        content = insight.get("content", "")
        st.markdown(content)

    st.divider()

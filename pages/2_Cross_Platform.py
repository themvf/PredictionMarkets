"""Cross Platform — matched pairs with side-by-side price comparison."""

import streamlit as st
import pandas as pd
import json
from pathlib import Path
import sys

PROJECT_DIR = Path(__file__).resolve().parent.parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from streamlit_app import init_config, init_database, init_queries

st.set_page_config(page_title="Cross Platform", page_icon="🔄", layout="wide")

config = init_config()
db = init_database(config)
queries = init_queries(db)

st.title("Cross-Platform Comparison")
st.markdown("Matched markets across Kalshi and Polymarket with price gap analysis.")

pairs = queries.get_all_pairs()

if not pairs:
    st.info("No cross-platform pairs found. Run the Discovery Agent with OpenAI to match markets.")
    st.stop()

st.metric("Matched Pairs", len(pairs))

# Filter by gap threshold
min_gap = st.slider("Minimum price gap ($)", 0.0, 0.50, 0.0, 0.01)
filtered = [p for p in pairs if (p.get("price_gap") or 0) >= min_gap]

st.caption(f"Showing {len(filtered)} pairs with gap >= ${min_gap:.2f}")

for pair in filtered:
    kalshi_yes = pair.get("kalshi_yes")
    poly_yes = pair.get("poly_yes")
    gap = pair.get("price_gap", 0) or 0

    # Color-code by gap size
    if gap >= 0.10:
        border_color = "red"
    elif gap >= 0.05:
        border_color = "orange"
    else:
        border_color = "green"

    with st.container(border=True):
        col1, col2, col3 = st.columns([2, 2, 1])

        with col1:
            st.markdown(f"**🔷 Kalshi**")
            st.markdown(f"**{pair.get('kalshi_title', 'Unknown')}**")
            if kalshi_yes is not None:
                st.metric("Yes Price", f"${kalshi_yes:.2f}")
            else:
                st.metric("Yes Price", "N/A")

        with col2:
            st.markdown(f"**🟣 Polymarket**")
            st.markdown(f"**{pair.get('poly_title', 'Unknown')}**")
            if poly_yes is not None:
                st.metric("Yes Price", f"${poly_yes:.2f}")
            else:
                st.metric("Yes Price", "N/A")

        with col3:
            st.metric("Gap", f"${gap:.2f}")
            confidence = pair.get("match_confidence", 0)
            st.caption(f"Confidence: {confidence:.0%}")

        # Expandable LLM analysis
        analyses = queries.get_latest_analyses(limit=100)
        pair_analyses = [a for a in analyses if a.get("pair_id") == pair["id"]]
        if pair_analyses:
            latest = pair_analyses[0]
            llm_data = latest.get("llm_analysis")
            if llm_data:
                with st.expander("GPT-4o Analysis"):
                    try:
                        analysis = json.loads(llm_data)
                        st.markdown(analysis.get("analysis", "No analysis available."))
                        col_a, col_b = st.columns(2)
                        col_a.metric("Risk Score", f"{analysis.get('risk_score', 'N/A')}/10")
                        col_b.caption(f"Likely cause: {analysis.get('likely_cause', 'unknown')}")
                        factors = analysis.get("key_factors", [])
                        if factors:
                            st.markdown("**Key Factors:** " + ", ".join(factors))
                    except (json.JSONDecodeError, TypeError):
                        st.markdown(str(llm_data))

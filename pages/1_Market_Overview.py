"""Market Overview — filterable table of all markets from both platforms."""

import streamlit as st
import pandas as pd
from pathlib import Path
import sys

PROJECT_DIR = Path(__file__).resolve().parent.parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from streamlit_app import init_config, init_database, init_queries

st.set_page_config(page_title="Market Overview", page_icon="📊", layout="wide")

config = init_config()
db = init_database(config)
queries = init_queries(db)

st.title("Market Overview")

# Filters
col1, col2, col3, col_cat = st.columns(4)
with col1:
    platform_filter = st.selectbox(
        "Platform",
        ["All", "kalshi", "polymarket"],
    )
with col2:
    status_filter = st.selectbox("Status", ["active", "closed", "settled"])
with col3:
    search_query = st.text_input("Search", placeholder="Filter by title...")
with col_cat:
    categories = queries.get_distinct_categories(status=status_filter)
    category_filter = st.selectbox("Category", ["All"] + categories)

# Additional filters
col4, col5 = st.columns(2)
with col4:
    vol_min = st.number_input("Min Volume ($)", 0, 10000000, 0, 1000)
with col5:
    liq_filter = st.selectbox("Liquidity Tier", ["All", "deep", "moderate", "thin", "micro"])

# Fetch data
if search_query:
    markets = queries.search_markets(search_query)
else:
    platform = None if platform_filter == "All" else platform_filter
    cat = None if category_filter == "All" else category_filter
    markets = queries.get_all_markets(platform=platform, status=status_filter, category=cat)

# Apply volume filter
if vol_min > 0:
    markets = [m for m in markets if (m.get("volume") or 0) >= vol_min]

# Apply liquidity tier filter
if liq_filter != "All":
    from db.market_math import liquidity_score
    markets = [m for m in markets
               if liquidity_score(m.get("volume"), m.get("liquidity")) == liq_filter]

if not markets:
    st.info("No markets found. Run the Discovery Agent to populate markets.")
    st.stop()

# Build DataFrame
df = pd.DataFrame(markets)

# Display columns
display_cols = ["platform", "title", "yes_price", "no_price", "volume", "liquidity", "category", "close_time"]
available_cols = [c for c in display_cols if c in df.columns]
df_display = df[available_cols].copy()

# Format prices
for col in ["yes_price", "no_price"]:
    if col in df_display.columns:
        df_display[col] = df_display[col].apply(
            lambda x: f"${x:.2f}" if pd.notna(x) else "N/A"
        )

# Format volume
if "volume" in df_display.columns:
    df_display["volume"] = df_display["volume"].apply(
        lambda x: f"{x:,.0f}" if pd.notna(x) else "N/A"
    )

# Sort options
sort_by = st.selectbox(
    "Sort by",
    ["volume", "yes_price", "title"],
    index=0,
)

st.metric("Markets Found", len(df))

# Add platform emoji
df_display["platform"] = df_display["platform"].map({
    "kalshi": "🔷 Kalshi",
    "polymarket": "🟣 Polymarket",
}).fillna(df_display["platform"])

st.dataframe(
    df_display,
    use_container_width=True,
    hide_index=True,
    column_config={
        "title": st.column_config.TextColumn("Market", width="large"),
        "platform": st.column_config.TextColumn("Platform", width="small"),
        "yes_price": st.column_config.TextColumn("Yes Price"),
        "no_price": st.column_config.TextColumn("No Price"),
        "volume": st.column_config.TextColumn("Volume"),
        "category": st.column_config.TextColumn("Category"),
        "close_time": st.column_config.TextColumn("Closes"),
    },
)

# Category breakdown
st.divider()
st.subheader("Category Breakdown")
if "category" in df.columns:
    cat_counts = df["category"].value_counts().head(15)
    if not cat_counts.empty:
        st.bar_chart(cat_counts)

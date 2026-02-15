"""
Brackets Arbitrage Bot — Overview Page
Paper trading simulation for multi-bracket spread strategies on Polymarket.
"""

import time
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime

from core.state_manager import StrategyState
from core.capital_manager import CapitalManager
from core.api_client import check_api_health
from core.strategy_content import OVERVIEW_CONTENT

st.set_page_config(
    page_title="Brackets Arbitrage Bot",
    page_icon="📊",
    layout="wide",
)

STRATEGIES = [
    {"name": "trump_posts", "display": "Trump Posts", "tier": 1},
    {"name": "mrbeast_views", "display": "MrBeast Views", "tier": 1},
    {"name": "kaito_ai", "display": "Kaito AI", "tier": 1},
    {"name": "album_sales", "display": "Album Sales", "tier": 1},
    {"name": "temperature", "display": "Daily Temperature", "tier": 2},
    {"name": "tate_posts", "display": "Tate Posts", "tier": 2},
    {"name": "box_office", "display": "Box Office", "tier": 2},
    {"name": "gpu_prices", "display": "GPU Prices", "tier": 2},
    {"name": "musk_tweets", "display": "Musk Tweets", "tier": 2},
]

# --- Title ---
st.title("Brackets Arbitrage Bot")
st.caption("Paper trading simulation — Multi-bracket spread strategies on Polymarket")

# --- Strategy Overview (expandable) ---
with st.expander("Strategy Analysis & Methodology", expanded=False):
    st.markdown(OVERVIEW_CONTENT)

st.divider()

# --- Summary Table ---
st.subheader("Strategy Overview")

rows = []
total_equity = 0.0
for s in STRATEGIES:
    state = StrategyState(s["name"])
    cap = CapitalManager(state)
    metrics = cap.get_metrics()
    total_equity += metrics["total_equity"]

    last_scan = ""
    if state.last_updated > 0:
        last_scan = datetime.fromtimestamp(state.last_updated).strftime("%m/%d %H:%M")

    rows.append({
        "Strategy": s["display"],
        "Tier": s["tier"],
        "Equity": f"${metrics['total_equity']:,.2f}",
        "Return": f"{metrics['return_pct']:+.1f}%",
        "Open Positions": metrics["open_trades"],
        "Win Rate": f"{metrics['win_rate']:.0f}%" if metrics["total_trades"] > 0 else "-",
        "Total Trades": metrics["total_trades"],
        "Last Scan": last_scan or "Never",
    })

df = pd.DataFrame(rows)
st.dataframe(df, use_container_width=True, hide_index=True)

# Total equity
st.metric("Combined Portfolio Equity", f"${total_equity:,.2f}",
          delta=f"{((total_equity - 9000) / 9000 * 100):+.1f}%")

st.divider()

# --- Overlaid Equity Curves ---
st.subheader("Equity Curves (All Strategies)")

has_data = False
fig, ax = plt.subplots(figsize=(12, 5))
fig.patch.set_facecolor("#0e1117")
ax.set_facecolor("#0e1117")

colors = ["#00d4aa", "#ff6b6b", "#ffd93d", "#6bcbff", "#c084fc", "#fb923c", "#4ade80", "#f472b6", "#a3e635"]

for i, s in enumerate(STRATEGIES):
    state = StrategyState(s["name"])
    if state.performance_log and len(state.performance_log) >= 2:
        has_data = True
        dates = [datetime.fromtimestamp(p["timestamp"]) for p in state.performance_log]
        equities = [p["total_equity"] for p in state.performance_log]
        ax.plot(dates, equities, color=colors[i], linewidth=1.5, label=s["display"], alpha=0.9)

if has_data:
    ax.axhline(y=1000, color="#666666", linestyle="--", linewidth=1, alpha=0.4, label="Starting ($1,000)")
    ax.set_ylabel("Total Equity ($)", color="#fafafa")
    ax.tick_params(colors="#fafafa")
    ax.legend(facecolor="#1a1f2e", edgecolor="#333", labelcolor="#fafafa", fontsize=9)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["bottom"].set_color("#333")
    ax.spines["left"].set_color("#333")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d %H:%M"))
    fig.autofmt_xdate()
    st.pyplot(fig)
else:
    st.caption("No performance data yet. Scan markets on individual strategy pages to begin.")

plt.close(fig)

st.divider()

# --- API Health Check ---
st.subheader("API Health")

if st.button("Check API Connectivity"):
    with st.spinner("Checking APIs..."):
        health = check_api_health()

    col1, col2, col3 = st.columns(3)

    for col, (name, data) in zip([col1, col2, col3], health.items()):
        with col:
            status = data.get("status", "error")
            if status == "ok":
                st.success(f"{name.upper()}: Connected")
            else:
                error = data.get("error", f"HTTP {data.get('code', '?')}")
                st.error(f"{name.upper()}: {error}")
else:
    st.caption("Click to verify Gamma API, CLOB API, and XTracker connectivity.")

# --- Auto-refresh every 5 minutes ---
import streamlit.components.v1 as components
components.html(
    """<script>
        setTimeout(function() {
            window.parent.postMessage({type: 'streamlit:rerun'}, '*');
        }, 300000);
    </script>""",
    height=0,
)

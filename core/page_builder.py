"""
Shared page layout builder for all 7 strategy pages.
Provides consistent UI across pages with strategy-specific customizations.
"""

import time
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timedelta

from core.state_manager import StrategyState, PaperTrade
from core.capital_manager import CapitalManager
from core.market_discovery import (
    discover_events, analyze_event_brackets, fetch_bracket_orderbooks,
    get_strategy_xtracker, STRATEGY_CONFIG,
)
from core.simulation_engine import simulate_buy
from core.strategy_content import STRATEGY_CONTENT


def render_strategy_page(
    strategy_name: str,
    page_title: str,
    tier: int,
    extra_widgets: callable = None,
):
    """
    Render a complete strategy page with consistent layout.

    Args:
        strategy_name: Key in STRATEGY_CONFIG (e.g., "trump_posts")
        page_title: Display title (e.g., "Trump Posts")
        tier: 1 or 2
        extra_widgets: Optional callable(state, capital) for strategy-specific UI
    """
    st.set_page_config(page_title=f"{page_title} - Tier {tier}", layout="wide")

    # Initialize state
    state = StrategyState(strategy_name)
    capital = CapitalManager(state)

    # --- Sidebar ---
    with st.sidebar:
        tier_color = ":green" if tier == 1 else ":orange"
        st.markdown(f"### {page_title}")
        st.markdown(f"**Tier {tier}** {tier_color}[{'HIGH PRIORITY' if tier == 1 else 'MODERATE'}]")
        st.divider()

        if st.button("Scan Markets", key="scan_btn", use_container_width=True):
            st.session_state[f"{strategy_name}_scan"] = True

        auto_refresh = st.toggle("Auto-refresh (60s)", key=f"{strategy_name}_auto")
        if auto_refresh:
            time.sleep(0.1)  # Small delay to prevent immediate rerun
            st.rerun()  # Will rerun after page renders

        st.divider()
        if st.button("Reset Simulation", key="reset_btn", type="secondary", use_container_width=True):
            state.reset()
            st.success("Simulation reset!")
            st.rerun()

        # Quick metrics in sidebar
        metrics = capital.get_metrics()
        st.metric("Total Equity", f"${metrics['total_equity']:,.2f}",
                   delta=f"{metrics['return_pct']:+.1f}%")
        st.metric("Open Positions", metrics["open_trades"])
        if metrics["total_trades"] > 0:
            st.metric("Win Rate", f"{metrics['win_rate']:.0f}%")

    # --- Main Content ---
    st.title(f"{page_title} - Tier {tier}")

    # Strategy Analysis (expandable)
    content = STRATEGY_CONTENT.get(strategy_name, "No analysis available.")
    with st.expander("Strategy Analysis & Methodology", expanded=False):
        st.markdown(content)

    # Strategy-specific extra widgets (XTracker, countdown, etc.)
    if extra_widgets:
        extra_widgets(state, capital)

    # --- Portfolio Metrics Row ---
    st.subheader("Portfolio")
    metrics = capital.get_metrics()
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("Cash Balance", f"${metrics['cash']:,.2f}")
    with col2:
        st.metric("Invested", f"${metrics['invested']:,.2f}")
    with col3:
        color = "normal" if metrics["unrealized_pnl"] == 0 else ("off" if metrics["unrealized_pnl"] < 0 else "normal")
        st.metric("Unrealized P&L", f"${metrics['unrealized_pnl']:,.2f}")
    with col4:
        st.metric("Realized P&L", f"${metrics['realized_pnl']:,.2f}")
    with col5:
        st.metric("Total Equity", f"${metrics['total_equity']:,.2f}",
                   delta=f"{metrics['return_pct']:+.1f}%")

    st.divider()

    # --- Active Markets Section ---
    st.subheader("Active Markets")

    if st.session_state.get(f"{strategy_name}_scan"):
        with st.spinner("Scanning for bracket markets..."):
            _scan_and_display_markets(strategy_name, state, capital)
        st.session_state[f"{strategy_name}_scan"] = False
    else:
        # Show cached events
        if state.events_tracked:
            st.info(f"Tracking {len(state.events_tracked)} events. Click **Scan Markets** to refresh.")
            for eid, meta in state.events_tracked.items():
                with st.container(border=True):
                    cols = st.columns([3, 1, 1, 1, 1])
                    cols[0].write(f"**{meta.get('title', 'Unknown Event')}**")
                    cols[1].write(f"Brackets: {meta.get('bracket_count', '?')}")
                    cols[2].write(f"Cost: ${meta.get('total_cost', 0):.2f}")
                    cols[3].write(f"Edge: {meta.get('edge_pct', 0):.0f}%")
                    if meta.get('edge', 0) > 0.6:
                        cols[4].success("QUALIFYING")
                    elif meta.get('edge', 0) > 0.2:
                        cols[4].warning("MARGINAL")
                    else:
                        cols[4].error("NO EDGE")
        else:
            st.info("No markets scanned yet. Click **Scan Markets** in the sidebar.")

    st.divider()

    # --- Open Positions ---
    st.subheader("Open Positions")
    open_trades = state.get_open_trades()
    if open_trades:
        rows = []
        for t in open_trades:
            hold_hours = (time.time() - t.entry_time) / 3600
            rows.append({
                "Bracket": t.bracket_title[:40],
                "Entry Price": f"${t.entry_price:.4f}",
                "Shares": f"{t.shares:.1f}",
                "Cost": f"${t.entry_cost:.2f}",
                "Hold Time": f"{hold_hours:.1f}h",
                "Status": t.status,
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.caption("No open positions.")

    # --- Trade History ---
    st.subheader("Trade History")
    closed_trades = state.get_closed_trades()
    if closed_trades:
        rows = []
        for t in closed_trades:
            duration_h = ((t.exit_time or t.entry_time) - t.entry_time) / 3600
            rows.append({
                "Bracket": t.bracket_title[:40],
                "Entry": f"${t.entry_price:.4f}",
                "Exit": f"${t.exit_price:.4f}" if t.exit_price else "-",
                "P&L": f"${t.pnl:+.2f}" if t.pnl else "-",
                "Result": t.status,
                "Duration": f"{duration_h:.1f}h",
                "Slippage": f"{t.slippage:.2%}",
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.caption("No closed trades yet.")

    # --- Equity Curve ---
    st.subheader("Equity Curve")
    if state.performance_log:
        _render_equity_curve(state.performance_log)
    else:
        st.caption("No performance data yet. Equity curve will appear after scanning.")

    # Record performance snapshot
    state.record_performance(unrealized_pnl=metrics["unrealized_pnl"])


def _scan_and_display_markets(strategy_name: str, state: StrategyState, capital: CapitalManager):
    """Scan for markets, analyze brackets, and display with trade buttons."""
    events = discover_events(strategy_name)

    if not events:
        st.warning("No active events found for this strategy. Markets may not be open yet.")
        return

    st.success(f"Found {len(events)} events")

    for event in events:
        analysis = analyze_event_brackets(event)
        event_title = event.get("title", "Unknown")
        event_id = str(event.get("id", ""))

        # Track event
        state.track_event(event_id, {
            "title": event_title,
            "bracket_count": analysis["bracket_count"],
            "total_cost": analysis["total_cost"],
            "edge": analysis["edge"],
            "edge_pct": analysis["edge_pct"],
            "scanned_at": time.time(),
        })

        with st.container(border=True):
            st.markdown(f"#### {event_title}")
            cols = st.columns([1, 1, 1, 1])
            cols[0].metric("Brackets", analysis["bracket_count"])
            cols[1].metric("Total Cost", f"${analysis['total_cost']:.2f}")
            cols[2].metric("Edge", f"{analysis['edge_pct']:.0f}%")
            cols[3].metric("Qualifying (1-5c)", len(analysis["qualifying"]))

            if analysis["edge"] > 0.6 and analysis["qualifying"]:
                # Show qualifying brackets with trade buttons
                st.markdown("**Qualifying Brackets:**")
                enriched = fetch_bracket_orderbooks(analysis["qualifying"][:10])

                for bracket in enriched:
                    bcol1, bcol2, bcol3, bcol4 = st.columns([3, 1, 1, 1])
                    bcol1.write(bracket["title"][:50])
                    bcol2.write(f"Ask: ${bracket.get('best_ask', bracket['yes_price']):.3f}")
                    bcol3.write(f"Vol: ${bracket.get('volume', 0):,.0f}")

                    btn_key = f"trade_{strategy_name}_{bracket.get('market_id', '')}_{bracket.get('token_id', '')[:8]}"
                    if bcol4.button("Paper Trade", key=btn_key):
                        _execute_paper_trade(state, capital, event, bracket)

            elif analysis["edge"] > 0.2:
                st.warning(f"Marginal edge ({analysis['edge_pct']:.0f}%). Monitor but don't trade.")
            else:
                st.error(f"No edge ({analysis['edge_pct']:.0f}%). Bracket costs too high.")


def _execute_paper_trade(state: StrategyState, capital: CapitalManager, event: dict, bracket: dict):
    """Execute a simulated paper trade on a qualifying bracket."""
    bet_size = capital.get_bet_size()

    if not capital.can_afford(bet_size):
        st.error(f"Insufficient cash. Need ${bet_size:.2f}, have ${capital.cash:.2f}")
        return

    orderbook = bracket.get("orderbook")
    if not orderbook:
        st.error("No orderbook data available for this bracket.")
        return

    # Simulate buy
    result = simulate_buy(orderbook, bet_size)
    if not result:
        st.error("Could not simulate fill. Orderbook may be empty.")
        return

    # Create trade record
    trade_id = f"SIM-{bracket.get('condition_id', 'X')[:8]}-{int(time.time())}"
    trade = PaperTrade(
        trade_id=trade_id,
        strategy=state.strategy_name,
        event_title=event.get("title", ""),
        bracket_title=bracket.get("title", ""),
        side="YES",
        shares=result["shares"],
        entry_price=result["avg_price"],
        entry_cost=result["total_cost"],
        entry_time=time.time(),
        token_id=bracket.get("token_id", ""),
        condition_id=bracket.get("condition_id", ""),
        slippage=result["slippage_vs_best"],
        orderbook_depth_at_entry=orderbook.get("ask_depth_usd", 0),
        market_id=str(bracket.get("market_id", "")),
        event_id=str(event.get("id", "")),
    )
    state.add_trade(trade)
    st.success(
        f"Paper trade placed: {result['shares']:.1f} shares @ ${result['avg_price']:.4f} "
        f"= ${result['total_cost']:.2f} (slippage: {result['slippage_vs_best']:.2%})"
    )


def _render_equity_curve(performance_log: list[dict]):
    """Render equity curve chart from performance snapshots."""
    if len(performance_log) < 2:
        st.caption("Need at least 2 data points for equity curve.")
        return

    dates = [datetime.fromtimestamp(p["timestamp"]) for p in performance_log]
    equities = [p["total_equity"] for p in performance_log]

    fig, ax = plt.subplots(figsize=(10, 4))
    fig.patch.set_facecolor("#0e1117")
    ax.set_facecolor("#0e1117")

    ax.plot(dates, equities, color="#00d4aa", linewidth=2)
    ax.fill_between(dates, equities, alpha=0.15, color="#00d4aa")

    # Starting capital reference line
    ax.axhline(y=1000, color="#666666", linestyle="--", linewidth=1, alpha=0.5)

    ax.set_ylabel("Total Equity ($)", color="#fafafa")
    ax.tick_params(colors="#fafafa")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["bottom"].set_color("#333")
    ax.spines["left"].set_color("#333")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d %H:%M"))
    fig.autofmt_xdate()

    st.pyplot(fig)
    plt.close(fig)


# --- Strategy-Specific Extra Widgets ---

def social_media_widgets(username: str, display_name: str):
    """Factory for social media strategy extra widgets (XTracker counter)."""
    def _widgets(state, capital):
        st.subheader(f"Live Post Counter — {display_name}")
        data = get_strategy_xtracker(state.strategy_name)
        if data:
            col1, col2 = st.columns(2)
            with col1:
                count = data.get("count", data.get("postCount", "N/A"))
                st.metric("Current Count", count)
            with col2:
                period = data.get("period", data.get("timeframe", ""))
                st.caption(f"Tracking: @{username} | Period: {period}")
        else:
            st.info(f"XTracker data not available for @{username}. Check connectivity.")
        st.divider()
    return _widgets


def kaito_placeholder_widgets(state, capital):
    """Kaito AI placeholder with countdown to March 2026."""
    launch_date = datetime(2026, 3, 1)
    now = datetime.now()
    delta = launch_date - now

    if delta.total_seconds() > 0:
        st.warning(f"LAUNCHING MARCH 2026 — {delta.days} days remaining")
        col1, col2, col3 = st.columns(3)
        col1.metric("Days Until Launch", delta.days)
        col2.metric("Status", "MONITORING")
        col3.metric("Markets Found", 0)
    else:
        st.success("Kaito AI markets should be LIVE! Scan for markets.")
    st.divider()


def temperature_widgets(state, capital):
    """Temperature-specific widgets: city selector."""
    cities = ["NYC", "London", "Chicago", "Seoul", "Miami", "Atlanta",
              "Toronto", "Dallas", "Paris", "Seattle"]
    st.subheader("City Selection")
    selected = st.multiselect("Select cities to monitor", cities, default=["NYC", "Chicago"])
    if selected:
        st.caption(f"Monitoring: {', '.join(selected)}")
    st.divider()


def box_office_widgets(state, capital):
    """Box office specific widgets."""
    st.subheader("Current Releases")
    st.caption("Box office tracking for opening weekends. Markets appear when new movies release.")
    st.divider()


def mrbeast_widgets(state, capital):
    """MrBeast-specific widgets."""
    st.subheader("YouTube View Tracking")
    st.caption("View counts are tracked in near-real-time from YouTube. Scan markets to find active video brackets.")
    st.divider()

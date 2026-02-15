"""
Shared page layout builder for all 9 strategy pages.
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
    STRATEGY_CONFIG,
)
from core.api_client import (
    get_xtracker_user, get_active_trackings, get_window_post_count,
    get_apple_music_top_albums, get_latest_gpu_price, get_gpu_price_history,
)
from core.simulation_engine import simulate_buy
from core.strategy_content import STRATEGY_CONTENT

AUTO_SCAN_INTERVAL = 300  # 5 minutes in seconds


def _should_auto_scan(strategy_name: str) -> bool:
    """Check if enough time has passed since last scan for auto-scan."""
    last_key = f"{strategy_name}_last_auto_scan"
    last_scan = st.session_state.get(last_key, 0)
    now = time.time()
    if now - last_scan >= AUTO_SCAN_INTERVAL:
        st.session_state[last_key] = now
        return True
    return False


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

    # --- Auto-scan: trigger scan every 5 minutes ---
    if _should_auto_scan(strategy_name):
        st.session_state[f"{strategy_name}_scan"] = True

    # --- Sidebar ---
    with st.sidebar:
        tier_color = ":green" if tier == 1 else ":orange"
        st.markdown(f"### {page_title}")
        st.markdown(f"**Tier {tier}** {tier_color}[{'HIGH PRIORITY' if tier == 1 else 'MODERATE'}]")
        st.divider()

        if st.button("Scan Markets", key="scan_btn", use_container_width=True):
            st.session_state[f"{strategy_name}_scan"] = True
            st.session_state[f"{strategy_name}_last_auto_scan"] = time.time()

        st.caption("Auto-scan: every 5 minutes")

        # Show time until next auto-scan
        last_scan = st.session_state.get(f"{strategy_name}_last_auto_scan", 0)
        if last_scan > 0:
            next_scan_in = max(0, AUTO_SCAN_INTERVAL - (time.time() - last_scan))
            mins = int(next_scan_in // 60)
            secs = int(next_scan_in % 60)
            st.caption(f"Next scan in: {mins}m {secs}s")

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
            last_ts = state.last_updated
            last_str = datetime.fromtimestamp(last_ts).strftime("%H:%M:%S") if last_ts else "Never"
            st.info(f"Tracking {len(state.events_tracked)} events. Last scan: {last_str}. Auto-scan every 5 min.")
            for eid, meta in state.events_tracked.items():
                with st.container(border=True):
                    cols = st.columns([3, 1, 1, 1, 1])
                    cols[0].write(f"**{meta.get('title', 'Unknown Event')}**")
                    cols[1].write(f"Brackets: {meta.get('bracket_count', '?')}")
                    cols[2].write(f"Cost: ${meta.get('total_cost', 0):.2f}")
                    cols[3].write(f"Edge: {meta.get('edge_pct', 0):.0f}%")
                    if meta.get('edge', 0) > 0.30:
                        cols[4].success("QUALIFYING")
                    elif meta.get('edge', 0) > 0.15:
                        cols[4].warning("MARGINAL")
                    else:
                        cols[4].error("NO EDGE")
        else:
            st.info("No markets scanned yet. First auto-scan will run shortly.")

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

    # --- Auto-refresh via st.rerun with fragment ---
    # Use Streamlit's built-in auto-rerun to trigger every 5 minutes
    _schedule_auto_rerun(strategy_name)


def _schedule_auto_rerun(strategy_name: str):
    """Schedule the next auto-rerun at the 5-minute mark."""
    last_scan = st.session_state.get(f"{strategy_name}_last_auto_scan", 0)
    if last_scan > 0:
        next_scan_in = AUTO_SCAN_INTERVAL - (time.time() - last_scan)
        if next_scan_in <= 0:
            # Time to scan again
            st.rerun()
        else:
            # Use st.empty placeholder to trigger rerun at the right time
            # Streamlit's auto_refresh will handle this
            import streamlit.components.v1 as components
            components.html(
                f"""<script>
                    setTimeout(function() {{
                        window.parent.postMessage({{type: 'streamlit:rerun'}}, '*');
                    }}, {int(next_scan_in * 1000)});
                </script>""",
                height=0,
            )
    else:
        # First load — trigger initial scan after 5 seconds
        st.session_state[f"{strategy_name}_last_auto_scan"] = time.time()
        import streamlit.components.v1 as components
        components.html(
            """<script>
                setTimeout(function() {
                    window.parent.postMessage({type: 'streamlit:rerun'}, '*');
                }, 5000);
            </script>""",
            height=0,
        )


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

            if analysis["edge"] > 0.30 and analysis["qualifying"]:
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

            elif analysis["edge"] > 0.15:
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
        data = get_xtracker_user(username)
        if data:
            total_posts = data.get("_count", {}).get("posts", "N/A")
            last_sync = data.get("lastSync", "")
            trackings = data.get("trackings", [])
            active = [t for t in trackings if t.get("isActive")]

            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Posts (All Time)", f"{total_posts:,}" if isinstance(total_posts, int) else total_posts)
            with col2:
                st.metric("Active Tracking Windows", len(active))
            with col3:
                if last_sync:
                    try:
                        sync_dt = datetime.fromisoformat(last_sync.replace("Z", "+00:00"))
                        st.caption(f"Last sync: {sync_dt.strftime('%m/%d %H:%M:%S UTC')}")
                    except ValueError:
                        st.caption(f"Last sync: {last_sync}")

            # Show active tracking windows with post counts
            if active:
                for tracking in active:
                    title = tracking.get("title", "Unknown window")
                    start = tracking.get("startDate", "")
                    end = tracking.get("endDate", "")
                    with st.container(border=True):
                        tcol1, tcol2 = st.columns([3, 1])
                        tcol1.write(f"**{title}**")
                        if start and end:
                            window_count = get_window_post_count(username, start, end)
                            if window_count is not None:
                                tcol2.metric("Posts in Window", window_count)
                            else:
                                tcol2.write("Count unavailable")
        else:
            st.warning(f"XTracker data not available for @{username}. API may be temporarily down.")
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


def album_sales_widgets(state, capital):
    """Album sales widgets: Apple Music chart positions."""
    st.subheader("Apple Music Top Albums (US)")
    albums = get_apple_music_top_albums("us", 25)
    if albums:
        col1, col2 = st.columns([1, 3])
        with col1:
            st.metric("Chart Data", f"{len(albums)} albums")
        with col2:
            st.caption("Source: Apple Music RSS (free, updated daily)")

        # Show top 10 albums with rank
        rows = []
        for i, album in enumerate(albums[:10], 1):
            rows.append({
                "Rank": f"#{i}",
                "Album": album.get("name", "Unknown"),
                "Artist": album.get("artistName", "Unknown"),
                "Release Date": album.get("releaseDate", ""),
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        # Highlight recent releases (last 7 days) — these are the ones with active markets
        from datetime import datetime, timedelta
        cutoff = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        recent = [a for a in albums if a.get("releaseDate", "") >= cutoff]
        if recent:
            st.info(f"{len(recent)} recent releases (last 7 days) — check for active bracket markets")
    else:
        st.warning("Apple Music chart data unavailable. API may be temporarily down.")
    st.divider()


def gpu_price_widgets(state, capital):
    """GPU price tracking widgets: H100 rental price data."""
    st.subheader("H100 GPU Rental Prices")

    latest = get_latest_gpu_price()
    if latest:
        # Display latest price data
        col1, col2, col3 = st.columns(3)
        with col1:
            price = latest.get("price") or latest.get("avg_price") or latest.get("value")
            if price:
                st.metric("Latest H100 Price", f"${float(price):.2f}/hr")
            else:
                st.metric("Latest Entry", str(latest))
        with col2:
            date_val = latest.get("date") or latest.get("timestamp") or ""
            st.caption(f"Date: {date_val}")
        with col3:
            st.caption("Source: United Compute GPU Price Tracker")

        # Show price history chart if available
        history = get_gpu_price_history()
        if len(history) >= 2:
            prices = []
            dates = []
            for entry in history[-30:]:  # Last 30 days
                p = entry.get("price") or entry.get("avg_price") or entry.get("value")
                d = entry.get("date") or entry.get("timestamp")
                if p and d:
                    try:
                        prices.append(float(p))
                        dates.append(str(d))
                    except (ValueError, TypeError):
                        pass
            if prices:
                chart_data = pd.DataFrame({"Date": dates, "Price ($/hr)": prices})
                st.line_chart(chart_data, x="Date", y="Price ($/hr)")
    else:
        st.warning("GPU price data unavailable. GitHub data source may be temporarily down.")
        st.caption("Resolution source: Silicon Data H100 Index (SDH100RT) — silicondata.com")
    st.divider()


def mrbeast_widgets(state, capital):
    """MrBeast-specific widgets."""
    st.subheader("YouTube View Tracking")
    st.caption("View counts are tracked in near-real-time from YouTube. Scan markets to find active video brackets.")
    st.divider()

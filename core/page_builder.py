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
    estimate_outcome, select_bracket_spread,
    STRATEGY_CONFIG,
)
from core.api_client import (
    get_xtracker_user, get_active_trackings, get_window_post_count,
    get_apple_music_top_albums, get_latest_gpu_price, get_gpu_price_history,
    get_market_resolution, get_orderbook,
)
from core.simulation_engine import simulate_buy, simulate_sell
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


TAKE_PROFIT_BID = 0.30  # Auto-sell when best bid >= $0.30


def _sync_settled_trades(state: StrategyState, capital: CapitalManager) -> dict:
    """
    Check all open trades for resolution or take-profit.
    Returns summary dict and current_bids for mark-to-market.
    """
    open_trades = state.get_open_trades()
    if not open_trades:
        return {"settled": 0, "won": 0, "lost": 0, "sold": 0,
                "pnl": 0.0, "current_bids": {}}

    settled = []
    current_bids: dict[str, float] = {}

    for trade in open_trades:
        # --- 1. Check Gamma API resolution ---
        if trade.market_id:
            resolution = get_market_resolution(trade.market_id)
            if resolution and resolution["resolved"] and resolution["result"]:
                winner = resolution["result"]  # "yes" or "no"
                trade_side = trade.side.lower()
                if trade_side == winner:
                    pnl = (1.00 - trade.entry_price) * trade.shares
                    state.close_trade(trade.trade_id, "WON", 1.00, round(pnl, 4))
                    settled.append(("WON", pnl))
                else:
                    pnl = -trade.entry_cost
                    state.close_trade(trade.trade_id, "LOST", 0.00, round(pnl, 4))
                    settled.append(("LOST", pnl))
                continue  # Trade closed, skip orderbook check

        # --- 2. Fetch orderbook for take-profit + mark-to-market ---
        if not trade.token_id:
            continue

        orderbook = get_orderbook(trade.token_id)
        if not orderbook:
            continue

        best_bid = orderbook.get("best_bid", 0.0)
        current_bids[trade.token_id] = best_bid

        # --- 3. Take-profit: auto-sell when bid >= $0.30 ---
        if best_bid >= TAKE_PROFIT_BID:
            sell_result = simulate_sell(orderbook, trade.shares)
            if sell_result:
                proceeds = sell_result["proceeds"]
                pnl = proceeds - trade.entry_cost
                exit_price = sell_result["avg_price"]
                state.close_trade(trade.trade_id, "SOLD", round(exit_price, 6),
                                  round(pnl, 4))
                settled.append(("SOLD", pnl))

    won = [s for s in settled if s[0] == "WON"]
    lost = [s for s in settled if s[0] == "LOST"]
    sold = [s for s in settled if s[0] == "SOLD"]

    return {
        "settled": len(settled),
        "won": len(won),
        "lost": len(lost),
        "sold": len(sold),
        "pnl": round(sum(p for _, p in settled), 4),
        "current_bids": current_bids,
    }


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

    # --- Settlement: run on every scan cycle ---
    current_bids: dict[str, float] = st.session_state.get(f"{strategy_name}_current_bids", {})
    if st.session_state.get(f"{strategy_name}_scan"):
        with st.spinner("Settling open positions..."):
            settle_result = _sync_settled_trades(state, capital)
            current_bids = settle_result["current_bids"]
            st.session_state[f"{strategy_name}_current_bids"] = current_bids
            if settle_result["settled"] > 0:
                parts = []
                if settle_result["won"]:
                    parts.append(f"{settle_result['won']} WON")
                if settle_result["lost"]:
                    parts.append(f"{settle_result['lost']} LOST")
                if settle_result["sold"]:
                    parts.append(f"{settle_result['sold']} SOLD")
                pnl = settle_result["pnl"]
                st.success(f"Settled {settle_result['settled']} trades: "
                           f"{', '.join(parts)} ({'+' if pnl >= 0 else ''}${pnl:.2f})")

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

        # Quick metrics in sidebar (with mark-to-market bids)
        metrics = capital.get_metrics(current_bids)
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
    metrics = capital.get_metrics(current_bids)
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
                    if meta.get('edge', 0) > 0.05:
                        cols[4].success("QUALIFYING")
                    elif meta.get('edge', 0) > 0.02:
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
            bid = current_bids.get(t.token_id, 0.0)
            mkt_value = t.shares * bid if bid else 0.0
            unreal_pnl = mkt_value - t.entry_cost if bid else 0.0
            rows.append({
                "Bracket": t.bracket_title[:40],
                "Entry Price": f"${t.entry_price:.4f}",
                "Shares": f"{t.shares:.1f}",
                "Cost": f"${t.entry_cost:.2f}",
                "Bid": f"${bid:.3f}" if bid else "-",
                "Unrealized": f"${unreal_pnl:+.2f}" if bid else "-",
                "Hold Time": f"{hold_hours:.1f}h",
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
    """Scan for markets, analyze brackets, and display with batch buy."""
    events = discover_events(strategy_name)

    if not events:
        st.warning("No active events found for this strategy. Markets may not be open yet.")
        return

    st.success(f"Found {len(events)} events")

    # Get outcome prediction for this strategy
    prediction = None
    for event in events:
        if prediction is None:
            prediction = estimate_outcome(strategy_name, event)
        break  # Use first event for prediction context

    # Show prediction if available
    if prediction:
        with st.container(border=True):
            st.markdown("**Outcome Prediction**")
            est = prediction.get("estimate", 0)
            source = prediction.get("source", "")
            pcols = st.columns(4)

            if "velocity" in prediction:
                pcols[0].metric("Estimated Final", f"~{est:.0f}")
                pcols[1].metric("Velocity", f"{prediction['velocity']:.1f}/hr")
                pcols[2].metric("Current Count", prediction.get("current_count", "?"))
                pcols[3].metric("Hours Left", f"{prediction.get('remaining_hours', 0):.1f}h")
                window_title = prediction.get("window_title", "")
                if window_title:
                    st.caption(f"Window: {window_title} | Source: {source}")
            elif "top_album" in prediction:
                pcols[0].metric("Est. Units", f"~{est:,.0f}")
                pcols[1].write(f"Top: {prediction['top_album']}")
                pcols[2].write(f"By: {prediction['top_artist']}")
                pcols[3].caption(source)
            else:
                pcols[0].metric("Estimate", f"{est}")
                pcols[1].caption(source)

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
            cols[3].metric("Qualifying (1-10c)", len(analysis["qualifying"]))

            if analysis["edge"] > 0.05 and analysis["qualifying"]:
                # Fetch orderbooks for qualifying brackets
                enriched = fetch_bracket_orderbooks(analysis["qualifying"][:20])

                # Smart selection
                selected = select_bracket_spread(enriched, strategy_name, prediction)
                non_selected = [b for b in enriched if not b.get("selected")]

                # Duplicate protection: filter out brackets we already hold
                held_tokens = {t.token_id for t in state.get_open_trades()}
                new_selected = [b for b in selected if b.get("token_id", "") not in held_tokens]
                already_held = len(selected) - len(new_selected)

                # Compute spread cost summary
                spread_cost = sum(
                    b.get("best_ask", b.get("yes_price", 0))
                    for b in selected if b.get("orderbook")
                )
                bet_size = capital.get_bet_size()
                total_batch_cost = min(bet_size * len(new_selected), capital.cash)

                # Show selected brackets
                sel_method = "proximity to estimate" if prediction else "cheapest price"
                st.markdown(f"**Selected Brackets** ({len(selected)} via {sel_method}):")

                rows = []
                for b in selected:
                    ask = b.get("best_ask", b.get("yes_price", 0))
                    held = b.get("token_id", "") in held_tokens
                    rows.append({
                        "Bracket": b.get("title", "")[:50],
                        "Ask": f"${ask:.3f}",
                        "Vol": f"${b.get('volume', 0):,.0f}",
                        "Spread": f"${b.get('spread', 0):.3f}" if b.get("spread") else "-",
                        "Filters": "PASS" if b.get("passes_filters") else "WARN",
                        "Status": "HELD" if held else "NEW",
                    })
                if rows:
                    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

                # Spread summary
                scol1, scol2, scol3 = st.columns(3)
                scol1.metric("Total Spread Ask", f"${spread_cost:.3f}")
                scol2.metric("Potential Payout", "$1.00")
                edge_pct = ((1.0 - spread_cost) / 1.0 * 100) if spread_cost < 1 else 0
                scol3.metric("Spread Edge", f"{edge_pct:.0f}%")

                # Auto-execute batch buy on new brackets
                if new_selected:
                    st.info(f"Auto-buying {len(new_selected)} new brackets (~${total_batch_cost:.2f})...")
                    _execute_batch_trade(state, capital, event, new_selected)
                elif already_held:
                    st.success(f"All {already_held} selected brackets already held. No new trades needed.")

                # Manual re-buy button for edge cases (e.g. after reset)
                btn_key = f"rebuy_{strategy_name}_{event_id}_{int(time.time()) // 300}"
                if selected and st.button("Re-buy Full Spread", key=btn_key, type="secondary"):
                    _execute_batch_trade(state, capital, event, selected)

                # Show non-selected brackets in secondary table
                if non_selected:
                    with st.expander(f"Other qualifying brackets ({len(non_selected)})"):
                        other_rows = []
                        for b in non_selected:
                            ask = b.get("best_ask", b.get("yes_price", 0))
                            other_rows.append({
                                "Bracket": b.get("title", "")[:50],
                                "Ask": f"${ask:.3f}",
                                "Vol": f"${b.get('volume', 0):,.0f}",
                            })
                        st.dataframe(pd.DataFrame(other_rows), use_container_width=True, hide_index=True)

            elif analysis["edge"] > 0.02:
                st.warning(f"Marginal edge ({analysis['edge_pct']:.0f}%). Monitor but don't trade.")
            else:
                st.error(f"No edge ({analysis['edge_pct']:.0f}%). Bracket costs too high.")


def _execute_batch_trade(state: StrategyState, capital: CapitalManager, event: dict, selected_brackets: list[dict]):
    """Execute batch paper trades on selected brackets."""
    results = []
    total_cost = 0.0
    total_shares = 0.0
    skipped = 0

    for bracket in selected_brackets:
        bet_size = capital.get_bet_size()

        if not capital.can_afford(bet_size):
            skipped += len(selected_brackets) - len(results) - skipped
            st.warning(f"Ran out of cash after {len(results)} trades. ${capital.cash:.2f} remaining.")
            break

        orderbook = bracket.get("orderbook")
        if not orderbook:
            skipped += 1
            continue

        result = simulate_buy(orderbook, bet_size)
        if not result:
            skipped += 1
            continue

        trade_id = f"SIM-{bracket.get('condition_id', 'X')[:8]}-{int(time.time())}-{len(results)}"
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
        results.append(result)
        total_cost += result["total_cost"]
        total_shares += result["shares"]

    if results:
        avg_slip = sum(r["slippage_vs_best"] for r in results) / len(results)
        st.success(
            f"Batch complete: {len(results)} trades placed, "
            f"${total_cost:.2f} total cost, "
            f"avg slippage {avg_slip:.2%}"
        )
        if skipped:
            st.caption(f"{skipped} brackets skipped (no orderbook or no fill)")
    else:
        st.error("No trades could be filled. Orderbooks may be empty.")


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

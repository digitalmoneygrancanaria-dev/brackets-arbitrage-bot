"""
Strategy-specific event and bracket discovery.
Searches Gamma API for qualifying bracket markets per strategy.
Includes smart bracket selection and outcome estimation.
"""

import re
import time
from datetime import datetime, timezone
from typing import Optional
from core import api_client
from core.simulation_engine import (
    compute_bracket_set_cost,
    compute_theoretical_edge,
    passes_volume_filter,
    passes_liquidity_filter,
)

# Strategy search configurations
STRATEGY_CONFIG = {
    "trump_posts": {
        "queries": ["truth social", "donald trump # truth"],
        "xtracker_user": "realDonaldTrump",
        "category": "social_media",
        "target_brackets": 8,
    },
    "mrbeast_views": {
        "queries": ["mrbeast", "mr beast"],
        "xtracker_user": None,
        "category": "youtube",
        "target_brackets": 8,
    },
    "kaito_ai": {
        "queries": ["kaito", "mindshare"],
        "xtracker_user": None,
        "category": "kaito",
        "target_brackets": 8,
    },
    "temperature": {
        "queries": ["highest temperature"],
        "xtracker_user": None,
        "category": "temperature",
        "target_brackets": 6,
        "cities": ["nyc", "london", "chicago", "seoul", "miami", "atlanta",
                    "toronto", "dallas", "paris", "seattle"],
    },
    "tate_posts": {
        "queries": ["andrew tate", "tate # posts"],
        "xtracker_user": "Cobratate",
        "category": "social_media",
        "target_brackets": 15,
    },
    "box_office": {
        "queries": ["box office", "opening weekend"],
        "xtracker_user": None,
        "category": "box_office",
        "target_brackets": 4,
    },
    "musk_tweets": {
        "queries": ["musk # tweets", "musk tweets"],
        "xtracker_user": "elonmusk",
        "category": "social_media",
        "target_brackets": 10,
    },
    "album_sales": {
        "queries": ["first week album sales", "first week sales"],
        "xtracker_user": None,
        "category": "album_sales",
        "target_brackets": 8,
    },
    "gpu_prices": {
        "queries": ["gpu rental", "h100"],
        "xtracker_user": None,
        "category": "gpu_prices",
        "target_brackets": 6,
    },
}


def discover_events(strategy_name: str) -> list[dict]:
    """
    Search for active bracket events matching strategy keywords.
    Only returns events with 3+ markets (bracket-type).
    """
    config = STRATEGY_CONFIG.get(strategy_name)
    if not config:
        return []

    events = api_client.search_events_broad(config["queries"])
    # Filter to bracket events only (3+ markets = multi-bracket)
    bracket_events = [e for e in events if len(e.get("markets", [])) >= 3]
    return bracket_events


def analyze_event_brackets(event: dict) -> dict:
    """
    For a given event, fetch all bracket markets and compute:
    - bracket prices (YES side)
    - total bracket cost
    - theoretical edge
    - qualifying brackets (price 1-10 cents)
    """
    markets = event.get("markets", [])
    if not markets:
        return {"event": event, "brackets": [], "total_cost": 0, "edge": 0, "qualifying": []}

    brackets = []
    for mkt in markets:
        # Get YES price from outcomePrices
        outcome_prices = mkt.get("outcomePrices")
        yes_price = 0.0
        if outcome_prices:
            try:
                if isinstance(outcome_prices, str):
                    import json
                    prices = json.loads(outcome_prices)
                else:
                    prices = outcome_prices
                yes_price = float(prices[0]) if prices else 0.0
            except (json.JSONDecodeError, IndexError, ValueError):
                pass

        # Fallback to bestAsk if available
        if yes_price == 0.0:
            yes_price = float(mkt.get("bestAsk", 0) or 0)

        volume = float(mkt.get("volume", 0) or mkt.get("volumeNum", 0) or 0)

        brackets.append({
            "market_id": mkt.get("id", ""),
            "title": mkt.get("groupItemTitle", mkt.get("question", "Unknown")),
            "yes_price": round(yes_price, 4),
            "volume": round(volume, 2),
            "condition_id": mkt.get("conditionId", ""),
            "token_id": _get_yes_token_id(mkt),
            "resolved": mkt.get("resolved", False),
            "closed": mkt.get("closed", False),
            "end_date": mkt.get("endDate", ""),
        })

    # Compute totals
    active_brackets = [b for b in brackets if not b["resolved"] and not b["closed"]]
    prices = [b["yes_price"] for b in active_brackets if b["yes_price"] > 0]
    total_cost = compute_bracket_set_cost(prices)
    edge = compute_theoretical_edge(total_cost)

    # Qualifying brackets: price between 1-10 cents
    qualifying = [b for b in active_brackets if 0.01 <= b["yes_price"] <= 0.10]

    return {
        "event": event,
        "brackets": brackets,
        "active_brackets": active_brackets,
        "total_cost": round(total_cost, 4),
        "edge": round(edge, 4),
        "edge_pct": round(edge * 100, 1),
        "qualifying": qualifying,
        "bracket_count": len(active_brackets),
    }


def _get_yes_token_id(market: dict) -> str:
    """Extract YES token ID from market data."""
    tokens = market.get("clobTokenIds")
    if tokens:
        try:
            if isinstance(tokens, str):
                import json
                tokens = json.loads(tokens)
            if isinstance(tokens, list) and len(tokens) > 0:
                return tokens[0]  # First token is YES
        except (json.JSONDecodeError, IndexError):
            pass
    return ""


def fetch_bracket_orderbooks(qualifying_brackets: list[dict]) -> list[dict]:
    """
    Fetch orderbooks for qualifying brackets and check volume/liquidity filters.
    Returns brackets enriched with orderbook data and filter results.
    """
    enriched = []
    for bracket in qualifying_brackets:
        token_id = bracket.get("token_id", "")
        if not token_id:
            continue

        orderbook = api_client.get_orderbook(token_id)
        if not orderbook:
            bracket["orderbook"] = None
            bracket["passes_filters"] = False
            enriched.append(bracket)
            continue

        bracket["orderbook"] = orderbook
        bracket["best_bid"] = orderbook["best_bid"]
        bracket["best_ask"] = orderbook["best_ask"]
        bracket["spread"] = orderbook["spread"]
        bracket["bid_depth_usd"] = orderbook["bid_depth_usd"]
        bracket["ask_depth_usd"] = orderbook["ask_depth_usd"]

        # Check filters
        vol_ok = bracket.get("volume", 0) >= 1000
        liq_ok = passes_liquidity_filter(orderbook, min_depth=1000)
        bracket["passes_volume"] = vol_ok
        bracket["passes_liquidity"] = liq_ok
        bracket["passes_filters"] = vol_ok or liq_ok  # Pass if either filter met

        enriched.append(bracket)

    return enriched


def get_strategy_xtracker(strategy_name: str) -> Optional[dict]:
    """Get XTracker data for social media strategies."""
    config = STRATEGY_CONFIG.get(strategy_name, {})
    username = config.get("xtracker_user")
    if not username:
        return None
    return api_client.get_xtracker_user(username)


# ---------------------------------------------------------------------------
# Smart bracket selection & outcome estimation
# ---------------------------------------------------------------------------

def parse_bracket_range(title: str) -> Optional[tuple[float, float]]:
    """
    Extract numeric low/high from bracket titles.
    Handles patterns like:
      "60-79", "100-119 posts", "≤31F", "≥42F", "<50K", "200+",
      "$0.40-$0.50/hr", "32-33F", "14M-17M"
    Returns (low, high) or None if unparseable.
    """
    if not title:
        return None

    # Normalize: strip $, commas, F/°, "posts", "views", "/hr", etc.
    t = title.strip()

    # Pattern: "≤X" or "<X" or "Under X" or "Less than X" → (0, X)
    m = re.search(r'(?:[≤<]|[Uu]nder|[Ll]ess\s+than)\s*\$?([\d,.]+)', t)
    if m:
        val = _parse_num(m.group(1))
        if val is not None:
            return (0.0, val)

    # Pattern: "≥X" or ">X" or "X+" or "Over X" or "More than X" → (X, X*2)
    m = re.search(r'(?:[≥>]|[Oo]ver|[Mm]ore\s+than)\s*\$?([\d,.]+)', t)
    if m:
        val = _parse_num(m.group(1))
        if val is not None:
            return (val, val * 2)  # Open-ended upper; use 2x as proxy

    m = re.search(r'\$?([\d,.]+)\s*\+', t)
    if m:
        val = _parse_num(m.group(1))
        if val is not None:
            return (val, val * 2)

    # Pattern: "X-Y" (with optional $ prefix, K/M suffix, unit suffix like F, /hr)
    m = re.search(r'\$?([\d,.]+)\s*[KkMm]?\s*[-–—to]+\s*\$?([\d,.]+)\s*[KkMm]?', t)
    if m:
        low = _parse_num_with_suffix(m.group(0).split('-')[0].split('–')[0].split('—')[0].strip())
        high = _parse_num_with_suffix(m.group(0).split('-')[-1].split('–')[-1].split('—')[-1].strip())
        if low is not None and high is not None:
            return (low, high)

    return None


def _parse_num(s: str) -> Optional[float]:
    """Parse a plain number string, stripping commas."""
    try:
        return float(s.replace(",", ""))
    except (ValueError, TypeError):
        return None


def _parse_num_with_suffix(s: str) -> Optional[float]:
    """Parse a number with optional K/M suffix, stripping $, commas, units."""
    s = re.sub(r'[$/hrFf°\s]', '', s.strip())
    m = re.match(r'^([\d,.]+)\s*([KkMm]?)$', s)
    if not m:
        return _parse_num(s)
    val = _parse_num(m.group(1))
    if val is None:
        return None
    suffix = m.group(2).upper()
    if suffix == 'K':
        val *= 1_000
    elif suffix == 'M':
        val *= 1_000_000
    return val


def estimate_outcome(strategy_name: str, event: dict) -> Optional[dict]:
    """
    Estimate the likely outcome for a strategy using real-time data.

    Returns dict with:
        estimate: float - projected final value
        velocity: float - rate per hour (for social media)
        current_count: int - posts so far
        remaining_hours: float - hours left in window
        source: str - description of data source
    Or None if no real-time predictor is available.
    """
    config = STRATEGY_CONFIG.get(strategy_name, {})
    category = config.get("category", "")

    if category == "social_media":
        return _estimate_social_media(config)

    if category == "gpu_prices":
        return _estimate_gpu_price()

    if category == "album_sales":
        return _estimate_album_sales()

    # temperature, box_office, youtube, kaito — no real-time predictor yet
    return None


def _estimate_social_media(config: dict) -> Optional[dict]:
    """Estimate post count using XTracker velocity projection."""
    username = config.get("xtracker_user")
    if not username:
        return None

    trackings = api_client.get_active_trackings(username)
    if not trackings:
        return None

    # Use the first active tracking window
    tracking = trackings[0]
    start_str = tracking.get("startDate", "")
    end_str = tracking.get("endDate", "")
    if not start_str or not end_str:
        return None

    try:
        start_dt = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
        end_dt = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
    except ValueError:
        return None

    now = datetime.now(timezone.utc)
    elapsed = (now - start_dt).total_seconds() / 3600  # hours
    remaining = max(0, (end_dt - now).total_seconds() / 3600)

    if elapsed <= 0:
        return None

    # Get current post count in window
    current_count = api_client.get_window_post_count(username, start_str, end_str)
    if current_count is None:
        return None

    velocity = current_count / elapsed if elapsed > 0 else 0
    estimated_final = current_count + (velocity * remaining)

    return {
        "estimate": round(estimated_final, 1),
        "velocity": round(velocity, 2),
        "current_count": current_count,
        "elapsed_hours": round(elapsed, 1),
        "remaining_hours": round(remaining, 1),
        "window_title": tracking.get("title", ""),
        "source": f"XTracker @{username}",
    }


def _estimate_gpu_price() -> Optional[dict]:
    """Estimate GPU price from latest tracker data."""
    latest = api_client.get_latest_gpu_price()
    if not latest:
        return None

    price = latest.get("price") or latest.get("avg_price") or latest.get("value")
    if not price:
        return None

    try:
        price_val = float(price)
    except (ValueError, TypeError):
        return None

    return {
        "estimate": price_val,
        "source": "United Compute GPU Tracker",
    }


def _estimate_album_sales() -> Optional[dict]:
    """
    Rough album sales estimate from Apple Music chart rank.
    Top 1 → ~200K+, Top 5 → ~100-150K, Top 10 → ~50-100K, etc.
    Very rough heuristic — better than nothing.
    """
    albums = api_client.get_apple_music_top_albums("us", 10)
    if not albums:
        return None

    # Map chart rank to rough first-week unit estimate
    rank_to_sales = {
        1: 200_000, 2: 150_000, 3: 125_000, 4: 100_000, 5: 80_000,
        6: 65_000, 7: 55_000, 8: 45_000, 9: 40_000, 10: 35_000,
    }

    # Return the #1 album estimate as a reference point
    top = albums[0]
    return {
        "estimate": rank_to_sales.get(1, 200_000),
        "top_album": top.get("name", "Unknown"),
        "top_artist": top.get("artistName", "Unknown"),
        "source": "Apple Music chart rank heuristic",
    }


def select_bracket_spread(
    qualifying: list[dict],
    strategy_name: str,
    prediction: Optional[dict] = None,
) -> list[dict]:
    """
    Select the best N brackets from qualifying list.

    If prediction available: sort by distance from estimate, pick closest N.
    If no prediction: sort by YES price ascending (cheapest), pick N with best coverage.

    Returns list of selected bracket dicts with 'selected' flag added.
    """
    config = STRATEGY_CONFIG.get(strategy_name, {})
    target_n = config.get("target_brackets", 8)

    if not qualifying:
        return []

    # Cap target at available brackets
    target_n = min(target_n, len(qualifying))

    estimated_val = prediction.get("estimate") if prediction else None

    if estimated_val is not None:
        # Smart selection: sort by distance from estimate
        scored = []
        for b in qualifying:
            bracket_range = parse_bracket_range(b.get("title", ""))
            if bracket_range:
                low, high = bracket_range
                mid = (low + high) / 2
                distance = abs(mid - estimated_val)
            else:
                # Unparseable bracket — assign high distance so it's picked last
                distance = float("inf")
            scored.append((distance, b))

        scored.sort(key=lambda x: x[0])
        selected = [b for _, b in scored[:target_n]]
    else:
        # Fallback: even spread across bracket range for maximum coverage
        scored = []
        for b in qualifying:
            bracket_range = parse_bracket_range(b.get("title", ""))
            if bracket_range:
                mid = (bracket_range[0] + bracket_range[1]) / 2
            else:
                mid = float("inf")
            scored.append((mid, b))
        scored.sort(key=lambda x: x[0])

        n = len(scored)
        if n <= target_n:
            selected = [b for _, b in scored]
        elif target_n == 1:
            selected = [scored[n // 2][1]]
        else:
            indices = [round(i * (n - 1) / (target_n - 1)) for i in range(target_n)]
            selected = [scored[i][1] for i in indices]

    # Mark selected
    for b in selected:
        b["selected"] = True

    return selected

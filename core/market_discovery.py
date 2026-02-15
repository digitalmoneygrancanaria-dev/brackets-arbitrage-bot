"""
Strategy-specific event and bracket discovery.
Searches Gamma API for qualifying bracket markets per strategy.
"""

import time
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
    },
    "mrbeast_views": {
        "queries": ["mrbeast", "mr beast"],
        "xtracker_user": None,
        "category": "youtube",
    },
    "kaito_ai": {
        "queries": ["kaito", "mindshare"],
        "xtracker_user": None,
        "category": "kaito",
    },
    "temperature": {
        "queries": ["highest temperature"],
        "xtracker_user": None,
        "category": "temperature",
        "cities": ["nyc", "london", "chicago", "seoul", "miami", "atlanta",
                    "toronto", "dallas", "paris", "seattle"],
    },
    "tate_posts": {
        "queries": ["andrew tate", "tate # posts"],
        "xtracker_user": "Cobratate",
        "category": "social_media",
    },
    "box_office": {
        "queries": ["box office", "opening weekend"],
        "xtracker_user": None,
        "category": "box_office",
    },
    "musk_tweets": {
        "queries": ["musk # tweets", "musk tweets"],
        "xtracker_user": "elonmusk",
        "category": "social_media",
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
    - qualifying brackets (price 1-5 cents)
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

    # Qualifying brackets: price between 1-5 cents
    qualifying = [b for b in active_brackets if 0.01 <= b["yes_price"] <= 0.05]

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

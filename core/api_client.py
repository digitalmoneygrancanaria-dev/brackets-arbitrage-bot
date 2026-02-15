"""
Public API wrappers for Polymarket Gamma API, CLOB API, and XTracker.
No authentication required — all endpoints are read-only public.
"""

import time
import requests
from typing import Optional

GAMMA_BASE = "https://gamma-api.polymarket.com"
CLOB_BASE = "https://clob.polymarket.com"
XTRACKER_BASE = "https://xtracker.polymarket.com"

SESSION = requests.Session()
SESSION.headers.update({"Accept": "application/json"})

# Simple rate limiting
_last_request_time = 0.0
_MIN_INTERVAL = 0.25  # 250ms between requests


def _rate_limit():
    global _last_request_time
    now = time.time()
    elapsed = now - _last_request_time
    if elapsed < _MIN_INTERVAL:
        time.sleep(_MIN_INTERVAL - elapsed)
    _last_request_time = time.time()


def _get(url: str, params: dict = None, timeout: int = 15) -> Optional[dict | list]:
    _rate_limit()
    try:
        resp = SESSION.get(url, params=params, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        print(f"[API] Error fetching {url}: {e}")
        return None


# ---------------------------------------------------------------------------
# Gamma API — market/event metadata and resolution status
# ---------------------------------------------------------------------------

def search_events(query: str, active: bool = True, limit: int = 50) -> list[dict]:
    """Search for events by keyword. Returns list of event dicts."""
    params = {
        "limit": limit,
        "active": str(active).lower(),
        "closed": "false",
        "order": "volume24hr",
        "ascending": "false",
    }
    # Gamma search uses the /events endpoint with a slug filter
    data = _get(f"{GAMMA_BASE}/events", params=params)
    if not data:
        return []
    # Filter by query keyword in title or slug
    query_lower = query.lower()
    return [e for e in data if query_lower in e.get("title", "").lower()
            or query_lower in e.get("slug", "").lower()]


def search_events_broad(queries: list[str], active: bool = True) -> list[dict]:
    """Search multiple keywords and deduplicate results by event ID."""
    seen_ids = set()
    results = []
    for q in queries:
        for event in search_events(q, active=active):
            eid = event.get("id")
            if eid and eid not in seen_ids:
                seen_ids.add(eid)
                results.append(event)
    return results


def get_event(event_id: str) -> Optional[dict]:
    """Get a single event with all its markets."""
    return _get(f"{GAMMA_BASE}/events/{event_id}")


def get_market(market_id: str) -> Optional[dict]:
    """
    Get a single market by its numeric gamma market ID.
    IMPORTANT: Do NOT use condition_id query param — it's broken.
    Always use /markets/{numeric_id} path.
    """
    return _get(f"{GAMMA_BASE}/markets/{market_id}")


def get_markets_for_event(event_id: str) -> list[dict]:
    """Get all bracket markets for an event."""
    params = {"limit": 100}
    # The events endpoint includes markets inline
    event = get_event(event_id)
    if event and "markets" in event:
        return event["markets"]
    # Fallback: query markets by event slug
    return []


def search_markets(query: str, active: bool = True, limit: int = 100) -> list[dict]:
    """Search markets directly. Used when event search doesn't work."""
    params = {
        "limit": limit,
        "active": str(active).lower(),
        "closed": "false",
    }
    data = _get(f"{GAMMA_BASE}/markets", params=params)
    if not data:
        return []
    query_lower = query.lower()
    return [m for m in data if query_lower in m.get("question", "").lower()
            or query_lower in m.get("groupItemTitle", "").lower()]


# ---------------------------------------------------------------------------
# CLOB API — orderbooks and market data
# ---------------------------------------------------------------------------

def get_orderbook(token_id: str) -> Optional[dict]:
    """
    Fetch full orderbook for a token.

    CRITICAL: CLOB returns bids sorted ASCENDING (worst first) and
    asks sorted DESCENDING (worst first).
    - best_bid = max(bid prices)
    - best_ask = min(ask prices)

    Returns dict with: bids, asks, best_bid, best_ask, spread, mid_price
    """
    data = _get(f"{CLOB_BASE}/book", params={"token_id": token_id})
    if not data:
        return None

    bids = data.get("bids", [])
    asks = data.get("asks", [])

    # Parse prices as floats
    bid_prices = [float(b["price"]) for b in bids if float(b.get("price", 0)) > 0]
    ask_prices = [float(a["price"]) for a in asks if float(a.get("price", 0)) > 0]

    best_bid = max(bid_prices) if bid_prices else 0.0
    best_ask = min(ask_prices) if ask_prices else 1.0

    spread = best_ask - best_bid if best_ask > best_bid else 0.0
    mid_price = (best_bid + best_ask) / 2 if (best_bid > 0 and best_ask < 1) else best_ask

    # Compute total depth in USD
    bid_depth_usd = sum(float(b["price"]) * float(b["size"]) for b in bids)
    ask_depth_usd = sum(float(a["price"]) * float(a["size"]) for a in asks)

    return {
        "bids": bids,
        "asks": asks,
        "best_bid": best_bid,
        "best_ask": best_ask,
        "spread": spread,
        "mid_price": mid_price,
        "bid_depth_usd": bid_depth_usd,
        "ask_depth_usd": ask_depth_usd,
        "bid_count": len(bids),
        "ask_count": len(asks),
    }


def get_clob_market(condition_id: str) -> Optional[dict]:
    """Get market info from CLOB by condition_id (works unlike Gamma)."""
    return _get(f"{CLOB_BASE}/markets/{condition_id}")


# ---------------------------------------------------------------------------
# XTracker — real-time social media post counts
# ---------------------------------------------------------------------------

def get_xtracker_user(username: str) -> Optional[dict]:
    """
    Get real-time post count for a tracked user.
    Known tracked users: elonmusk, realDonaldTrump, Cobratate
    """
    data = _get(f"{XTRACKER_BASE}/user/{username}")
    return data


def get_post_count(username: str) -> Optional[int]:
    """Get the current post count for a user from XTracker."""
    data = get_xtracker_user(username)
    if data and "count" in data:
        return int(data["count"])
    return None


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

def check_api_health() -> dict:
    """Check connectivity to all three API endpoints."""
    results = {}

    # Gamma
    try:
        resp = SESSION.get(f"{GAMMA_BASE}/markets?limit=1", timeout=5)
        results["gamma"] = {"status": "ok" if resp.status_code == 200 else "error",
                            "code": resp.status_code}
    except Exception as e:
        results["gamma"] = {"status": "error", "error": str(e)}

    # CLOB
    try:
        resp = SESSION.get(f"{CLOB_BASE}/markets", timeout=5)
        results["clob"] = {"status": "ok" if resp.status_code == 200 else "error",
                           "code": resp.status_code}
    except Exception as e:
        results["clob"] = {"status": "error", "error": str(e)}

    # XTracker
    try:
        resp = SESSION.get(f"{XTRACKER_BASE}/user/elonmusk", timeout=5)
        results["xtracker"] = {"status": "ok" if resp.status_code == 200 else "error",
                               "code": resp.status_code}
    except Exception as e:
        results["xtracker"] = {"status": "error", "error": str(e)}

    return results

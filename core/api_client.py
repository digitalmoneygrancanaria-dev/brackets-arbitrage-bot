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
# Actual API: /api/users (all users) and /api/users/{handle} (single user)
# /api/users/{handle}/posts?startDate=...&endDate=... (posts in window)
# ---------------------------------------------------------------------------

def get_xtracker_users() -> Optional[list[dict]]:
    """Get all tracked users with post counts and active tracking windows."""
    data = _get(f"{XTRACKER_BASE}/api/users")
    if data and data.get("success") and "data" in data:
        return data["data"]
    return None


def get_xtracker_user(username: str) -> Optional[dict]:
    """
    Get a single tracked user's data by handle.
    Known tracked users: elonmusk, realDonaldTrump, Cobratate, WhiteHouse

    Returns dict with: handle, name, trackings[], _count.posts, lastSync, etc.
    """
    data = _get(f"{XTRACKER_BASE}/api/users/{username}")
    if data and data.get("success") and "data" in data:
        return data["data"]
    return None


def get_xtracker_posts(username: str, start_date: str = None, end_date: str = None) -> Optional[list[dict]]:
    """
    Get posts for a user, optionally filtered by date range.
    Dates should be ISO 8601 format (e.g., '2026-02-13T17:00:00.000Z').
    """
    params = {}
    if start_date:
        params["startDate"] = start_date
    if end_date:
        params["endDate"] = end_date
    data = _get(f"{XTRACKER_BASE}/api/users/{username}/posts", params=params if params else None)
    if data and data.get("success") and "data" in data:
        return data["data"]
    return None


def get_post_count(username: str) -> Optional[int]:
    """Get the total post count for a user from XTracker."""
    data = get_xtracker_user(username)
    if data:
        count = data.get("_count", {}).get("posts")
        if count is not None:
            return int(count)
    return None


def get_active_trackings(username: str) -> list[dict]:
    """Get active tracking windows for a user (linked to Polymarket markets)."""
    data = get_xtracker_user(username)
    if not data:
        return []
    trackings = data.get("trackings", [])
    return [t for t in trackings if t.get("isActive")]


def get_window_post_count(username: str, start_date: str, end_date: str) -> Optional[int]:
    """Get post count for a specific tracking window."""
    posts = get_xtracker_posts(username, start_date, end_date)
    if posts is not None:
        return len(posts)
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
        resp = SESSION.get(f"{XTRACKER_BASE}/api/users", timeout=5)
        results["xtracker"] = {"status": "ok" if resp.status_code == 200 else "error",
                               "code": resp.status_code}
    except Exception as e:
        results["xtracker"] = {"status": "error", "error": str(e)}

    return results

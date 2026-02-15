"""
Realistic fill simulation engine.
Walks orderbook levels to simulate market orders with slippage.
"""

from typing import Optional


def simulate_buy(orderbook: dict, amount_usd: float, max_depth_pct: float = 0.10) -> Optional[dict]:
    """
    Simulate a market buy by walking the ask side of the orderbook.

    Args:
        orderbook: Dict from api_client.get_orderbook() with asks list
        amount_usd: USD amount to spend
        max_depth_pct: Max fraction of total ask depth we're willing to take (10%)

    Returns dict with: shares, avg_price, total_cost, slippage_vs_best, levels_hit
    """
    asks = orderbook.get("asks", [])
    if not asks:
        return None

    # Sort asks by price ascending (best ask first)
    # CLOB returns asks descending (worst first), so reverse
    sorted_asks = sorted(asks, key=lambda a: float(a["price"]))

    best_ask = float(sorted_asks[0]["price"]) if sorted_asks else 1.0

    # Compute max shares we can take (10% of total ask depth)
    total_ask_shares = sum(float(a["size"]) for a in sorted_asks)
    max_shares = total_ask_shares * max_depth_pct

    remaining_usd = amount_usd
    total_shares = 0.0
    total_cost = 0.0
    levels_hit = 0

    for level in sorted_asks:
        if remaining_usd <= 0 or total_shares >= max_shares:
            break

        price = float(level["price"])
        size = float(level["size"])

        # How many shares can we buy at this level?
        affordable_shares = remaining_usd / price
        depth_limited_shares = max_shares - total_shares
        fill_shares = min(size, affordable_shares, depth_limited_shares)

        if fill_shares <= 0:
            break

        fill_cost = fill_shares * price
        total_shares += fill_shares
        total_cost += fill_cost
        remaining_usd -= fill_cost
        levels_hit += 1

    if total_shares == 0:
        return None

    avg_price = total_cost / total_shares
    slippage = (avg_price - best_ask) / best_ask if best_ask > 0 else 0.0

    return {
        "shares": round(total_shares, 4),
        "avg_price": round(avg_price, 6),
        "total_cost": round(total_cost, 4),
        "slippage_vs_best": round(slippage, 6),
        "best_ask": best_ask,
        "levels_hit": levels_hit,
    }


def simulate_sell(orderbook: dict, shares: float, max_depth_pct: float = 0.10) -> Optional[dict]:
    """
    Simulate a market sell by walking the bid side of the orderbook.

    Args:
        orderbook: Dict from api_client.get_orderbook() with bids list
        shares: Number of shares to sell
        max_depth_pct: Max fraction of total bid depth we're willing to hit (10%)

    Returns dict with: proceeds, avg_price, slippage_vs_best, levels_hit
    """
    bids = orderbook.get("bids", [])
    if not bids:
        return None

    # Sort bids by price descending (best bid first)
    # CLOB returns bids ascending (worst first), so reverse
    sorted_bids = sorted(bids, key=lambda b: float(b["price"]), reverse=True)

    best_bid = float(sorted_bids[0]["price"]) if sorted_bids else 0.0

    # Max shares we can sell (10% of total bid depth)
    total_bid_shares = sum(float(b["size"]) for b in sorted_bids)
    max_sellable = min(shares, total_bid_shares * max_depth_pct)

    remaining_shares = max_sellable
    total_proceeds = 0.0
    levels_hit = 0

    for level in sorted_bids:
        if remaining_shares <= 0:
            break

        price = float(level["price"])
        size = float(level["size"])

        fill_shares = min(size, remaining_shares)
        total_proceeds += fill_shares * price
        remaining_shares -= fill_shares
        levels_hit += 1

    shares_sold = max_sellable - remaining_shares
    if shares_sold == 0:
        return None

    avg_price = total_proceeds / shares_sold
    slippage = (best_bid - avg_price) / best_bid if best_bid > 0 else 0.0

    return {
        "shares_sold": round(shares_sold, 4),
        "proceeds": round(total_proceeds, 4),
        "avg_price": round(avg_price, 6),
        "slippage_vs_best": round(slippage, 6),
        "best_bid": best_bid,
        "levels_hit": levels_hit,
    }


def passes_volume_filter(market: dict, min_vol: float = 1000.0) -> bool:
    """Check if market has sufficient trading volume (>= $1,000)."""
    volume = 0.0
    for key in ("volume", "volume24hr", "volumeNum"):
        val = market.get(key)
        if val is not None:
            try:
                volume = max(volume, float(val))
            except (ValueError, TypeError):
                pass
    return volume >= min_vol


def passes_liquidity_filter(orderbook: dict, min_depth: float = 1000.0) -> bool:
    """Check if orderbook has sufficient depth (sum of price*size >= $1,000)."""
    total_depth = orderbook.get("bid_depth_usd", 0) + orderbook.get("ask_depth_usd", 0)
    return total_depth >= min_depth


def compute_bracket_set_cost(bracket_prices: list[float]) -> float:
    """
    Sum of all YES bracket prices. If < $1.00, there's a theoretical edge.
    The lower the sum, the bigger the edge.
    """
    return sum(bracket_prices)


def compute_theoretical_edge(total_cost: float) -> float:
    """
    Theoretical edge = 1.00 - total_cost.
    Positive = profitable spread, negative = no edge.
    """
    return 1.0 - total_cost

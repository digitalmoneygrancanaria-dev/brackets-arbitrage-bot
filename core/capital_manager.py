"""
Capital and position sizing for paper trading.
$1,000 starting capital per strategy, 1% per bet (~$10).
"""

from core.state_manager import StrategyState


class CapitalManager:
    """Manages capital allocation and portfolio metrics for a strategy."""

    def __init__(self, state: StrategyState, bet_pct: float = 0.01):
        self.state = state
        self.bet_pct = bet_pct  # 1% of equity per bet

    @property
    def starting_capital(self) -> float:
        return self.state.starting_capital

    @property
    def cash(self) -> float:
        return self.state.get_cash()

    @property
    def invested(self) -> float:
        return self.state.get_total_invested()

    @property
    def realized_pnl(self) -> float:
        return self.state.realized_pnl

    def get_unrealized_pnl(self, current_bids: dict[str, float]) -> float:
        """
        Compute unrealized P&L based on current bid prices.
        current_bids: {token_id: best_bid_price}
        """
        total = 0.0
        for trade in self.state.get_open_trades():
            bid = current_bids.get(trade.token_id, 0.0)
            current_value = trade.shares * bid
            total += current_value - trade.entry_cost
        return total

    def get_total_equity(self, current_bids: dict[str, float] = None) -> float:
        unrealized = self.get_unrealized_pnl(current_bids) if current_bids else 0.0
        return self.cash + self.invested + unrealized

    def get_bet_size(self, current_bids: dict[str, float] = None) -> float:
        """1% of total equity."""
        equity = self.get_total_equity(current_bids)
        return round(equity * self.bet_pct, 2)

    def can_afford(self, amount: float) -> bool:
        return self.cash >= amount

    def get_metrics(self, current_bids: dict[str, float] = None) -> dict:
        if current_bids is None:
            current_bids = {}

        unrealized = self.get_unrealized_pnl(current_bids)
        equity = self.cash + self.invested + unrealized
        return_pct = ((equity - self.starting_capital) / self.starting_capital) * 100

        closed = self.state.get_closed_trades()
        wins = [t for t in closed if t.pnl and t.pnl > 0]
        losses = [t for t in closed if t.pnl and t.pnl <= 0]

        win_rate = (len(wins) / len(closed) * 100) if closed else 0.0

        gross_profit = sum(t.pnl for t in wins) if wins else 0.0
        gross_loss = abs(sum(t.pnl for t in losses)) if losses else 0.0
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else float("inf") if gross_profit > 0 else 0.0

        return {
            "cash": round(self.cash, 2),
            "invested": round(self.invested, 2),
            "unrealized_pnl": round(unrealized, 2),
            "realized_pnl": round(self.realized_pnl, 2),
            "total_equity": round(equity, 2),
            "return_pct": round(return_pct, 2),
            "bet_size": self.get_bet_size(current_bids),
            "win_rate": round(win_rate, 1),
            "profit_factor": round(profit_factor, 2) if profit_factor != float("inf") else "inf",
            "total_trades": len(closed),
            "open_trades": len(self.state.get_open_trades()),
        }

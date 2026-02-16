"""
Persistent state management for paper trading.
Each strategy gets its own JSON file on the Railway volume.
"""

import json
import os
import time
from dataclasses import dataclass, field, asdict
from typing import Optional

DATA_DIR = os.environ.get("DATA_DIR", os.path.join(os.path.dirname(os.path.dirname(__file__)), "data"))


@dataclass
class PaperTrade:
    trade_id: str
    strategy: str
    event_title: str
    bracket_title: str
    side: str  # YES or NO
    shares: float
    entry_price: float
    entry_cost: float
    entry_time: float  # Unix timestamp
    token_id: str
    condition_id: str
    status: str = "OPEN"  # OPEN, WON, LOST, SOLD
    exit_price: Optional[float] = None
    exit_time: Optional[float] = None
    pnl: Optional[float] = None
    slippage: float = 0.0
    orderbook_depth_at_entry: float = 0.0
    market_id: str = ""
    event_id: str = ""
    fees_paid: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "PaperTrade":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class PerformanceSnapshot:
    timestamp: float
    cash: float
    invested: float
    unrealized_pnl: float
    realized_pnl: float
    total_equity: float
    open_positions: int
    closed_positions: int


class StrategyState:
    """Loads/saves per-strategy state from JSON on disk."""

    def __init__(self, strategy_name: str):
        self.strategy_name = strategy_name
        self.file_path = os.path.join(DATA_DIR, f"{strategy_name}_state.json")
        self.trades: list[PaperTrade] = []
        self.events_tracked: dict[str, dict] = {}  # event_id -> metadata
        self.performance_log: list[dict] = []
        self.starting_capital: float = 1000.0
        self.realized_pnl: float = 0.0
        self.last_updated: float = 0.0
        self._load()

    def _load(self):
        if not os.path.exists(self.file_path):
            return
        try:
            with open(self.file_path, "r") as f:
                data = json.load(f)
            self.trades = [PaperTrade.from_dict(t) for t in data.get("trades", [])]
            self.events_tracked = data.get("events_tracked", {})
            self.performance_log = data.get("performance_log", [])
            self.starting_capital = data.get("starting_capital", 1000.0)
            self.realized_pnl = data.get("realized_pnl", 0.0)
            self.last_updated = data.get("last_updated", 0.0)
        except (json.JSONDecodeError, KeyError) as e:
            print(f"[State] Error loading {self.file_path}: {e}")

    def _save(self):
        os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
        self.last_updated = time.time()
        data = {
            "strategy": self.strategy_name,
            "trades": [t.to_dict() for t in self.trades],
            "events_tracked": self.events_tracked,
            "performance_log": self.performance_log,
            "starting_capital": self.starting_capital,
            "realized_pnl": self.realized_pnl,
            "last_updated": self.last_updated,
        }
        with open(self.file_path, "w") as f:
            json.dump(data, f, indent=2, default=str)

    def add_trade(self, trade: PaperTrade):
        self.trades.append(trade)
        self._save()
        _append_simulation_log("TRADE_OPEN", self.strategy_name, trade.to_dict())

    def close_trade(self, trade_id: str, status: str, exit_price: float, pnl: float, fees: float = 0.0):
        for t in self.trades:
            if t.trade_id == trade_id:
                t.status = status
                t.exit_price = exit_price
                t.exit_time = time.time()
                t.pnl = pnl
                t.fees_paid = fees
                self.realized_pnl += pnl
                self._save()
                _append_simulation_log("TRADE_CLOSE", self.strategy_name, t.to_dict())
                return True
        return False

    def get_open_trades(self) -> list[PaperTrade]:
        return [t for t in self.trades if t.status == "OPEN"]

    def get_closed_trades(self) -> list[PaperTrade]:
        return [t for t in self.trades if t.status != "OPEN"]

    def get_total_invested(self) -> float:
        return sum(t.entry_cost for t in self.get_open_trades())

    def get_cash(self) -> float:
        invested = self.get_total_invested()
        return self.starting_capital + self.realized_pnl - invested

    def record_performance(self, unrealized_pnl: float = 0.0):
        cash = self.get_cash()
        invested = self.get_total_invested()
        snap = {
            "timestamp": time.time(),
            "cash": round(cash, 2),
            "invested": round(invested, 2),
            "unrealized_pnl": round(unrealized_pnl, 2),
            "realized_pnl": round(self.realized_pnl, 2),
            "total_equity": round(cash + invested + unrealized_pnl, 2),
            "open_positions": len(self.get_open_trades()),
            "closed_positions": len(self.get_closed_trades()),
        }
        self.performance_log.append(snap)
        self._save()

    def track_event(self, event_id: str, metadata: dict):
        self.events_tracked[event_id] = metadata
        self._save()

    def reset(self):
        self.trades = []
        self.events_tracked = {}
        self.performance_log = []
        self.realized_pnl = 0.0
        self._save()


def _append_simulation_log(action: str, strategy: str, data: dict):
    """Append to the cross-strategy simulation log (JSONL)."""
    log_path = os.path.join(DATA_DIR, "simulation_log.jsonl")
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    entry = {
        "timestamp": time.time(),
        "action": action,
        "strategy": strategy,
        **data,
    }
    try:
        with open(log_path, "a") as f:
            f.write(json.dumps(entry, default=str) + "\n")
    except Exception as e:
        print(f"[Log] Error appending to simulation log: {e}")

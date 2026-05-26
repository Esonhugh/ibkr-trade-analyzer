"""LifoAnalyzer — LIFO (Last In, First Out) lot matching for cost basis and P&L.

LIFO sells the most recently purchased shares first. Compared to FIFO:
  - In a rising market: LIFO realizes smaller gains (newer shares cost more)
  - In a falling market: LIFO realizes larger gains (newer shares cost less)
  - Remaining position cost basis reflects earliest purchases

This is one of the 7 matching methods available in IBKR's Tax Optimizer.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from ibkr_analyzer_lib.models import OpenPosition, Trade


@dataclass
class LifoLedger:
    """Per-symbol LIFO state."""

    symbol: str = ""
    asset_category: str = ""
    currency: str = "USD"
    quantity: float = 0.0
    cost_basis: float = 0.0  # weighted avg of remaining lots
    realized_pnl: float = 0.0
    total_commission: float = 0.0
    n_buys: int = 0
    n_sells: int = 0
    history: list[dict] = field(default_factory=list)


class LifoAnalyzer:
    """Compute per-symbol P&L using LIFO lot matching."""

    def __init__(self, trades: list[Trade], positions: list[OpenPosition] | None = None):
        self.trades = trades
        self.positions = positions or []
        self._ledgers: dict[str, LifoLedger] = {}
        self._compute()

    def _compute(self) -> None:
        """Process all trades with LIFO matching."""
        by_symbol: dict[str, list[Trade]] = defaultdict(list)
        for t in self.trades:
            if t.asset_category == "CASH":
                continue
            by_symbol[t.symbol].append(t)

        for symbol, sym_trades in by_symbol.items():
            sym_trades.sort(key=lambda t: t.date_time or datetime.min)
            ledger = LifoLedger(
                symbol=symbol,
                asset_category=sym_trades[0].asset_category if sym_trades else "",
                currency=sym_trades[0].currency if sym_trades else "USD",
            )

            # lots: list of [qty, price, multiplier] — pop from END for LIFO
            lots: list[list[float]] = []

            for t in sym_trades:
                qty = abs(t.quantity)
                price = t.trade_price
                comm = abs(t.commission)
                multiplier = t.multiplier or 1.0

                ledger.total_commission += comm

                if t.buy_sell in ("BUY", "BOT"):
                    lots.append([qty, price, multiplier])
                    ledger.quantity += qty
                    ledger.n_buys += 1

                elif t.buy_sell in ("SELL", "SLD"):
                    realized = 0.0
                    remaining = qty
                    # LIFO: match from the END (most recent lots first)
                    while remaining > 0 and lots:
                        lot = lots[-1]  # last lot = most recent
                        matched = min(remaining, lot[0])
                        realized += matched * (price - lot[1]) * multiplier
                        lot[0] -= matched
                        remaining -= matched
                        if lot[0] <= 1e-9:
                            lots.pop()  # remove exhausted lot from end
                    ledger.realized_pnl += realized
                    ledger.quantity -= qty
                    ledger.n_sells += 1

                # Compute current cost basis from remaining lots
                if lots:
                    total_qty = sum(l[0] for l in lots)
                    total_cost = sum(l[0] * l[1] for l in lots)
                    cost_basis = total_cost / total_qty if total_qty > 0 else 0.0
                else:
                    cost_basis = 0.0

                ledger.cost_basis = cost_basis

                ledger.history.append({
                    "date": t.date_time.strftime("%Y-%m-%d") if t.date_time else "",
                    "action": t.buy_sell,
                    "qty": qty,
                    "price": price,
                    "commission": comm,
                    "cost_basis_after": cost_basis,
                    "position_after": ledger.quantity,
                    "cumulative_pnl": ledger.realized_pnl,
                })

            self._ledgers[symbol] = ledger

    def summary(self) -> dict[str, Any]:
        """Return LIFO cost analysis summary."""
        if not self._ledgers:
            return {"total_symbols": 0}

        total_realized = sum(l.realized_pnl for l in self._ledgers.values())
        total_commission = sum(l.total_commission for l in self._ledgers.values())

        # Per-symbol details
        sorted_symbols = sorted(
            self._ledgers.values(),
            key=lambda l: abs(l.realized_pnl) + abs(l.quantity * l.cost_basis),
            reverse=True,
        )

        symbol_details = []
        for ledger in sorted_symbols[:20]:
            mark_price = 0.0
            for pos in self.positions:
                if pos.symbol == ledger.symbol:
                    mark_price = pos.mark_price
                    break

            unrealized = 0.0
            if ledger.quantity > 0 and mark_price > 0:
                sym_trades = [t for t in self.trades if t.symbol == ledger.symbol]
                multiplier = sym_trades[-1].multiplier or 1.0 if sym_trades else 1.0
                unrealized = (mark_price - ledger.cost_basis) * ledger.quantity * multiplier

            symbol_details.append({
                "symbol": ledger.symbol,
                "asset_category": ledger.asset_category,
                "current_qty": ledger.quantity,
                "lifo_cost_basis": ledger.cost_basis,
                "realized_pnl_lifo": ledger.realized_pnl,
                "unrealized_pnl_lifo": unrealized,
                "total_return_lifo": ledger.realized_pnl + unrealized,
                "n_buys": ledger.n_buys,
                "n_sells": ledger.n_sells,
                "total_commission": ledger.total_commission,
            })

        return {
            "total_symbols": len(self._ledgers),
            "total_realized_pnl_lifo": total_realized,
            "total_commission": total_commission,
            "symbol_details": symbol_details,
        }

    def get_symbol_history(self, symbol: str) -> list[dict]:
        """Get trade-by-trade LIFO cost evolution for a symbol."""
        ledger = self._ledgers.get(symbol)
        if not ledger:
            return []
        return ledger.history

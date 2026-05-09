"""DilutedCostAnalyzer — 摊薄成本价/保本价 (Breakeven Price) analysis.

Follows the Futu/Moomoo convention:
  成本价 = (持有期内买入总金额 - 持有期内卖出总金额) / 持有数量

Key behaviors:
  - BUY:  cost = (prev_cost * prev_qty + buy_amount) / new_qty
  - SELL: cost = (prev_cost * prev_qty - sell_amount) / remaining_qty
          Selling at a profit REDUCES the breakeven cost of remaining shares.
  - Commission is tracked separately, NOT folded into cost price (matching Futu).
  - When position clears to 0, record total P&L and reset for next holding period.

This differs from FIFO and weighted-average methods:
  - FIFO: matches earliest lots, cost per share varies by lot
  - Weighted average: sells don't change avg cost
  - Breakeven (this): sells reduce/increase remaining cost — reflects true breakeven point
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from models import OpenPosition, Trade


@dataclass
class PositionLedger:
    """Running state for a single symbol under breakeven cost method."""

    symbol: str = ""
    asset_category: str = ""
    currency: str = "USD"
    quantity: float = 0.0
    breakeven_cost: float = 0.0  # per-share breakeven (保本价)
    # Tracking accumulators (within current holding period)
    cum_buy_amount: float = 0.0  # total buy notional in current holding period
    cum_sell_amount: float = 0.0  # total sell notional in current holding period
    # Lifetime stats
    realized_pnl: float = 0.0  # total realized P&L (from cleared holding periods)
    n_buys: int = 0
    n_sells: int = 0
    total_buy_amount: float = 0.0  # lifetime total
    total_sell_amount: float = 0.0  # lifetime total
    total_commission: float = 0.0
    history: list[dict] = field(default_factory=list)  # chronological snapshots


class DilutedCostAnalyzer:
    """Compute per-symbol breakeven cost (摊薄成本价/保本价) and compare with FIFO."""

    def __init__(self, trades: list[Trade], positions: list[OpenPosition] | None = None):
        self.trades = trades
        self.positions = positions or []
        self._ledgers: dict[str, PositionLedger] = {}
        self._compute()

    def _compute(self) -> None:
        """Process all trades chronologically to build breakeven cost ledgers."""
        by_symbol: dict[str, list[Trade]] = defaultdict(list)
        for t in self.trades:
            if t.asset_category == "CASH":
                continue  # skip FX trades
            by_symbol[t.symbol].append(t)

        for symbol, sym_trades in by_symbol.items():
            sym_trades.sort(key=lambda t: t.date_time or datetime.min)
            ledger = PositionLedger(
                symbol=symbol,
                asset_category=sym_trades[0].asset_category if sym_trades else "",
                currency=sym_trades[0].currency if sym_trades else "USD",
            )

            for t in sym_trades:
                qty = abs(t.quantity)
                price = t.trade_price
                comm = abs(t.commission)
                multiplier = t.multiplier or 1.0
                notional = qty * price * multiplier

                ledger.total_commission += comm

                if t.buy_sell in ("BUY", "BOT"):
                    # Breakeven: new_cost = (old_cost * old_qty + buy_amount) / new_qty
                    new_qty = ledger.quantity + qty
                    if new_qty > 0:
                        old_total = ledger.breakeven_cost * ledger.quantity * multiplier
                        ledger.breakeven_cost = (old_total + notional) / (new_qty * multiplier)
                    else:
                        ledger.breakeven_cost = price

                    ledger.quantity = new_qty
                    ledger.cum_buy_amount += notional
                    ledger.n_buys += 1
                    ledger.total_buy_amount += notional

                elif t.buy_sell in ("SELL", "SLD"):
                    # Breakeven: new_cost = (old_cost * old_qty - sell_amount) / remaining_qty
                    # Selling at profit → cost goes DOWN (remaining shares are cheaper to break even)
                    # Selling at loss  → cost goes UP (need remaining shares to recover more)
                    remaining = ledger.quantity - qty

                    if remaining > 0:
                        old_total = ledger.breakeven_cost * ledger.quantity * multiplier
                        ledger.breakeven_cost = (old_total - notional) / (remaining * multiplier)
                        ledger.quantity = remaining
                        ledger.cum_sell_amount += notional
                    elif remaining == 0:
                        # Position fully closed — record realized P&L for this holding period
                        period_pnl = ledger.cum_sell_amount + notional - ledger.cum_buy_amount
                        ledger.realized_pnl += period_pnl
                        # Reset for next holding period
                        ledger.quantity = 0
                        ledger.breakeven_cost = 0.0
                        ledger.cum_buy_amount = 0.0
                        ledger.cum_sell_amount = 0.0
                    else:
                        # Oversold (shouldn't happen in normal long-only, but handle gracefully)
                        period_pnl = ledger.cum_sell_amount + notional - ledger.cum_buy_amount
                        ledger.realized_pnl += period_pnl
                        ledger.quantity = remaining  # negative = short
                        ledger.breakeven_cost = price
                        ledger.cum_buy_amount = 0.0
                        ledger.cum_sell_amount = 0.0

                    ledger.n_sells += 1
                    ledger.total_sell_amount += notional

                # Record snapshot after every trade
                ledger.history.append({
                    "date": t.date_time.strftime("%Y-%m-%d") if t.date_time else "",
                    "action": t.buy_sell,
                    "qty": qty,
                    "price": price,
                    "commission": comm,
                    "breakeven_after": ledger.breakeven_cost,
                    "position_after": ledger.quantity,
                    "cumulative_pnl": ledger.realized_pnl,
                })

            self._ledgers[symbol] = ledger

    def summary(self) -> dict[str, Any]:
        """Return breakeven cost analysis summary."""
        if not self._ledgers:
            return {"total_symbols": 0}

        # For active positions, unrealized P&L = (mark - breakeven) * qty
        # Total "realized" includes only fully-closed holding periods
        total_realized = sum(l.realized_pnl for l in self._ledgers.values())
        total_commission = sum(l.total_commission for l in self._ledgers.values())

        # FIFO comparison (from trade-level data)
        fifo_realized = sum(
            t.realized_pnl for t in self.trades
            if t.realized_pnl != 0 and t.asset_category != "CASH"
        )

        # Per-symbol breakdown
        sorted_symbols = sorted(
            self._ledgers.values(),
            key=lambda l: abs(l.realized_pnl) + abs(l.quantity * l.breakeven_cost),
            reverse=True,
        )

        symbol_details = []
        for ledger in sorted_symbols[:20]:
            # Find matching open position for mark price
            mark_price = 0.0
            fifo_cost = 0.0
            for pos in self.positions:
                if pos.symbol == ledger.symbol:
                    mark_price = pos.mark_price
                    fifo_cost = pos.cost_basis_price
                    break

            unrealized = 0.0
            multiplier = 1.0
            if ledger.quantity > 0:
                sym_trades = [t for t in self.trades if t.symbol == ledger.symbol]
                if sym_trades:
                    multiplier = sym_trades[-1].multiplier or 1.0
                if mark_price > 0:
                    unrealized = (mark_price - ledger.breakeven_cost) * ledger.quantity * multiplier

            detail: dict[str, Any] = {
                "symbol": ledger.symbol,
                "asset_category": ledger.asset_category,
                "current_qty": ledger.quantity,
                "diluted_avg_cost": ledger.breakeven_cost,
                "realized_pnl_diluted": ledger.realized_pnl,
                "unrealized_pnl_diluted": unrealized,
                "total_return_diluted": ledger.realized_pnl + unrealized,
                "n_buys": ledger.n_buys,
                "n_sells": ledger.n_sells,
                "total_commission": ledger.total_commission,
            }
            if fifo_cost > 0:
                detail["fifo_cost_basis"] = fifo_cost
                detail["cost_diff"] = ledger.breakeven_cost - fifo_cost
                detail["cost_diff_pct"] = (
                    (ledger.breakeven_cost - fifo_cost) / fifo_cost * 100 if fifo_cost else 0
                )
            if mark_price > 0:
                detail["mark_price"] = mark_price
                detail["pnl_pct"] = (
                    (mark_price - ledger.breakeven_cost) / ledger.breakeven_cost * 100
                    if ledger.breakeven_cost > 0 else 0
                )
            symbol_details.append(detail)

        # Active positions (qty > 0)
        active_positions = [
            {
                "symbol": l.symbol,
                "quantity": l.quantity,
                "avg_cost": l.breakeven_cost,
                "total_cost": l.quantity * l.breakeven_cost,
                "n_buys": l.n_buys,
                "n_sells": l.n_sells,
            }
            for l in sorted_symbols if l.quantity > 0
        ]

        return {
            "total_symbols": len(self._ledgers),
            "total_realized_pnl_diluted": total_realized,
            "total_realized_pnl_fifo": fifo_realized,
            "pnl_method_diff": total_realized - fifo_realized,
            "pnl_method_diff_pct": (
                (total_realized - fifo_realized) / abs(fifo_realized) * 100
                if fifo_realized != 0 else 0
            ),
            "total_commission_in_cost": total_commission,
            "active_positions": len(active_positions),
            "symbol_details": symbol_details,
            "active_position_details": sorted(
                active_positions, key=lambda x: x["total_cost"], reverse=True
            )[:15],
        }

    def get_symbol_history(self, symbol: str) -> list[dict]:
        """Get trade-by-trade breakeven cost evolution for a symbol."""
        ledger = self._ledgers.get(symbol)
        if not ledger:
            return []
        return ledger.history

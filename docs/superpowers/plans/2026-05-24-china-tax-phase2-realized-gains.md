# China Tax Phase 2 Realized Gains Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add opt-in Phase 2 China tax support for realized stock gains with IBKR realized P&L as the primary tax-estimate口径 and FIFO/diluted口径 as evidence comparisons.

**Architecture:** Extend the existing `ChinaTaxAnalyzer` so dividends and realized stock gains remain in one annual China tax report. Keep Phase 2 opt-in with `include_realized_pnl=False` by default. Add a small internal FIFO helper in `china_tax.py`; reuse `DilutedCostAnalyzer` for diluted/breakeven comparison.

**Tech Stack:** Python dataclasses, existing IBKR `models.py`, existing `DilutedCostAnalyzer`, pytest, MCP server tool schema in `server/ibkr_mcp_server.py`.

---

## File Structure

- Modify `skills/ibkr-trade-analyzer/scripts/analyzers/china_tax.py`
  - Extend `ChinaTaxConfig`.
  - Add realized gain collection, FIFO comparison, diluted comparison, property-transfer estimate, and review-required output.
  - Extend Markdown/CSV output.
- Modify `server/ibkr_mcp_server.py`
  - Add MCP schema parameters for Phase 2.
  - Pass Phase 2 parameters into `ChinaTaxConfig`.
- Modify `server/test_china_tax_analyzer.py`
  - Add unit tests for Phase 2 calculation, comparison, review-required behavior, and Phase 1 compatibility.
- Modify `server/test_china_tax_mcp.py`
  - Add MCP schema and tool-return tests for `include_realized_pnl=True`.

## Verification Command

Use this command after each task that changes code:

```bash
uv run --python 3.14 --with pytest --with mcp --with plotly --with pandas --with numpy --with requests python -m pytest "/Users/esonhugh/workspace/projects/WebStormProjects/cc/self-marketplace/ibkr-trade-analyzer/server/test_china_tax_analyzer.py" "/Users/esonhugh/workspace/projects/WebStormProjects/cc/self-marketplace/ibkr-trade-analyzer/server/test_china_tax_mcp.py"
```

Expected after final task: all tests in both files pass.

---

### Task 1: Add Phase 2 config and preserve Phase 1 default output

**Files:**
- Modify: `server/test_china_tax_analyzer.py`
- Modify: `skills/ibkr-trade-analyzer/scripts/analyzers/china_tax.py`

- [ ] **Step 1: Write failing tests for config defaults and Phase 1 compatibility**

Append this test to `server/test_china_tax_analyzer.py`:

```python
def test_realized_pnl_disabled_by_default_preserves_phase1_output_shape():
    result = ChinaTaxAnalyzer(_sample_data(), ChinaTaxConfig(tax_year=2025)).summary()

    assert "property_transfer_income_estimate" not in result
    assert "realized_pnl_comparison" not in result
    assert "review_required" not in result


def test_realized_pnl_config_defaults_to_stock_ibkr_primary_method():
    config = ChinaTaxConfig(tax_year=2025, include_realized_pnl=True)

    assert config.china_iit_property_transfer_rate == 0.20
    assert config.realized_pnl_asset_types == ("STK",)
    assert config.realized_pnl_primary_method == "ibkr"
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
uv run --python 3.14 --with pytest python -m pytest "/Users/esonhugh/workspace/projects/WebStormProjects/cc/self-marketplace/ibkr-trade-analyzer/server/test_china_tax_analyzer.py::test_realized_pnl_config_defaults_to_stock_ibkr_primary_method" -q
```

Expected: FAIL with `TypeError` for unexpected `include_realized_pnl` or `AttributeError` for missing config fields.

- [ ] **Step 3: Extend `ChinaTaxConfig` minimally**

In `skills/ibkr-trade-analyzer/scripts/analyzers/china_tax.py`, change the dataclass to:

```python
@dataclass(frozen=True)
class ChinaTaxConfig:
    tax_year: int
    resident_country: str = "CN"
    china_iit_dividend_rate: float = 0.20
    china_iit_property_transfer_rate: float = 0.20
    include_realized_pnl: bool = False
    realized_pnl_asset_types: tuple[str, ...] = ("STK",)
    realized_pnl_primary_method: str = "ibkr"
    fx_mode: str = "ibkr_evidence"
    dividend_country: str = "US"
```

Do not add Phase 2 output yet.

- [ ] **Step 4: Run tests and verify GREEN for config/default behavior**

Run:

```bash
uv run --python 3.14 --with pytest python -m pytest "/Users/esonhugh/workspace/projects/WebStormProjects/cc/self-marketplace/ibkr-trade-analyzer/server/test_china_tax_analyzer.py::test_realized_pnl_disabled_by_default_preserves_phase1_output_shape" "/Users/esonhugh/workspace/projects/WebStormProjects/cc/self-marketplace/ibkr-trade-analyzer/server/test_china_tax_analyzer.py::test_realized_pnl_config_defaults_to_stock_ibkr_primary_method" -q
```

Expected: both tests PASS.

- [ ] **Step 5: Commit**

```bash
git -C "/Users/esonhugh/workspace/projects/WebStormProjects/cc/self-marketplace/ibkr-trade-analyzer" add server/test_china_tax_analyzer.py skills/ibkr-trade-analyzer/scripts/analyzers/china_tax.py
git -C "/Users/esonhugh/workspace/projects/WebStormProjects/cc/self-marketplace/ibkr-trade-analyzer" commit -m "test: add china tax phase 2 config defaults"
```

---

### Task 2: Add IBKR realized P&L property-transfer estimate

**Files:**
- Modify: `server/test_china_tax_analyzer.py`
- Modify: `skills/ibkr-trade-analyzer/scripts/analyzers/china_tax.py`

- [ ] **Step 1: Add test helper for Phase 2 stock data**

Append this helper to `server/test_china_tax_analyzer.py` after `_sample_data()`:

```python
def _sample_realized_gain_data(realized_pnl: float = 100.0, asset_category: str = "STK") -> AccountData:
    data = _sample_data()
    data.cash_transactions = []
    data.trades.extend([
        Trade(
            asset_category=asset_category,
            symbol="AAPL",
            currency="USD",
            date_time=datetime(2025, 2, 1, 10, 0),
            quantity=10,
            trade_price=90,
            proceeds=-900,
            commission=-1,
            realized_pnl=0,
            buy_sell="BUY",
            multiplier=1,
        ),
        Trade(
            asset_category=asset_category,
            symbol="AAPL",
            currency="USD",
            date_time=datetime(2025, 3, 1, 10, 0),
            quantity=-10,
            trade_price=100,
            proceeds=1000,
            commission=-1,
            realized_pnl=realized_pnl,
            buy_sell="SELL",
            multiplier=1,
        ),
    ])
    return data
```

- [ ] **Step 2: Write failing realized-gain tax estimate test**

Append this test:

```python
def test_realized_stock_gain_uses_ibkr_pnl_as_property_transfer_candidate():
    data = _sample_realized_gain_data(realized_pnl=100)
    result = ChinaTaxAnalyzer(data, ChinaTaxConfig(tax_year=2025, include_realized_pnl=True)).summary()

    estimate = result["property_transfer_income_estimate"][0]
    assert estimate["country"] == "US"
    assert estimate["category"] == "property_transfer_income_candidate"
    assert estimate["currency"] == "USD"
    assert estimate["ibkr_realized_pnl_original"] == 100
    assert estimate["income_rmb"] == 700
    assert estimate["china_rate"] == 0.20
    assert estimate["china_tax_before_credit"] == 140
    assert estimate["foreign_tax_paid_rmb"] == 0
    assert estimate["estimated_tax_rmb"] == 140
```

- [ ] **Step 3: Run test and verify RED**

Run:

```bash
uv run --python 3.14 --with pytest python -m pytest "/Users/esonhugh/workspace/projects/WebStormProjects/cc/self-marketplace/ibkr-trade-analyzer/server/test_china_tax_analyzer.py::test_realized_stock_gain_uses_ibkr_pnl_as_property_transfer_candidate" -q
```

Expected: FAIL with missing `property_transfer_income_estimate`.

- [ ] **Step 4: Add minimal Phase 2 summary branch**

In `ChinaTaxAnalyzer.summary()`, after Phase 1 fields are assembled, build the result in a local variable and append Phase 2 fields only when enabled:

```python
        result = {
            "tax_year": self.config.tax_year,
            "status": "informational_estimate",
            "disclaimer": "Informational estimate and evidence organizer only; not tax filing advice.",
            "evidence_summary": evidence_rows,
            "china_iit_estimate": estimates,
            "treaty_sanity_check": treaty_rows,
            "fx_evidence": fx_evidence,
            "markdown": markdown,
            "csv_rows": {
                "evidence_summary": evidence_rows,
                "china_iit_estimate": estimates,
                "treaty_sanity_check": treaty_rows,
            },
        }
        if self.config.include_realized_pnl:
            phase2 = self._realized_pnl_summary(fx_rates)
            result.update(phase2)
            result["csv_rows"].update({
                "property_transfer_income_estimate": phase2["property_transfer_income_estimate"],
                "realized_pnl_comparison": phase2["realized_pnl_comparison"],
                "review_required": phase2["review_required"],
            })
        return result
```

Replace the existing direct `return { ... }` block with this structure.

- [ ] **Step 5: Add minimal `_realized_pnl_summary()` implementation**

Add this method inside `ChinaTaxAnalyzer` before `collect_dividend_items()`:

```python
    def _realized_pnl_summary(self, fx_rates: dict[str, float]) -> dict[str, Any]:
        stock_trades = [
            trade for trade in self.data.trades
            if trade.date_time
            and trade.date_time.year == self.config.tax_year
            and trade.asset_category in self.config.realized_pnl_asset_types
            and trade.asset_category == "STK"
        ]
        by_currency: dict[str, float] = {}
        for trade in stock_trades:
            if trade.realized_pnl == 0:
                continue
            by_currency[trade.currency] = by_currency.get(trade.currency, 0.0) + trade.realized_pnl

        estimates = []
        review_required = []
        for currency, pnl in sorted(by_currency.items()):
            if currency != "USD":
                review_required.append({
                    "area": "realized_pnl",
                    "reason": "non_usd_stock_realized_pnl",
                    "currency": currency,
                    "amount": self._round_money(pnl),
                })
                continue
            rate = fx_rates.get(currency)
            if rate is None:
                review_required.append({
                    "area": "realized_pnl",
                    "reason": "missing_rmb_fx_evidence",
                    "currency": currency,
                    "amount": self._round_money(pnl),
                })
                continue
            income_rmb = self._round_money(max(pnl * rate, 0))
            tax = self._round_money(income_rmb * self.config.china_iit_property_transfer_rate)
            estimates.append({
                "country": "US",
                "category": "property_transfer_income_candidate",
                "currency": currency,
                "ibkr_realized_pnl_original": self._round_money(pnl),
                "income_rmb": income_rmb,
                "china_rate": self.config.china_iit_property_transfer_rate,
                "china_tax_before_credit": tax,
                "foreign_tax_paid_rmb": 0,
                "estimated_tax_rmb": tax,
                "notes": "IBKR realized P&L primary evidence口径; informational estimate only",
            })
        return {
            "property_transfer_income_estimate": estimates,
            "realized_pnl_comparison": [],
            "review_required": review_required,
        }
```

- [ ] **Step 6: Run test and verify GREEN**

Run:

```bash
uv run --python 3.14 --with pytest python -m pytest "/Users/esonhugh/workspace/projects/WebStormProjects/cc/self-marketplace/ibkr-trade-analyzer/server/test_china_tax_analyzer.py::test_realized_stock_gain_uses_ibkr_pnl_as_property_transfer_candidate" -q
```

Expected: PASS.

- [ ] **Step 7: Run all analyzer tests**

Run:

```bash
uv run --python 3.14 --with pytest python -m pytest "/Users/esonhugh/workspace/projects/WebStormProjects/cc/self-marketplace/ibkr-trade-analyzer/server/test_china_tax_analyzer.py" -q
```

Expected: all tests PASS.

- [ ] **Step 8: Commit**

```bash
git -C "/Users/esonhugh/workspace/projects/WebStormProjects/cc/self-marketplace/ibkr-trade-analyzer" add server/test_china_tax_analyzer.py skills/ibkr-trade-analyzer/scripts/analyzers/china_tax.py
git -C "/Users/esonhugh/workspace/projects/WebStormProjects/cc/self-marketplace/ibkr-trade-analyzer" commit -m "feat: add china tax realized stock gain estimate"
```

---

### Task 3: Add realized loss and non-STK review-required handling

**Files:**
- Modify: `server/test_china_tax_analyzer.py`
- Modify: `skills/ibkr-trade-analyzer/scripts/analyzers/china_tax.py`

- [ ] **Step 1: Write failing tests**

Append these tests:

```python
def test_realized_stock_loss_has_zero_tax_and_review_item():
    data = _sample_realized_gain_data(realized_pnl=-50)
    result = ChinaTaxAnalyzer(data, ChinaTaxConfig(tax_year=2025, include_realized_pnl=True)).summary()

    estimate = result["property_transfer_income_estimate"][0]
    assert estimate["ibkr_realized_pnl_original"] == -50
    assert estimate["income_rmb"] == 0
    assert estimate["estimated_tax_rmb"] == 0
    assert any(item["reason"] == "realized_loss_treatment_requires_review" for item in result["review_required"])


def test_non_stock_realized_pnl_is_review_required_not_auto_taxed():
    data = _sample_realized_gain_data(realized_pnl=100, asset_category="OPT")
    result = ChinaTaxAnalyzer(data, ChinaTaxConfig(tax_year=2025, include_realized_pnl=True)).summary()

    assert result["property_transfer_income_estimate"] == []
    assert any(item["reason"] == "non_stock_realized_pnl" for item in result["review_required"])
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
uv run --python 3.14 --with pytest python -m pytest "/Users/esonhugh/workspace/projects/WebStormProjects/cc/self-marketplace/ibkr-trade-analyzer/server/test_china_tax_analyzer.py::test_realized_stock_loss_has_zero_tax_and_review_item" "/Users/esonhugh/workspace/projects/WebStormProjects/cc/self-marketplace/ibkr-trade-analyzer/server/test_china_tax_analyzer.py::test_non_stock_realized_pnl_is_review_required_not_auto_taxed" -q
```

Expected: FAIL because review-required entries are missing.

- [ ] **Step 3: Add loss and non-STK review collection**

At the start of `_realized_pnl_summary()`, add non-STK realized P&L review entries:

```python
        review_required = []
        for trade in self.data.trades:
            if not trade.date_time or trade.date_time.year != self.config.tax_year:
                continue
            if trade.asset_category == "CASH" or trade.realized_pnl == 0:
                continue
            if trade.asset_category not in self.config.realized_pnl_asset_types:
                review_required.append({
                    "area": "realized_pnl",
                    "reason": "non_stock_realized_pnl",
                    "asset_category": trade.asset_category,
                    "symbol": trade.symbol,
                    "currency": trade.currency,
                    "amount": self._round_money(trade.realized_pnl),
                })
```

Then remove the later `review_required = []` line from the method.

Inside the USD estimate branch, after creating the estimate for each currency, add:

```python
            if pnl < 0:
                review_required.append({
                    "area": "realized_pnl",
                    "reason": "realized_loss_treatment_requires_review",
                    "currency": currency,
                    "amount": self._round_money(pnl),
                    "notes": "Losses are preserved for review and not automatically offset against dividends or other income.",
                })
```

- [ ] **Step 4: Run tests and verify GREEN**

Run:

```bash
uv run --python 3.14 --with pytest python -m pytest "/Users/esonhugh/workspace/projects/WebStormProjects/cc/self-marketplace/ibkr-trade-analyzer/server/test_china_tax_analyzer.py::test_realized_stock_loss_has_zero_tax_and_review_item" "/Users/esonhugh/workspace/projects/WebStormProjects/cc/self-marketplace/ibkr-trade-analyzer/server/test_china_tax_analyzer.py::test_non_stock_realized_pnl_is_review_required_not_auto_taxed" -q
```

Expected: both tests PASS.

- [ ] **Step 5: Run all analyzer tests**

Run:

```bash
uv run --python 3.14 --with pytest python -m pytest "/Users/esonhugh/workspace/projects/WebStormProjects/cc/self-marketplace/ibkr-trade-analyzer/server/test_china_tax_analyzer.py" -q
```

Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git -C "/Users/esonhugh/workspace/projects/WebStormProjects/cc/self-marketplace/ibkr-trade-analyzer" add server/test_china_tax_analyzer.py skills/ibkr-trade-analyzer/scripts/analyzers/china_tax.py
git -C "/Users/esonhugh/workspace/projects/WebStormProjects/cc/self-marketplace/ibkr-trade-analyzer" commit -m "feat: flag realized gain review items"
```

---

### Task 4: Add FIFO realized P&L comparison

**Files:**
- Modify: `server/test_china_tax_analyzer.py`
- Modify: `skills/ibkr-trade-analyzer/scripts/analyzers/china_tax.py`

- [ ] **Step 1: Write failing complete-FIFO comparison test**

Append this test:

```python
def test_realized_pnl_comparison_includes_complete_fifo_result():
    data = _sample_realized_gain_data(realized_pnl=100)
    result = ChinaTaxAnalyzer(data, ChinaTaxConfig(tax_year=2025, include_realized_pnl=True)).summary()

    comparison = result["realized_pnl_comparison"][0]
    assert comparison["symbol"] == "AAPL"
    assert comparison["currency"] == "USD"
    assert comparison["ibkr_realized_pnl"] == 100
    assert comparison["fifo_realized_pnl"] == 98
    assert comparison["fifo_status"] == "complete"
    assert comparison["difference_ibkr_vs_fifo"] == 2
```

The expected FIFO P&L is `1000 proceeds - 900 cost - 1 buy commission - 1 sell commission = 98`.

- [ ] **Step 2: Run test and verify RED**

Run:

```bash
uv run --python 3.14 --with pytest python -m pytest "/Users/esonhugh/workspace/projects/WebStormProjects/cc/self-marketplace/ibkr-trade-analyzer/server/test_china_tax_analyzer.py::test_realized_pnl_comparison_includes_complete_fifo_result" -q
```

Expected: FAIL because `realized_pnl_comparison` is empty.

- [ ] **Step 3: Add FIFO helper methods**

Add these methods inside `ChinaTaxAnalyzer`, before `_realized_pnl_summary()`:

```python
    def _fifo_realized_by_symbol(self, trades: list[Trade]) -> dict[str, dict[str, Any]]:
        by_symbol: dict[str, list[Trade]] = {}
        for trade in trades:
            by_symbol.setdefault(trade.symbol, []).append(trade)

        results: dict[str, dict[str, Any]] = {}
        for symbol, symbol_trades in by_symbol.items():
            lots: list[dict[str, float]] = []
            realized = 0.0
            status = "complete"
            currency = symbol_trades[0].currency if symbol_trades else ""
            for trade in sorted(symbol_trades, key=lambda t: t.date_time):
                qty = abs(trade.quantity)
                multiplier = trade.multiplier or 1.0
                commission = abs(trade.commission)
                if trade.buy_sell in ("BUY", "BOT"):
                    lots.append({
                        "quantity": qty,
                        "unit_cost": trade.trade_price * multiplier,
                        "commission_remaining": commission,
                    })
                elif trade.buy_sell in ("SELL", "SLD"):
                    remaining = qty
                    matched_cost = 0.0
                    matched_buy_commission = 0.0
                    while remaining > 1e-9 and lots:
                        lot = lots[0]
                        matched_qty = min(remaining, lot["quantity"])
                        ratio = matched_qty / lot["quantity"] if lot["quantity"] else 0
                        matched_cost += matched_qty * lot["unit_cost"]
                        matched_buy_commission += lot["commission_remaining"] * ratio
                        lot["quantity"] -= matched_qty
                        lot["commission_remaining"] -= lot["commission_remaining"] * ratio
                        remaining -= matched_qty
                        if lot["quantity"] <= 1e-9:
                            lots.pop(0)
                    if remaining > 1e-9:
                        status = "incomplete"
                    sell_proceeds = abs(trade.proceeds) if trade.proceeds else qty * trade.trade_price * multiplier
                    realized += sell_proceeds - matched_cost - matched_buy_commission - commission
            results[symbol] = {
                "symbol": symbol,
                "currency": currency,
                "fifo_realized_pnl": self._round_money(realized),
                "fifo_status": status,
            }
        return results
```

- [ ] **Step 4: Add comparison rows to `_realized_pnl_summary()`**

In `_realized_pnl_summary()`, after `stock_trades` is defined, add:

```python
        fifo_by_symbol = self._fifo_realized_by_symbol(stock_trades)
        ibkr_by_symbol: dict[str, dict[str, Any]] = {}
        for trade in stock_trades:
            entry = ibkr_by_symbol.setdefault(trade.symbol, {
                "symbol": trade.symbol,
                "currency": trade.currency,
                "ibkr_realized_pnl": 0.0,
            })
            entry["ibkr_realized_pnl"] += trade.realized_pnl

        comparison = []
        for symbol, ibkr_entry in sorted(ibkr_by_symbol.items()):
            fifo_entry = fifo_by_symbol.get(symbol, {"fifo_realized_pnl": 0.0, "fifo_status": "incomplete"})
            ibkr_pnl = self._round_money(ibkr_entry["ibkr_realized_pnl"])
            fifo_pnl = self._round_money(fifo_entry["fifo_realized_pnl"])
            comparison.append({
                "symbol": symbol,
                "currency": ibkr_entry["currency"],
                "ibkr_realized_pnl": ibkr_pnl,
                "fifo_realized_pnl": fifo_pnl,
                "fifo_status": fifo_entry["fifo_status"],
                "diluted_realized_pnl": 0.0,
                "difference_ibkr_vs_fifo": self._round_money(ibkr_pnl - fifo_pnl),
                "difference_ibkr_vs_diluted": ibkr_pnl,
                "notes": "FIFO comparison rebuilt from available Flex trades",
            })
```

Change the return value at the end of `_realized_pnl_summary()` from:

```python
            "realized_pnl_comparison": [],
```

to:

```python
            "realized_pnl_comparison": comparison,
```

- [ ] **Step 5: Add FIFO incomplete review item**

After building each comparison row, add:

```python
            if fifo_entry["fifo_status"] == "incomplete":
                review_required.append({
                    "area": "realized_pnl",
                    "reason": "fifo_lot_history_incomplete",
                    "symbol": symbol,
                    "currency": ibkr_entry["currency"],
                    "notes": "Available Flex trades do not fully reconstruct FIFO lots for this symbol.",
                })
```

- [ ] **Step 6: Run test and verify GREEN**

Run:

```bash
uv run --python 3.14 --with pytest python -m pytest "/Users/esonhugh/workspace/projects/WebStormProjects/cc/self-marketplace/ibkr-trade-analyzer/server/test_china_tax_analyzer.py::test_realized_pnl_comparison_includes_complete_fifo_result" -q
```

Expected: PASS.

- [ ] **Step 7: Run all analyzer tests**

Run:

```bash
uv run --python 3.14 --with pytest python -m pytest "/Users/esonhugh/workspace/projects/WebStormProjects/cc/self-marketplace/ibkr-trade-analyzer/server/test_china_tax_analyzer.py" -q
```

Expected: all tests PASS.

- [ ] **Step 8: Commit**

```bash
git -C "/Users/esonhugh/workspace/projects/WebStormProjects/cc/self-marketplace/ibkr-trade-analyzer" add server/test_china_tax_analyzer.py skills/ibkr-trade-analyzer/scripts/analyzers/china_tax.py
git -C "/Users/esonhugh/workspace/projects/WebStormProjects/cc/self-marketplace/ibkr-trade-analyzer" commit -m "feat: add fifo realized pnl comparison"
```

---

### Task 5: Add missing historical lot test and review-required behavior

**Files:**
- Modify: `server/test_china_tax_analyzer.py`
- Modify: `skills/ibkr-trade-analyzer/scripts/analyzers/china_tax.py`

- [ ] **Step 1: Write failing missing-lot test**

Append this test:

```python
def test_missing_fifo_lot_marks_comparison_incomplete():
    data = _sample_data()
    data.cash_transactions = []
    data.trades.append(
        Trade(
            asset_category="STK",
            symbol="MSFT",
            currency="USD",
            date_time=datetime(2025, 3, 1, 10, 0),
            quantity=-5,
            trade_price=100,
            proceeds=500,
            commission=-1,
            realized_pnl=50,
            buy_sell="SELL",
            multiplier=1,
        )
    )

    result = ChinaTaxAnalyzer(data, ChinaTaxConfig(tax_year=2025, include_realized_pnl=True)).summary()

    comparison = result["realized_pnl_comparison"][0]
    assert comparison["symbol"] == "MSFT"
    assert comparison["fifo_status"] == "incomplete"
    assert any(item["reason"] == "fifo_lot_history_incomplete" for item in result["review_required"])
```

- [ ] **Step 2: Run test and verify RED or GREEN**

Run:

```bash
uv run --python 3.14 --with pytest python -m pytest "/Users/esonhugh/workspace/projects/WebStormProjects/cc/self-marketplace/ibkr-trade-analyzer/server/test_china_tax_analyzer.py::test_missing_fifo_lot_marks_comparison_incomplete" -q
```

Expected before Task 4 implementation: FAIL. Expected after Task 4 implementation: PASS. If it passes, do not change production code.

- [ ] **Step 3: If needed, add missing-lot review behavior**

Only if the test fails, ensure Task 4 Step 5 code exists in `_realized_pnl_summary()`:

```python
            if fifo_entry["fifo_status"] == "incomplete":
                review_required.append({
                    "area": "realized_pnl",
                    "reason": "fifo_lot_history_incomplete",
                    "symbol": symbol,
                    "currency": ibkr_entry["currency"],
                    "notes": "Available Flex trades do not fully reconstruct FIFO lots for this symbol.",
                })
```

- [ ] **Step 4: Run test and verify GREEN**

Run:

```bash
uv run --python 3.14 --with pytest python -m pytest "/Users/esonhugh/workspace/projects/WebStormProjects/cc/self-marketplace/ibkr-trade-analyzer/server/test_china_tax_analyzer.py::test_missing_fifo_lot_marks_comparison_incomplete" -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git -C "/Users/esonhugh/workspace/projects/WebStormProjects/cc/self-marketplace/ibkr-trade-analyzer" add server/test_china_tax_analyzer.py skills/ibkr-trade-analyzer/scripts/analyzers/china_tax.py
git -C "/Users/esonhugh/workspace/projects/WebStormProjects/cc/self-marketplace/ibkr-trade-analyzer" commit -m "test: cover incomplete fifo lot history"
```

---

### Task 6: Add diluted/breakeven comparison

**Files:**
- Modify: `server/test_china_tax_analyzer.py`
- Modify: `skills/ibkr-trade-analyzer/scripts/analyzers/china_tax.py`

- [ ] **Step 1: Write failing diluted comparison test**

Append this test:

```python
def test_realized_pnl_comparison_includes_diluted_result():
    data = _sample_realized_gain_data(realized_pnl=100)
    result = ChinaTaxAnalyzer(data, ChinaTaxConfig(tax_year=2025, include_realized_pnl=True)).summary()

    comparison = result["realized_pnl_comparison"][0]
    assert comparison["diluted_realized_pnl"] == 100
    assert comparison["difference_ibkr_vs_diluted"] == 0
```

- [ ] **Step 2: Run test and verify RED**

Run:

```bash
uv run --python 3.14 --with pytest python -m pytest "/Users/esonhugh/workspace/projects/WebStormProjects/cc/self-marketplace/ibkr-trade-analyzer/server/test_china_tax_analyzer.py::test_realized_pnl_comparison_includes_diluted_result" -q
```

Expected: FAIL because `diluted_realized_pnl` is still 0.

- [ ] **Step 3: Import `DilutedCostAnalyzer`**

At the top of `china_tax.py`, below model imports, add:

```python
from analyzers.diluted_cost import DilutedCostAnalyzer
```

If that import creates package import issues when tests run, use a local import inside `_realized_pnl_summary()`:

```python
from analyzers.diluted_cost import DilutedCostAnalyzer
```

- [ ] **Step 4: Add diluted lookup inside `_realized_pnl_summary()`**

After `fifo_by_symbol = ...`, add:

```python
        diluted_summary = DilutedCostAnalyzer(stock_trades).summary()
        diluted_by_symbol = {
            item["symbol"]: item
            for item in diluted_summary.get("symbol_details", [])
        }
```

When building each comparison row, replace:

```python
                "diluted_realized_pnl": 0.0,
                "difference_ibkr_vs_diluted": ibkr_pnl,
```

with:

```python
            diluted_pnl = self._round_money(diluted_by_symbol.get(symbol, {}).get("realized_pnl_diluted", 0.0))
```

and use:

```python
                "diluted_realized_pnl": diluted_pnl,
                "difference_ibkr_vs_diluted": self._round_money(ibkr_pnl - diluted_pnl),
```

- [ ] **Step 5: Run test and verify GREEN**

Run:

```bash
uv run --python 3.14 --with pytest python -m pytest "/Users/esonhugh/workspace/projects/WebStormProjects/cc/self-marketplace/ibkr-trade-analyzer/server/test_china_tax_analyzer.py::test_realized_pnl_comparison_includes_diluted_result" -q
```

Expected: PASS.

- [ ] **Step 6: Run all analyzer tests**

Run:

```bash
uv run --python 3.14 --with pytest python -m pytest "/Users/esonhugh/workspace/projects/WebStormProjects/cc/self-marketplace/ibkr-trade-analyzer/server/test_china_tax_analyzer.py" -q
```

Expected: all tests PASS.

- [ ] **Step 7: Commit**

```bash
git -C "/Users/esonhugh/workspace/projects/WebStormProjects/cc/self-marketplace/ibkr-trade-analyzer" add server/test_china_tax_analyzer.py skills/ibkr-trade-analyzer/scripts/analyzers/china_tax.py
git -C "/Users/esonhugh/workspace/projects/WebStormProjects/cc/self-marketplace/ibkr-trade-analyzer" commit -m "feat: add diluted realized pnl comparison"
```

---

### Task 7: Extend Markdown and CSV rows for Phase 2

**Files:**
- Modify: `server/test_china_tax_analyzer.py`
- Modify: `skills/ibkr-trade-analyzer/scripts/analyzers/china_tax.py`

- [ ] **Step 1: Write failing output test**

Append this test:

```python
def test_phase2_markdown_and_csv_include_realized_gain_sections():
    data = _sample_realized_gain_data(realized_pnl=100)
    result = ChinaTaxAnalyzer(data, ChinaTaxConfig(tax_year=2025, include_realized_pnl=True)).summary()

    assert "## Property Transfer Income Estimate" in result["markdown"]
    assert "## Realized P&L Comparison" in result["markdown"]
    assert "property_transfer_income_estimate" in result["csv_rows"]
    assert "realized_pnl_comparison" in result["csv_rows"]
    assert "review_required" in result["csv_rows"]
```

- [ ] **Step 2: Run test and verify RED**

Run:

```bash
uv run --python 3.14 --with pytest python -m pytest "/Users/esonhugh/workspace/projects/WebStormProjects/cc/self-marketplace/ibkr-trade-analyzer/server/test_china_tax_analyzer.py::test_phase2_markdown_and_csv_include_realized_gain_sections" -q
```

Expected: FAIL because Markdown lacks Phase 2 section headings.

- [ ] **Step 3: Add Phase 2 Markdown builder**

Add this static method inside `ChinaTaxAnalyzer` after `build_markdown()`:

```python
    @staticmethod
    def append_realized_pnl_markdown(
        markdown: str,
        estimates: list[dict[str, Any]],
        comparison: list[dict[str, Any]],
        review_required: list[dict[str, Any]],
    ) -> str:
        lines = [markdown.rstrip(), "", "## Property Transfer Income Estimate", ""]
        lines += [
            "| Country | Category | Currency | IBKR Realized P&L | Income RMB | China Rate | Estimated Tax RMB | Notes |",
            "|---|---|---|---:|---:|---:|---:|---|",
        ]
        for row in estimates:
            lines.append(
                f"| {row['country']} | {row['category']} | {row['currency']} | "
                f"{row['ibkr_realized_pnl_original']:.2f} | {row['income_rmb']:.2f} | "
                f"{row['china_rate']:.2%} | {row['estimated_tax_rmb']:.2f} | {row['notes']} |"
            )
        lines += ["", "## Realized P&L Comparison", ""]
        lines += [
            "| Symbol | Currency | IBKR P&L | FIFO P&L | FIFO Status | Diluted P&L | IBKR-FIFO | IBKR-Diluted | Notes |",
            "|---|---|---:|---:|---|---:|---:|---:|---|",
        ]
        for row in comparison:
            lines.append(
                f"| {row['symbol']} | {row['currency']} | {row['ibkr_realized_pnl']:.2f} | "
                f"{row['fifo_realized_pnl']:.2f} | {row['fifo_status']} | "
                f"{row['diluted_realized_pnl']:.2f} | {row['difference_ibkr_vs_fifo']:.2f} | "
                f"{row['difference_ibkr_vs_diluted']:.2f} | {row['notes']} |"
            )
        lines += ["", "## Review Required", ""]
        lines += ["| Area | Reason | Symbol | Currency | Amount | Notes |", "|---|---|---|---|---:|---|"]
        for row in review_required:
            lines.append(
                f"| {row.get('area', '')} | {row.get('reason', '')} | {row.get('symbol', '')} | "
                f"{row.get('currency', '')} | {row.get('amount', 0):.2f} | {row.get('notes', '')} |"
            )
        return "\n".join(lines) + "\n"
```

- [ ] **Step 4: Call the Markdown appender in `summary()`**

Inside `if self.config.include_realized_pnl:`, after `phase2 = self._realized_pnl_summary(fx_rates)`, add:

```python
            result["markdown"] = self.append_realized_pnl_markdown(
                result["markdown"],
                phase2["property_transfer_income_estimate"],
                phase2["realized_pnl_comparison"],
                phase2["review_required"],
            )
```

Keep the existing `result.update(phase2)` and `csv_rows.update(...)` lines.

- [ ] **Step 5: Run test and verify GREEN**

Run:

```bash
uv run --python 3.14 --with pytest python -m pytest "/Users/esonhugh/workspace/projects/WebStormProjects/cc/self-marketplace/ibkr-trade-analyzer/server/test_china_tax_analyzer.py::test_phase2_markdown_and_csv_include_realized_gain_sections" -q
```

Expected: PASS.

- [ ] **Step 6: Run all analyzer tests**

Run:

```bash
uv run --python 3.14 --with pytest python -m pytest "/Users/esonhugh/workspace/projects/WebStormProjects/cc/self-marketplace/ibkr-trade-analyzer/server/test_china_tax_analyzer.py" -q
```

Expected: all tests PASS.

- [ ] **Step 7: Commit**

```bash
git -C "/Users/esonhugh/workspace/projects/WebStormProjects/cc/self-marketplace/ibkr-trade-analyzer" add server/test_china_tax_analyzer.py skills/ibkr-trade-analyzer/scripts/analyzers/china_tax.py
git -C "/Users/esonhugh/workspace/projects/WebStormProjects/cc/self-marketplace/ibkr-trade-analyzer" commit -m "feat: add realized gain report output"
```

---

### Task 8: Extend MCP schema and handler for Phase 2

**Files:**
- Modify: `server/test_china_tax_mcp.py`
- Modify: `server/ibkr_mcp_server.py`

- [ ] **Step 1: Write failing MCP schema and tool tests**

Append these tests to `server/test_china_tax_mcp.py`:

```python
def test_china_tax_tool_schema_exposes_realized_pnl_parameters():
    tools = {tool.name: tool for tool in run(srv.list_tools())}
    properties = tools["ibkr_china_tax_annual_calc"].inputSchema["properties"]

    assert "include_realized_pnl" in properties
    assert "realized_pnl_asset_types" in properties
    assert "china_iit_property_transfer_rate" in properties


def test_china_tax_tool_returns_phase2_fields_when_enabled():
    srv._session_data.trades.extend([
        Trade(
            asset_category="STK",
            symbol="AAPL",
            currency="USD",
            date_time=datetime(2025, 2, 1, 10, 0),
            quantity=10,
            trade_price=90,
            proceeds=-900,
            commission=-1,
            realized_pnl=0,
            buy_sell="BUY",
            multiplier=1,
        ),
        Trade(
            asset_category="STK",
            symbol="AAPL",
            currency="USD",
            date_time=datetime(2025, 3, 1, 10, 0),
            quantity=-10,
            trade_price=100,
            proceeds=1000,
            commission=-1,
            realized_pnl=100,
            buy_sell="SELL",
            multiplier=1,
        ),
    ])

    result = run(srv.call_tool("ibkr_china_tax_annual_calc", {
        "tax_year": 2025,
        "include_realized_pnl": True,
    }))
    data = parse_result(result)

    assert data["property_transfer_income_estimate"][0]["estimated_tax_rmb"] == 140
    assert data["realized_pnl_comparison"][0]["symbol"] == "AAPL"
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
uv run --python 3.14 --with pytest --with mcp --with plotly --with pandas --with numpy --with requests python -m pytest "/Users/esonhugh/workspace/projects/WebStormProjects/cc/self-marketplace/ibkr-trade-analyzer/server/test_china_tax_mcp.py::test_china_tax_tool_schema_exposes_realized_pnl_parameters" "/Users/esonhugh/workspace/projects/WebStormProjects/cc/self-marketplace/ibkr-trade-analyzer/server/test_china_tax_mcp.py::test_china_tax_tool_returns_phase2_fields_when_enabled" -q
```

Expected: FAIL because schema/config wiring is missing.

- [ ] **Step 3: Extend MCP tool schema**

In `server/ibkr_mcp_server.py`, inside the `ibkr_china_tax_annual_calc` `properties` dict, after `china_iit_dividend_rate`, add:

```python
                    "include_realized_pnl": {
                        "type": "boolean",
                        "description": "Include Phase 2 STK realized P&L property-transfer candidate estimate. Default: false",
                        "default": False,
                    },
                    "realized_pnl_asset_types": {
                        "type": "array",
                        "items": {"type": "string", "enum": ["STK"]},
                        "description": "Asset types for Phase 2 realized P&L. First implementation supports STK only.",
                        "default": ["STK"],
                    },
                    "china_iit_property_transfer_rate": {
                        "type": "number",
                        "description": "China IIT estimate rate for property transfer income candidates. Default: 0.20",
                        "default": 0.20,
                    },
```

- [ ] **Step 4: Pass Phase 2 args into `ChinaTaxConfig`**

In `_china_tax_summary()`, replace config creation with:

```python
    realized_asset_types = args.get("realized_pnl_asset_types", ["STK"])
    if isinstance(realized_asset_types, str):
        realized_asset_types = [realized_asset_types]
    config = ChinaTaxConfig(
        tax_year=int(tax_year),
        china_iit_dividend_rate=float(args.get("china_iit_dividend_rate", 0.20)),
        china_iit_property_transfer_rate=float(args.get("china_iit_property_transfer_rate", 0.20)),
        include_realized_pnl=bool(args.get("include_realized_pnl", False)),
        realized_pnl_asset_types=tuple(realized_asset_types),
    )
```

- [ ] **Step 5: Run MCP tests and verify GREEN**

Run:

```bash
uv run --python 3.14 --with pytest --with mcp --with plotly --with pandas --with numpy --with requests python -m pytest "/Users/esonhugh/workspace/projects/WebStormProjects/cc/self-marketplace/ibkr-trade-analyzer/server/test_china_tax_mcp.py::test_china_tax_tool_schema_exposes_realized_pnl_parameters" "/Users/esonhugh/workspace/projects/WebStormProjects/cc/self-marketplace/ibkr-trade-analyzer/server/test_china_tax_mcp.py::test_china_tax_tool_returns_phase2_fields_when_enabled" -q
```

Expected: PASS.

- [ ] **Step 6: Run focused suite**

Run:

```bash
uv run --python 3.14 --with pytest --with mcp --with plotly --with pandas --with numpy --with requests python -m pytest "/Users/esonhugh/workspace/projects/WebStormProjects/cc/self-marketplace/ibkr-trade-analyzer/server/test_china_tax_analyzer.py" "/Users/esonhugh/workspace/projects/WebStormProjects/cc/self-marketplace/ibkr-trade-analyzer/server/test_china_tax_mcp.py" -q
```

Expected: all tests PASS.

- [ ] **Step 7: Commit**

```bash
git -C "/Users/esonhugh/workspace/projects/WebStormProjects/cc/self-marketplace/ibkr-trade-analyzer" add server/test_china_tax_mcp.py server/ibkr_mcp_server.py
git -C "/Users/esonhugh/workspace/projects/WebStormProjects/cc/self-marketplace/ibkr-trade-analyzer" commit -m "feat: expose china tax realized gains via mcp"
```

---

### Task 9: Final verification and documentation update

**Files:**
- Modify: `skills/china-tax/SKILL.md`
- Modify: `skills/china-tax/references/official-tax-rules-and-implementation-plan.md`

- [ ] **Step 1: Update skill current capability**

In `skills/china-tax/SKILL.md`, update the automated tool capability sentence to include Phase 2:

```markdown
The automated `ibkr_china_tax_annual_calc` MCP tool uses IBKR Flex as the primary source for Phase 1 U.S. dividend/withholding estimates and opt-in Phase 2 STK realized-gain evidence. 1042-S is optional follow-up reconciliation/evidence check, not required input. Activity-statement reconciliation beyond loaded Flex cash transactions/trades, options, derivatives, complex corporate actions, cost-basis hazards, and non-USD dividends or gains remain manual/review-required.
```

- [ ] **Step 2: Update reference implementation status**

In `skills/china-tax/references/official-tax-rules-and-implementation-plan.md`, change line 5 from:

```markdown
Implementation status: research/reference and command workflows exist; deterministic annual calculator code is proposed but not implemented.
```

to:

```markdown
Implementation status: Phase 1 dividend/withholding calculator exists; Phase 2 STK realized-gain support is implemented as opt-in evidence/estimate workflow with IBKR realized P&L primary口径 and FIFO/diluted comparisons.
```

- [ ] **Step 3: Run final focused verification**

Run:

```bash
uv run --python 3.14 --with pytest --with mcp --with plotly --with pandas --with numpy --with requests python -m pytest "/Users/esonhugh/workspace/projects/WebStormProjects/cc/self-marketplace/ibkr-trade-analyzer/server/test_china_tax_analyzer.py" "/Users/esonhugh/workspace/projects/WebStormProjects/cc/self-marketplace/ibkr-trade-analyzer/server/test_china_tax_mcp.py" "/Users/esonhugh/workspace/projects/WebStormProjects/cc/self-marketplace/ibkr-trade-analyzer/server/test_mcp_server.py" "/Users/esonhugh/workspace/projects/WebStormProjects/cc/self-marketplace/ibkr-trade-analyzer/server/test_plugin_manifests.py::test_command_docs_exist"
```

Expected: all selected tests PASS.

- [ ] **Step 4: Check diagnostics**

Run IDE diagnostics or equivalent. Expected: no new diagnostics in `china_tax.py`, `ibkr_mcp_server.py`, or test files.

- [ ] **Step 5: Commit docs**

```bash
git -C "/Users/esonhugh/workspace/projects/WebStormProjects/cc/self-marketplace/ibkr-trade-analyzer" add skills/china-tax/SKILL.md skills/china-tax/references/official-tax-rules-and-implementation-plan.md docs/superpowers/specs/2026-05-24-china-tax-phase2-realized-gains-design.md docs/superpowers/plans/2026-05-24-china-tax-phase2-realized-gains.md
git -C "/Users/esonhugh/workspace/projects/WebStormProjects/cc/self-marketplace/ibkr-trade-analyzer" commit -m "docs: document china tax phase 2 realized gains"
```

---

## Self-Review Checklist

- Spec coverage: Tasks cover opt-in config, IBKR primary estimate, FIFO comparison, diluted comparison, review-required records, MCP schema/handler, Markdown/CSV output, and docs.
- Placeholder scan: No TBD/TODO/fill-in placeholders. All code snippets and commands are concrete.
- Type consistency: Uses `property_transfer_income_estimate`, `realized_pnl_comparison`, and `review_required` consistently across analyzer, MCP, tests, and docs.
- Scope control: Only STK is auto-processed. Non-STK and complex cases become review-required.

# China Tax Phase 2 Realized Stock Gains Design

## Scope

Phase 2 adds realized stock gain evidence and informational China IIT estimates to the existing China tax annual workflow. It only auto-processes IBKR Flex stock trades where `asset_category == "STK"`. FX trades, options, transfers, splits, exercise/assignment, and other complex events are not included in automatic tax calculation and must be surfaced as `review_required`.

The primary calculation source remains IBKR Flex. Form 1042-S is optional follow-up reconciliation/evidence check, not required input.

## Tax Calculation Positioning

The output is an informational estimate and evidence organizer, not final tax filing advice. The realized-gain section is labeled as `property_transfer_income_candidate`. The calculator must not state that the computed amount is final tax payable.

The main tax estimate uses IBKR Flex `realized_pnl` as the primary evidence口径. FIFO and diluted/breakeven calculations are comparison views for review, not the default filing conclusion.

## Data Flow

```text
IBKR Flex trades
  -> filter tax_year + STK
  -> aggregate IBKR realized_pnl by currency/symbol
  -> rebuild FIFO realized P&L where lots are complete
  -> reuse/extend diluted cost analysis for comparison
  -> translate supported USD realized P&L to RMB using auditable FX evidence
  -> calculate property-transfer candidate tax estimate
  -> emit Markdown + CSV rows + review_required items
```

## Configuration and MCP API

Extend `ChinaTaxConfig` with:

```python
china_iit_property_transfer_rate: float = 0.20
include_realized_pnl: bool = False
realized_pnl_asset_types: tuple[str, ...] = ("STK",)
realized_pnl_primary_method: str = "ibkr"
```

Extend `ibkr_china_tax_annual_calc` with:

```text
include_realized_pnl: boolean, default false
realized_pnl_asset_types: array/string, default ["STK"]
china_iit_property_transfer_rate: number, default 0.20
```

Default behavior remains Phase 1 only. The realized-gain section appears only when `include_realized_pnl=True`.

## Output Additions

Add these top-level fields to the China tax summary when Phase 2 is enabled:

```json
{
  "property_transfer_income_estimate": [...],
  "realized_pnl_comparison": [...],
  "review_required": [...]
}
```

### `property_transfer_income_estimate`

Grouped by country/category/currency. First implementation supports USD STK realized gains only.

Fields:

- `country`
- `category`: `property_transfer_income_candidate`
- `currency`
- `ibkr_realized_pnl_original`
- `income_rmb`
- `china_rate`
- `china_tax_before_credit`
- `foreign_tax_paid_rmb`: normally 0 for realized stock gains unless explicit evidence is later added
- `estimated_tax_rmb`
- `notes`

Taxable amount uses positive IBKR realized P&L only:

```text
property_transfer_income_rmb = max(ibkr_realized_pnl_original * rmb_rate, 0)
estimated_tax_rmb = property_transfer_income_rmb * china_iit_property_transfer_rate
```

Realized losses are not automatically netted against dividends or other income. They are preserved as review items.

### `realized_pnl_comparison`

Per symbol, compare:

- `ibkr_realized_pnl`
- `fifo_realized_pnl`
- `fifo_status`: `complete` or `incomplete`
- `diluted_realized_pnl`
- `difference_ibkr_vs_fifo`
- `difference_ibkr_vs_diluted`
- `currency`
- `notes`

### `review_required`

Include records for:

- non-STK realized P&L
- non-USD stock realized P&L
- missing RMB FX evidence
- sell trades with missing historical lots for FIFO
- sell quantity exceeding available FIFO lots
- short/oversold cases
- potential corporate actions or transfer-related cost-basis hazards when detectable from Flex descriptions
- realized losses that need treatment confirmation

## FIFO Rebuild Rules

Build FIFO lots from available STK trades sorted by `date_time`.

- BUY/BOT adds a lot with quantity, cost, commission, currency, symbol.
- SELL/SLD consumes earliest lots.
- FIFO realized P&L is sell proceeds minus matched cost, with commissions included when available.
- If a sell cannot be fully matched from available prior lots, mark that symbol `fifo_status="incomplete"` and add `review_required`.
- Keep IBKR realized P&L available even when FIFO is incomplete.

## Diluted/Breakeven Comparison

Reuse `DilutedCostAnalyzer` for STK trades and expose its per-symbol realized P&L as a comparison口径. Do not use diluted/breakeven P&L as the primary tax estimate.

## FX Handling

Use the existing Phase 1 same-tax-year IBKR USD/RMB FX trade weighted average when available. Do not invent rates. Non-USD gains and missing RMB FX evidence are `review_required` unless a later explicit-rate mode is designed.

## Tests

Add TDD tests before implementation:

1. USD 100 IBKR realized gain at RMB rate 7.0 produces RMB 700 property-transfer candidate income and RMB 140 estimated tax.
2. USD 50 IBKR realized loss produces taxable income 0 and a review-required loss item.
3. IBKR, FIFO, and diluted/breakeven comparison rows are emitted for a simple complete-lot stock example.
4. Missing historical FIFO lot marks FIFO incomplete and adds `review_required` while preserving IBKR primary P&L.
5. Non-STK realized P&L is excluded from automatic calculation and added to `review_required`.
6. `include_realized_pnl=False` preserves Phase 1 output shape.
7. MCP `ibkr_china_tax_annual_calc(include_realized_pnl=True)` returns the Phase 2 fields.

## Out of Scope

- Automatic 1042-S import or reconciliation.
- Options, futures, FX gains/losses, transfers, splits, exercise/assignment, and other corporate-action cost basis handling.
- Final China tax filing advice or official exchange-rate determination.
- Cross-category or cross-market loss offset conclusions.

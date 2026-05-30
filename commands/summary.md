---
description: "Generate a one-page IBKR account summary from loaded Flex or local activity data"
argument-hint: "[--mode=flex|file] [--source=/path/activity.xml] [--period=YYYY-MM-DD:YYYY-MM-DD]"
allowed-tools: ["mcp__plugin_ibkr-trade-analyzer_ibkr-analyzer__ibkr_fetch_data", "mcp__plugin_ibkr-trade-analyzer_ibkr-analyzer__ibkr_pnl_summary", "mcp__plugin_ibkr-trade-analyzer_ibkr-analyzer__ibkr_portfolio", "mcp__plugin_ibkr-trade-analyzer_ibkr-analyzer__ibkr_cost_analysis", "mcp__plugin_ibkr-trade-analyzer_ibkr-analyzer__ibkr_trade_patterns"]
---

Generate a concise IBKR account summary using read-only reporting data.

## Workflow

1. Load data with `ibkr_fetch_data` using the requested mode/source, or Flex by default.
2. Call `ibkr_pnl_summary`, `ibkr_portfolio`, and `ibkr_cost_analysis`.
3. Call `ibkr_trade_patterns` only if the user asks for behavior/style detail.

## Output Format

- **Executive Summary** — 5 bullets maximum.
- **Key Metrics** — compact table for available P&L, drawdown, Sharpe, positions, cash, and fees.
- **Portfolio & Costs** — concentration, cash/currency exposure, commissions, interest, and dividends.
- **Watch Items** — up to 3 neutral review items, not trade instructions.

## Guardrails

- State that this is informational analysis, not investment or tax advice.
- Show exact tool errors and the next setup/diagnostic step.
- Do not invent missing account totals or metrics.

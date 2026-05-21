---
description: "Generate a one-page IBKR account summary from loaded Flex or local activity data"
argument-hint: "[--mode=flex|file] [--source=/path/activity.xml] [--period=YYYY-MM-DD:YYYY-MM-DD]"
allowed-tools: ["mcp__plugin_ibkr-trade-analyzer_ibkr-analyzer__ibkr_fetch_data", "mcp__plugin_ibkr-trade-analyzer_ibkr-analyzer__ibkr_pnl_summary", "mcp__plugin_ibkr-trade-analyzer_ibkr-analyzer__ibkr_portfolio", "mcp__plugin_ibkr-trade-analyzer_ibkr-analyzer__ibkr_cost_analysis", "mcp__plugin_ibkr-trade-analyzer_ibkr-analyzer__ibkr_trade_patterns"]
---

Generate a concise IBKR account summary. Use read-only MCP tools only; never place trades or change account settings.

## Workflow

1. Ensure data is loaded:
   - If the user provided a local file, call `ibkr_fetch_data(mode="file", source="<path>")`.
   - Otherwise call `ibkr_fetch_data(mode="flex")`.
2. Call `ibkr_pnl_summary`.
3. Call `ibkr_portfolio`.
4. Call `ibkr_cost_analysis`.
5. Call `ibkr_trade_patterns` only when the user asks for behavior/style detail or when the summary lacks enough context.

## Output Format

Return Markdown with these sections:

1. **Executive Summary** — 5 bullets maximum.
2. **Key Metrics** — table with P&L, Sharpe ratio, max drawdown, cash balances/count, position count, total commissions, and fee-to-P&L ratio when available.
3. **Portfolio & Risk** — concentration, cash exposure, currency exposure, and risk score when available.
4. **Costs & Friction** — commissions, interest, dividends, and fee burden.
5. **Watch Items** — 3 action-oriented observations phrased as things to review, not trade instructions.

## Guardrails

- State that this is informational analysis, not investment or tax advice.
- If data is missing or credentials are not configured, show the exact error and the next setup step.
- Do not invent account totals or metrics that are not present in tool output.

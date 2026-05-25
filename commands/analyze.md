---
description: "Run targeted IBKR analysis sections with optional period and asset-type filters"
argument-hint: "[--sections=trade,pnl,portfolio,cost,fx,diluted_cost] [--period=YYYY-MM-DD:YYYY-MM-DD] [--asset-types=STK,OPT] [--mode=flex|file] [--source=/path/activity.xml]"
allowed-tools: ["mcp__plugin_ibkr-trade-analyzer_ibkr-analyzer__ibkr_fetch_data", "mcp__plugin_ibkr-trade-analyzer_ibkr-analyzer__ibkr_analyze", "mcp__plugin_ibkr-trade-analyzer_ibkr-analyzer__ibkr_pnl_summary", "mcp__plugin_ibkr-trade-analyzer_ibkr-analyzer__ibkr_portfolio", "mcp__plugin_ibkr-trade-analyzer_ibkr-analyzer__ibkr_trade_patterns", "mcp__plugin_ibkr-trade-analyzer_ibkr-analyzer__ibkr_cost_analysis", "mcp__plugin_ibkr-trade-analyzer_ibkr-analyzer__ibkr_fx_analysis"]
---

Run targeted IBKR analysis using the section that best matches the user's intent.

## Intent Routing

- P&L, profit, loss, drawdown, Sharpe, monthly returns → `sections=["pnl"]` or `ibkr_pnl_summary`.
- Trading habits, win rate, frequency, holding period, profit factor → `sections=["trade"]` or `ibkr_trade_patterns`.
- Holdings, allocation, concentration, cash, exposure → `sections=["portfolio"]` or `ibkr_portfolio`.
- Fees, commissions, interest, dividends, fee drag → `sections=["cost"]` or `ibkr_cost_analysis`.
- FX, currency conversion, non-base cash → `sections=["fx"]` or `ibkr_fx_analysis`.
- Cost basis, breakeven, FIFO, LIFO, diluted cost → `sections=["diluted_cost"]` or `ibkr_analyze`.

## Workflow

1. Ensure data is loaded with `ibkr_fetch_data`.
2. Map the user's words to the smallest section list that answers the question.
3. Pass `period` and `asset_types` to `ibkr_analyze` when the user provides filters.
4. Use specialized tools for quick summaries when no filters are required.

## Output Format

Return Markdown with these sections:

1. **Scope** — data source, period, asset types, and selected sections.
2. **Findings** — concise bullets grouped by selected section.
3. **Evidence Table** — key metrics from the tool output.
4. **Limitations** — missing fields, stale report timing, or unsupported filters.

## Guardrails

- Ask a clarifying question only if the user's requested section cannot be inferred.
- Do not run all sections when one section is enough.
- Do not treat `price` as available through `ibkr_analyze`; the MCP analyzer sections are `trade`, `pnl`, `portfolio`, `cost`, `fx`, `diluted_cost`, and `china_tax`.

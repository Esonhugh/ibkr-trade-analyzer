---
description: "Analyze IBKR cash balances, currency exposure, FX history, and neutral review categories"
argument-hint: "[--mode=flex|file] [--source=/path/activity.xml] [--base=USD]"
allowed-tools: ["mcp__plugin_ibkr-trade-analyzer_ibkr-analyzer__ibkr_fetch_data", "mcp__plugin_ibkr-trade-analyzer_ibkr-analyzer__ibkr_portfolio", "mcp__plugin_ibkr-trade-analyzer_ibkr-analyzer__ibkr_fx_analysis", "mcp__plugin_ibkr-trade-analyzer_ibkr-analyzer__ibkr_cost_analysis"]
---

Analyze IBKR cash and FX exposure. This command provides informational review categories only; it must not present output as financial, tax, or trading advice.

## Workflow

1. Ensure data is loaded with `ibkr_fetch_data`.
2. Call `ibkr_portfolio` to inspect cash balances and currency exposure.
3. Call `ibkr_fx_analysis` to inspect conversion history and rates.
4. Call `ibkr_cost_analysis` to inspect commissions, interest, and fee drag.

## Output Format

Return Markdown with these sections:

1. **Cash Overview** — table by currency with balance, base-currency equivalent when available, and share of cash.
2. **Currency Exposure** — major non-base exposures and whether they are operational, investment-related, or unexplained from the available data.
3. **FX History** — recent conversion pairs, average rates, rate ranges, and FX commissions when available.
4. **Exposure Review** — group currencies into `Currency exposures to review`, `Operational balances to review`, and `Monitor`, with one sentence of evidence for each.
5. **Risks & Caveats** — rate timing, spread/slippage, tax implications, and report staleness.

## Guardrails

- Include: "This is informational analysis, not investment, tax, or FX trading advice."
- Do not tell the user to execute a conversion.
- Do not invent live FX rates; use only loaded IBKR report data unless the user explicitly asks to fetch external market data with another tool.

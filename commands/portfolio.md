---
description: "Calculate IBKR portfolio holdings, allocation, concentration, cash, and position sizing"
argument-hint: "[--mode=flex|file] [--source=/path/activity.xml] [--asset-types=STK,OPT] [--ff]"
allowed-tools: ["mcp__plugin_ibkr-trade-analyzer_ibkr-analyzer__ibkr_fetch_data", "mcp__plugin_ibkr-trade-analyzer_ibkr-analyzer__ibkr_portfolio", "mcp__plugin_ibkr-trade-analyzer_ibkr-analyzer__ibkr_analyze"]
---

Review IBKR portfolio structure using read-only reporting data.

## Workflow

1. Ensure data is loaded:
   - If the user provided `--ff`, call `ibkr_fetch_data(mode="flex", force_refresh=true)`.
   - If the user provided a local file, call `ibkr_fetch_data(mode="file", source="<path>")`.
   - Otherwise call `ibkr_fetch_data(mode="flex")`.
2. Call `ibkr_portfolio` for the full snapshot.
3. If the user requested asset-type filtering, call `ibkr_analyze(sections=["portfolio"], asset_types="<types>")`.

## Output Format

Return Markdown with these sections:

1. **Portfolio Snapshot** — base currency, position count, cash balance count, and total value when available.
2. **All Holdings** — table of every holding sorted by portfolio percentage from largest to smallest.
3. **Allocation** — asset class, long/short, sector, and currency allocation when present.
4. **Concentration Review** — largest position share, top-5 share, and risk score when available.
5. **Position Sizing Notes** — neutral observations about oversize, illiquid, or concentrated positions.

## Guardrails

- Do not recommend buying or selling.
- Mark missing fields as `N/A` instead of estimating.
- State that portfolio values depend on IBKR report timing and may not equal live account value.

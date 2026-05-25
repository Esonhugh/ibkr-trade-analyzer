---
name: ibkr-trade-analyzer
description: >
  Analyze Interactive Brokers (IBKR) trading history with read-only access.
  Use for IBKR / Interactive Brokers / Flex Query / activity statement analysis,
  including account summary reports, portfolio review, position sizing, cash and FX exposure,
  P&L breakdown, win rate, Sharpe ratio, max drawdown, commissions, fees, cost basis,
  breakeven / 保本价 / 摊薄成本, FIFO/LIFO, 现金换汇建议, 持仓分析, 盈亏分析,
  交易复盘, 账户摘要, and brokerage trading behavior.
---

# IBKR Trade Analyzer

Analyze Interactive Brokers trading history using **read-only** MCP tools. Follow the user's language for the response.

This skill is an intent router: identify what the user wants, load data once, call the smallest set of tools that answers the question, and present a structured report.

## Safety Boundary

- Flex Web Service is read-only reporting data.
- Never place trades, convert currency, create orders, or modify account settings.
- Cash-FX, portfolio, and risk comments are informational analysis, not investment, tax, or FX trading advice.
- Do not invent missing account totals, live prices, or FX rates.

## Data Loading

Before any analysis, ensure data is loaded:

- Flex mode: call `ibkr_fetch_data(mode="flex")`.
- Local file mode: call `ibkr_fetch_data(mode="file", source="/path/to/activity.xml")`.
- If credentials are missing, tell Claude users to run `claude plugin configure ibkr-trade-analyzer`; tell Codex users to export `IBKR_FLEX_TOKEN` and `IBKR_QUERY_ID` before starting Codex.

Data is cached in the MCP server session. Do not reload unless the user asks for `force_refresh` or changes the source file.

## Intent Router

| User Intent | Examples | Preferred Tool or Command Workflow |
|---|---|---|
| Account summary | summary report, 一页纸总结, quick review, 账户摘要 | `ibkr_pnl_summary` + `ibkr_portfolio` + `ibkr_cost_analysis`; use `/ibkr-trade-analyzer:summary` when slash commands are available |
| Portfolio / positions | holdings, position sizing, 仓位, 持仓, concentration | `ibkr_portfolio`; use `/ibkr-trade-analyzer:portfolio` when available |
| Cash and FX | cash balance, FX exposure, 现金换汇建议, currency exposure | `ibkr_portfolio` + `ibkr_fx_analysis` + `ibkr_cost_analysis`; use `/ibkr-trade-analyzer:cash-fx` when available |
| P&L performance | realized P&L, Sharpe, drawdown, monthly returns, 盈亏 | `ibkr_pnl_summary` |
| Trading behavior | win rate, frequency, holding period, profit factor, 交易习惯 | `ibkr_trade_patterns` |
| Costs and fees | commissions, interest, dividends, fee drag, 手续费 | `ibkr_cost_analysis` |
| China tax evidence | 中国个税, 境外所得, 外税抵免, 1042-S, 年度报税 | `ibkr_china_tax_annual_calc`; use `china-tax` skill for official-source workflow |
| Cost basis | breakeven, 保本价, 摊薄成本, FIFO, LIFO | `ibkr_analyze(sections=["diluted_cost"])` |
| Full report | generate report, export HTML, 导出报告 | `ibkr_generate_report`; use `/ibkr-trade-analyzer:report` when available |
| Filtered advanced analysis | date range, asset type, STK/OPT only | `ibkr_analyze(sections=[...], period="YYYY-MM-DD:YYYY-MM-DD", asset_types="STK,OPT")`; `china_tax` is opt-in only |

Ask one clarifying question only when the data source or intended section cannot be inferred.

## Available MCP Tools

| Tool | Use When |
|------|----------|
| `ibkr_fetch_data` | First call — loads Flex API data or a local CSV/XML file. |
| `ibkr_analyze` | Filtered or multi-section analysis with optional `period` and `asset_types`. |
| `ibkr_portfolio` | Portfolio snapshot: positions, cash, allocation, concentration, risk score. |
| `ibkr_pnl_summary` | P&L overview: total, Sharpe, drawdown, monthly returns, winners/losers. |
| `ibkr_trade_patterns` | Trading behavior: win rate, frequency, holding periods, profit factor. |
| `ibkr_fx_analysis` | FX conversion history, average rates, ranges, FX commissions. |
| `ibkr_cost_analysis` | Commissions, interest, dividends, and fee-to-P&L ratio. |
| `ibkr_china_tax_annual_calc` | Informational China resident annual dividend/withholding estimate from IBKR Flex data and IBKR FX evidence. |
| `ibkr_generate_report` | Generate Markdown and HTML report files. |

## Output Templates

### Summary Report

Use this format for account summaries:

1. **Executive Summary** — 5 bullets maximum.
2. **Key Metrics** — compact table.
3. **Portfolio & Risk** — concentration, cash, currency, risk score.
4. **Costs & Friction** — commissions, interest, dividends, fee burden.
5. **Watch Items** — things to review, not trading instructions.

### Portfolio Review

Use this format for holdings and position sizing:

1. **Portfolio Snapshot**.
2. **Top Positions** — top 10 by exposure when available.
3. **Allocation** — asset class, currency, sector, long/short when available.
4. **Concentration Review**.
5. **Position Sizing Notes**.

### Cash-FX Review

Use this format for currency questions:

1. **Cash Overview** — by currency.
2. **Currency Exposure**.
3. **FX History**.
4. **Conversion Considerations** — `Currency exposures to review`, `Operational balances to review`, `Monitor`.
5. **Risks & Caveats** — include informational-analysis disclaimer.

## Troubleshooting

- `Flex credentials not configured` — Claude: run `claude plugin configure ibkr-trade-analyzer`; Codex: export `IBKR_FLEX_TOKEN` and `IBKR_QUERY_ID` before starting Codex.
- `Token expired` — reconfigure the plugin with a new Flex token.
- Rate limit or cooldown — IBKR Flex can rate-limit repeated queries; use cached data or wait.
- Empty data — confirm the Flex Query includes Trades, Cash Transactions, Open Positions, and Account Information.
- Local file parse error — verify the file path and prefer XML exports.

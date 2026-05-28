---
name: ibkr-trade-analyzer
description: >
  This skill should be used when the user asks to analyze Interactive Brokers
  (IBKR) trading history, Flex Query data, activity statements, or local IBKR
  CSV/XML exports. Use it for account summaries, portfolio/holding review,
  position sizing, cash and FX exposure review, P&L, win rate, Sharpe ratio,
  max drawdown, commissions, fees, cost basis, breakeven / 保本价 / 摊薄成本,
  FIFO/LIFO comparison, report export, 交易复盘, 账户摘要, 持仓分析, 盈亏分析,
  and neutral 现金/外汇敞口 review. It provides read-only analysis only and must
  not place trades, convert currency, or give investment/tax advice.
version: 2.2.0
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
- If credentials are missing, tell Claude users to run `claude plugin configure ibkr-trade-analyzer`.

Data is cached in the MCP server session only while it is fresh for the current local date. The server may reload from today's XML cache or refresh Flex data when the in-memory session is stale. Do not force reload unless the user asks for `force_refresh`, uses `/ibkr-trade-analyzer:portfolio --ff`, or changes the source file.

## Intent Router

| User Intent | Examples | Preferred Tool or Command Workflow |
|---|---|---|
| Account summary | summary report, 一页纸总结, quick review, 账户摘要 | `ibkr_pnl_summary` + `ibkr_portfolio` + `ibkr_cost_analysis`; use `/ibkr-trade-analyzer:summary` when slash commands are available |
| Portfolio / positions | holdings, position sizing, 仓位, 持仓, concentration | `ibkr_portfolio`; use `/ibkr-trade-analyzer:portfolio` when available, or `/ibkr-trade-analyzer:portfolio --ff` when the user asks to force fresh Flex data |
| Cash and FX | cash balance, FX exposure, 现金换汇建议, currency exposure | `ibkr_portfolio` + `ibkr_fx_analysis` + `ibkr_cost_analysis`; use `/ibkr-trade-analyzer:cash-fx` when available |
| P&L performance | realized P&L, Sharpe, drawdown, monthly returns, 盈亏 | `ibkr_pnl_summary` |
| Trading behavior | win rate, frequency, holding period, profit factor, 交易习惯 | `ibkr_trade_patterns` |
| Costs and fees | commissions, interest, dividends, fee drag, 手续费 | `ibkr_cost_analysis` |
| China tax evidence | 中国个税, 境外所得, 外税抵免, 1042-S, 年度报税 | `ibkr_china_tax_annual_calc`; use `china-tax` skill and `/ibkr-trade-analyzer:china-tax-annual` for official-source annual workflows |
| China tax planning | 年前税务优化, year-end China tax planning, evidence readiness | use `china-tax` skill and `/ibkr-trade-analyzer:china-tax-year-end-plan` for neutral review workflows |
| Cost basis | breakeven, 保本价, 摊薄成本, FIFO, LIFO | `ibkr_analyze(sections=["diluted_cost"])` |
| Full report | generate report, export HTML, 导出报告 | `ibkr_generate_report`; use `/ibkr-trade-analyzer:report` when available |
| Filtered advanced analysis | date range, asset type, STK/OPT only | `ibkr_analyze(sections=[...], period="YYYY-MM-DD:YYYY-MM-DD", asset_types="STK,OPT")`; use `/ibkr-trade-analyzer:analyze` when available; `china_tax` is opt-in only |

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
| `ibkr_china_tax_annual_calc` | Informational China resident annual dividend/withholding estimate from IBKR Flex data and IBKR FX evidence; requires `tax_year` unless data dates allow inference. |
| `ibkr_generate_report` | Generate Markdown and HTML report files. |

`ibkr_china_tax_annual_calc` and `ibkr_analyze(sections=["china_tax"])` support opt-in STK realized P&L evidence with `include_realized_pnl=True`, `realized_pnl_asset_types=["STK"]`, and `china_iit_property_transfer_rate` when the user explicitly requests realized-gain review.

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

## Additional Resources

- `scripts/USAGE.md` — standalone CLI usage, analyzer sections, cache behavior, and local file workflows.
- `scripts/ibkr_analyzer.py` — standalone read-only CLI wrapper for generating reports outside MCP workflows.

## Troubleshooting

- `Flex credentials not configured` — run `claude plugin configure ibkr-trade-analyzer`.
- `Token expired` — reconfigure the plugin with a new Flex token.
- Rate limit or cooldown — IBKR Flex can rate-limit repeated queries; use cached data or wait.
- Empty data — confirm the Flex Query includes Trades, Cash Transactions, Open Positions, and Account Information.
- Local file parse error — verify the file path and prefer XML exports.

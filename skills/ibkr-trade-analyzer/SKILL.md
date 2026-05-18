---
name: ibkr-trade-analyzer
description: >
  Analyze Interactive Brokers (IBKR) trading history with read-only access.
  Generates comprehensive reports on trading patterns, P&L performance, portfolio structure,
  and fee analysis. Supports Flex Web Service API and local CSV/XML file import.
  Use this skill whenever the user mentions IBKR trading analysis, Interactive Brokers
  trade history, portfolio review, trading pattern analysis, P&L breakdown, or wants to
  understand their brokerage trading behavior. Also trigger when the user mentions
  Flex Query, activity statement, trade log analysis, or asks about their win rate,
  Sharpe ratio, max drawdown, or commission costs from IBKR.
---

# IBKR Trade Analyzer

Analyze Interactive Brokers trading history using **read-only** data access via MCP tools.
The plugin exposes structured tools that return JSON results — no subprocess orchestration needed.

## Available MCP Tools

| Tool | Use When |
|------|----------|
| `ibkr_fetch_data` | First call — loads data from Flex API or local file. Caches in session. |
| `ibkr_analyze` | Full or partial analysis with optional filters (period, asset types) |
| `ibkr_portfolio` | Quick portfolio snapshot (positions, cash, risk score) |
| `ibkr_pnl_summary` | P&L overview (total, Sharpe, drawdown, equity curve) |
| `ibkr_trade_patterns` | Trading behavior (win rate, frequency, holding periods) |
| `ibkr_fx_analysis` | FX conversion history and rate analysis |
| `ibkr_cost_analysis` | Fee/commission breakdown |
| `ibkr_generate_report` | Generate HTML + Markdown report files |

## Interaction Flow

### Step 1: Determine data source

Ask the user how they want to provide data:

- **Flex Web Service** (default) — online, pulls from IBKR's read-only reporting API
- **Local file** — offline, reads a CSV or XML file exported from IBKR

### Step 2: Load data

Call `ibkr_fetch_data` with the appropriate mode:

```
# Flex mode (Claude auto-injects plugin config; Codex reads inherited env vars)
ibkr_fetch_data(mode="flex")

# Local file mode
ibkr_fetch_data(mode="file", source="/path/to/activity.xml")
```

Data is cached in the MCP server's memory — subsequent tool calls reuse it without re-fetching.

### Step 3: Run analysis

Use the specific tool that matches the user's question:

- "How's my portfolio?" → `ibkr_portfolio`
- "What's my P&L?" → `ibkr_pnl_summary`
- "Show my trading patterns" → `ibkr_trade_patterns`
- "How much am I paying in fees?" → `ibkr_cost_analysis`
- "Show FX conversions" → `ibkr_fx_analysis`
- "Full analysis" → `ibkr_analyze` (runs all sections)
- "Generate a report" → `ibkr_generate_report`

For filtered analysis, use `ibkr_analyze` with parameters:

```
ibkr_analyze(sections=["pnl", "trade"], period="2025-01-01:2025-12-31", asset_types="STK,OPT")
```

### Step 4: Present results

All tools return structured JSON. Present the key findings conversationally.
If the user wants a full report file, use `ibkr_generate_report` — it returns paths to
the generated Markdown and HTML files.

## What the Analysis Covers

**Trading Behavior Patterns:**
Trade frequency, holding periods by asset type, time-of-day patterns, win rate,
profit factor, trade size distribution

**P&L Performance:**
Total realized P&L, equity curve, monthly/quarterly returns, max drawdown,
Sharpe ratio, P&L by asset type and symbol, top winners/losers

**Portfolio Structure:**
Asset allocation, sector concentration, long/short ratio, position concentration,
currency exposure, cash balances, risk score (0-100)

**Fees & Cash Flow:**
Total commissions, per-trade costs, interest income/expense, dividend income,
fee-to-PnL ratio

**FX Analysis:**
Multi-currency conversion history, average rates, rate ranges, FX commissions

## Read-Only Safety Guarantees

1. **API level:** Flex Web Service has zero write/order endpoints
2. **Code level:** No trading execution libraries imported
3. **Network level:** Only outbound HTTPS to `gdcdyn.interactivebrokers.com`
4. **File level:** Only writes to the reports output directory

## Credential Setup

Claude credentials are configured via the plugin's `userConfig` and automatically injected
as environment variables into the MCP server. Users set them up with:

```
claude plugin configure ibkr-trade-analyzer
```

For Codex, set credentials in the shell that starts Codex:

```bash
export IBKR_FLEX_TOKEN="your-token-here"
export IBKR_QUERY_ID="123456"
export PROXY=""  # optional
codex
```

To create a Flex Query:

> 1. Log into [IBKR Account Management](https://www.interactivebrokers.com/sso/Login)
> 2. Navigate to **Performance & Reports > Flex Queries**
> 3. Click **Create New Flex Query** (Activity type)
>    - Enable: Trades, Cash Transactions, Open Positions, Account Information
>    - Output format: XML → Save → note the **Query ID**
> 4. Go to **Manage Flex Web Service** → generate/copy your **Token**

## Troubleshooting

- **"Flex credentials not configured"** — Claude: run `claude plugin configure ibkr-trade-analyzer`; Codex: export `IBKR_FLEX_TOKEN` and `IBKR_QUERY_ID`
- **"Token expired"** — reconfigure the plugin with a new token
- **Rate limit (10-min cooldown)** — Flex queries run at most once per 10 minutes; wait and retry
- **Empty data** — ensure the Flex Query includes Trades + Cash Transactions sections
- **Local file parse error** — try specifying `mode="file"` with the correct path

## CLI Usage (Power Users)

The underlying scripts still work standalone:

```bash
uv run skills/ibkr-trade-analyzer/scripts/ibkr_analyzer.py --mode flex --output reports/
uv run skills/ibkr-trade-analyzer/scripts/ibkr_analyzer.py --mode file --source data.xml
```

See `skills/ibkr-trade-analyzer/scripts/USAGE.md` for full CLI reference.

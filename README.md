# IBKR Trade Analyzer

[![Version](https://img.shields.io/badge/version-2.0.0-blue)](https://github.com/Esonhugh/Marketplace/tree/Skyworship/plugins/ibkr-trade-analyzer)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

**A Claude Code and Codex plugin for analyzing Interactive Brokers trading history — read-only, zero risk.**

## What It Does

This plugin connects to your IBKR account (via the read-only Flex Web Service API) or reads local CSV/XML exports, then generates comprehensive trading analysis reports covering:

| Dimension | Details |
|-----------|---------|
| **Trading Patterns** | Frequency, holding periods, time-of-day patterns, win rate, profit factor |
| **P&L Performance** | Realized P&L, equity curve, Sharpe ratio, max drawdown, monthly returns |
| **Portfolio Structure** | Asset allocation, sector concentration, long/short ratio, position sizing |
| **Cost Basis (3 methods)** | Breakeven/保本价 (Futu method), FIFO, LIFO — side-by-side comparison |
| **Fees & Cash Flow** | Commissions, interest, dividends, financing costs, fee-to-PnL ratio |
| **Cash & Currency** | Multi-currency balances, FX conversion rates (1 USD = X FCY), liquidity ratio |
| **Trading Style Profile** | Auto-generated qualitative summary (day/swing/position trader, bias, risk) |
| **Risk Assessment** | Scored 0-100 across 6 dimensions with specific warnings |
| **Price Charts** | Historical price data with buy/sell trade markers overlaid |

### What's New in v2.0.0

- **Dual plugin manifests** — supports Claude Code (`.claude-plugin/plugin.json`) and Codex (`.codex-plugin/plugin.json`)
- **Codex marketplace metadata** — adds `.agents/plugins/marketplace.json` for local Codex marketplace installation
- **Dual MCP launch path** — Claude keeps using `.mcp.json`; Codex uses `.codex-mcp.json` and the same MCP server
- **Host-aware cache** — uses plugin data directories when available, with local `cache/` fallback

### v1.2.0

- **Breakeven cost (保本价/摊薄成本)** — Futu-style breakeven price: profitable sells reduce remaining cost, losses raise it. Commission tracked separately (not folded into cost)
- **LIFO lot matching** — Last In, First Out cost basis as a comparison method (one of IBKR's 7 Tax Optimizer methods)
- **Three-way cost comparison** — Breakeven vs FIFO vs LIFO shown side-by-side for each symbol
- **Per-symbol deep dive** — `--symbol AMZN,BRK B` generates detailed trade history with cost evolution per method
- **`diluted_cost` analyzer section** — new `--analyzers diluted_cost` option; included in default "all" run

## Installation

### Method 1: Claude Code Marketplace

First, add this repository as a marketplace source:

```claude
/plugin marketplace add Esonhugh/Marketplace
```

Then install the plugin:

```claude
/plugin install ibkr-trade-analyzer
```

Or with the `claude` CLI:

```bash
claude plugin marketplace add Esonhugh/Marketplace
claude plugin install ibkr-trade-analyzer
```

### Method 2: Codex Local Marketplace

From this plugin root, add the repo as a Codex marketplace source:

```bash
codex plugin marketplace add "$(pwd)"
```

Then open Codex and install `ibkr-trade-analyzer` from `/plugins`.

Codex does not use Claude `userConfig`; set credentials in the shell that starts Codex:

```bash
export IBKR_FLEX_TOKEN="your-token-here"
export IBKR_QUERY_ID="123456"
export PROXY=""  # optional
codex
```

### Method 3: Clone from GitHub

Clone the entire marketplace repo and point Claude Code to the plugin directory:

```bash
git clone https://github.com/Esonhugh/Marketplace.git
claude --plugin-dir ./Marketplace/plugins/ibkr-trade-analyzer
```

Or clone just the plugin into your plugins directory:

```bash
git clone --depth 1 --filter=blob:none --sparse \
  https://github.com/Esonhugh/Marketplace.git /tmp/marketplace
cd /tmp/marketplace && git sparse-checkout set plugins/ibkr-trade-analyzer
cp -r plugins/ibkr-trade-analyzer ~/.claude/plugins/ibkr-trade-analyzer
```

## Usage

Once installed, simply tell Claude or Codex:

```
Analyze my IBKR trading history
```

The assistant will guide you through:

1. **Choose data source** — Flex Web Service (online) or local file (offline)
2. **Provide credentials** — Flex Token + Query ID, or a file path
3. **Run analysis** — automated, produces Markdown + interactive HTML reports
4. **Review results** — discuss findings interactively

### Workflow Commands

The plugin also exposes command-style workflows for common reviews:

| Command | Use When | Main Tools |
|---------|----------|------------|
| `/ibkr-trade-analyzer:summary` | One-page account summary | `ibkr_pnl_summary`, `ibkr_portfolio`, `ibkr_cost_analysis` |
| `/ibkr-trade-analyzer:portfolio` | Holdings, allocation, concentration, position sizing | `ibkr_portfolio` |
| `/ibkr-trade-analyzer:cash-fx` | Cash balances, currency exposure, conversion considerations | `ibkr_portfolio`, `ibkr_fx_analysis`, `ibkr_cost_analysis` |
| `/ibkr-trade-analyzer:report` | Generate Markdown and HTML reports | `ibkr_generate_report` |
| `/ibkr-trade-analyzer:analyze` | Targeted section analysis with filters | `ibkr_analyze` |

Cash-FX and portfolio outputs are informational analysis only. They do not place trades, convert currency, or provide investment or tax advice.

### Selective Analysis

Run only specific sections with `--analyzers`:

```bash
# P&L deep-dive only
uv run ibkr_analyzer.py --mode flex --analyzers pnl,trade

# FX costs only (no network for prices)
uv run ibkr_analyzer.py --mode file --source activity.xml --analyzers fx --no-prices

# Portfolio snapshot
uv run ibkr_analyzer.py --mode flex --analyzers portfolio --no-prices
```

Available sections: `trade`, `pnl`, `portfolio`, `cost`, `price`, `fx`, `diluted_cost` (default: all).

## Data Source Options

### Option A: Flex Web Service (Recommended)

Pulls data directly from IBKR's read-only reporting API.

**Setup:**
1. Log into [IBKR Account Management](https://www.interactivebrokers.com/sso/Login)
2. Go to **Performance & Reports > Flex Queries**
3. Create a new Activity Flex Query with sections: **Trades, Cash Transactions, Open Positions, Account Information**
4. Set output format to **XML**, save and note the **Query ID**
5. Under **Manage Flex Web Service**, get your **Flex Token**

**Claude plugin configuration:** Credentials are prompted automatically when you install the plugin:

```claude
/plugin install ibkr-trade-analyzer
```

Claude Code will prompt you for your Flex Token (stored securely in system keychain)
and Query ID. Credentials are injected automatically on every future run — no files to
manage, no `.gitignore` entries needed.

**Codex or scripting configuration** — Codex inherits environment variables when launching the bundled MCP server:

```bash
export IBKR_FLEX_TOKEN="your-token-here"
export IBKR_QUERY_ID="123456"
export PROXY="socks5://127.0.0.1:7980"  # optional
```

## Configuration

Claude credentials are configured at install time via Claude Code's built-in settings system. Codex credentials are read from environment variables inherited by the Codex process.

| Field | Sensitive | Description |
|-------|-----------|-------------|
| `flex_token` | Yes — stored in system keychain | Flex Web Service token |
| `query_id` | No — stored in settings.json | Flex Query numeric ID |
| `proxy` | No | Proxy URL, e.g. `socks5://127.0.0.1:7980`. Falls back to `ALL_PROXY` / `HTTPS_PROXY` env vars |

### Option B: Local File

Export from IBKR Client Portal or TWS, then provide the file path. Supports CSV and XML formats.

- **Client Portal**: Performance & Reports → Statements → Activity → Download (XML recommended)
- **TWS**: Account → Account Window → Export

Example command (if running the script directly):
```bash
uv run ibkr_analyzer.py --mode file --source ~/Downloads/activity.xml --output reports/
```

## Output

Reports are saved to `reports/`:
- `ibkr-analysis-YYYY-MM-DD.md` — full Markdown report with tables
- `ibkr-analysis-YYYY-MM-DD.html` — interactive HTML report with Plotly charts

The Flex XML response is cached under the plugin host data directory (`$PLUGIN_DATA/cache` or `$CLAUDE_PLUGIN_DATA/cache`), with local `cache/` fallback. Subsequent runs on the same day skip the API call and load from cache automatically.

## Safety Guarantees

This plugin is designed with **read-only safety** as a core principle:

1. **API level** — Flex Web Service has zero write/order endpoints
2. **Code level** — No trading execution libraries imported (no `ibapi`, no `ib_insync`)
3. **Network level** — Only outbound HTTPS to IBKR's Flex reporting endpoints
4. **File level** — Only writes to the `reports/` output directory

## Requirements

- Python >= 3.10
- Dependencies are auto-installed via [PEP 723](https://peps.python.org/pep-0723/) inline metadata with `uv run`

## License

MIT

## Author

[Esonhugh](https://github.com/Esonhugh) — [Plugin Homepage](https://github.com/Esonhugh/Marketplace/tree/Skyworship/plugins/ibkr-trade-analyzer)

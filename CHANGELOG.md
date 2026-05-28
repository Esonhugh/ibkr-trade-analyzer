# Changelog

## [2.2.0] - 2026-05-28

### Added

- `portfolio --ff` workflow documentation for forcing a fresh Flex fetch before portfolio analysis.
- China tax MCP schema support for opt-in realized P&L parameters: `include_realized_pnl`, `realized_pnl_asset_types`, and `china_iit_property_transfer_rate`.
- Regression tests for session cache freshness, force refresh bypass, timestamp updates, portfolio command docs, China tax realized P&L MCP wiring, README config keys, and China tax command script guidance.

### Changed

- MCP session cache now reuses in-memory data only when it was loaded on the current local day; stale sessions fall through to today's XML cache or Flex API refresh.

## [2.1.0] - 2026-05-21

### Added

- Workflow command docs for account summary, portfolio review, cash/FX review, full reports, and targeted analysis.
- Command packaging validation for frontmatter and allowed IBKR MCP tools.

### Changed

- Skill routing now maps natural-language IBKR requests to focused MCP workflows.
- README usage docs now describe the new command-style workflows.

## [2.0.0] - 2026-05-18

### Changed

- Claude Flex token config is marked sensitive.

## [1.2.0] - 2026-05-09

### Added

- **Breakeven cost / 保本价 (Futu method)** — diluted cost analyzer computes a running breakeven price per symbol. Selling at profit reduces breakeven; selling at loss raises it. Commission tracked separately, matching Futu/Moomoo convention.
- **LIFO lot matching** — new `LifoAnalyzer` implements Last In, First Out cost basis (one of IBKR's 7 Tax Optimizer methods). Sells the most recently purchased lots first.
- **Three-way cost comparison** — report shows Breakeven vs FIFO vs LIFO side-by-side in summary tables and per-symbol detail cards.
- **Per-symbol deep dive** — `--symbol AMZN,BRK B` flag generates detailed trade-by-trade cost evolution with breakeven/FIFO/LIFO comparison.
- **`diluted_cost` analyzer section** — new section available via `--analyzers diluted_cost`; included by default when no `--analyzers` flag is specified.

### Fixed

- `cum_sell_amount` accumulator bug in diluted cost — was unconditionally incrementing after position-clearing sells, inflating realized P&L for subsequent holding periods.

## [1.1.0] - 2026-04-19

### Added

- `--analyzers` flag — run only specific sections (e.g. `--analyzers pnl,fx`), default is all.
- XML auto-cache — Flex XML saved to plugin data dir; same-day reruns skip the API call.
- FX rate display as `1 USD = X FCY` (more natural for USD-base accounts).
- Modular analyzers subpackage (`analyzers/trade.py`, `pnl.py`, `portfolio.py`, `cost.py`, `price.py`, `fx.py`).

## [1.0.0] - 2026-03-15

### Added

- Initial release with Flex Web Service and local file support.
- Trading patterns, P&L, portfolio, cost, price, and FX analysis.
- Markdown and interactive HTML (Plotly) report generation.
- PEP 723 inline metadata for zero-config `uv run` execution.

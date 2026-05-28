# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "mcp>=1.0",
#     "pandas>=2.0",
#     "plotly>=5.0",
#     "jinja2>=3.0",
#     "requests[socks]>=2.28",
#     "yfinance>=0.2",
# ]
# ///
"""IBKR Trade Analyzer - stdio MCP server.

Exposes structured tools for analyzing Interactive Brokers trading data.
Reads credentials from environment variables injected by Claude Code.
Imports shared analyzer modules from ibkr_analyzer_lib.
"""

from __future__ import annotations

import csv
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

def _first_env(*names: str) -> str:
    """Return the first non-empty environment variable from names."""
    for name in names:
        value = os.environ.get(name)
        if value:
            return value
    return ""


_ROOT_ENV_NAMES = ("PLUGIN_ROOT", "CLAUDE_PLUGIN_ROOT")
_DATA_ENV_NAMES = ("PLUGIN_DATA", "CLAUDE_PLUGIN_DATA")
_FLEX_TOKEN_ENV_NAMES = ("IBKR_FLEX_TOKEN", "CLAUDE_PLUGIN_OPTION_IBKR_FLEX_TOKEN")
_QUERY_ID_ENV_NAMES = ("IBKR_QUERY_ID", "CLAUDE_PLUGIN_OPTION_IBKR_QUERY_ID")
_PROXY_ENV_NAMES = (
    "PROXY",
    "CLAUDE_PLUGIN_OPTION_PROXY",
    "ALL_PROXY",
    "HTTPS_PROXY",
    "HTTP_PROXY",
)

# Prefer host-provided plugin root env vars, then derive from this file.
_project_root = Path(__file__).resolve().parent.parent
_plugin_root = _first_env(*_ROOT_ENV_NAMES) or str(_project_root)
_plugin_data = _first_env(*_DATA_ENV_NAMES)
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from ibkr_analyzer_lib.analyzers import (
    ChinaTaxAnalyzer,
    ChinaTaxConfig,
    CostAnalyzer,
    DilutedCostAnalyzer,
    FxAnalyzer,
    LifoAnalyzer,
    PnLAnalyzer,
    PortfolioAnalyzer,
    PriceAnalyzer,
    TradeAnalyzer,
)
from ibkr_analyzer_lib.loader import DataLoader
from ibkr_analyzer_lib.models import AccountData
from ibkr_analyzer_lib.report import ReportGenerator

# --- Session state ---
_session_data: AccountData | None = None
_session_loaded_at: float | None = None
_data_source_info: str = ""


def _is_session_cache_fresh(now: float | None = None) -> bool:
    if _session_data is None or _session_loaded_at is None:
        return False
    current = datetime.fromtimestamp(time.time() if now is None else now).date()
    loaded = datetime.fromtimestamp(_session_loaded_at).date()
    return loaded == current

# --- Credentials from env ---
# Primary: injected by Claude .mcp.json ${user_config.*} expansion.
# Fallback: *_PLUGIN_OPTION_* names used by plugin host subprocess integrations.
FLEX_TOKEN = _first_env(*_FLEX_TOKEN_ENV_NAMES)
QUERY_ID = _first_env(*_QUERY_ID_ENV_NAMES)
PROXY = _first_env(*_PROXY_ENV_NAMES)


def _data_dir() -> Path:
    """Writable cache directory for plugin hosts and local development."""
    d = Path(_plugin_data) / "cache" if _plugin_data else Path(_plugin_root) / "cache"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _load_data(mode: str = "flex", source: str | None = None, force_refresh: bool = False) -> AccountData:
    """Load or return cached AccountData. Raises RuntimeError on failure."""
    global _session_data, _session_loaded_at, _data_source_info

    if _session_data is not None and not force_refresh and _is_session_cache_fresh():
        return _session_data

    if mode == "flex":
        if not FLEX_TOKEN or not QUERY_ID:
            raise RuntimeError(
                "Flex credentials not configured. "
                "Run: claude plugin configure ibkr-trade-analyzer."
            )
        # Check for today's cached XML in the host data cache.
        data_dir = _data_dir()
        today_str = datetime.now().strftime("%Y-%m-%d")
        cached_xml = data_dir / f"flex-{today_str}.xml"

        if not cached_xml.exists():
            matches = sorted(data_dir.glob(f"*-flex-ibkr-{today_str}.xml"), key=lambda p: p.stat().st_mtime, reverse=True)
            if matches:
                cached_xml = matches[0]

        if cached_xml.exists() and not force_refresh:
            _session_data = DataLoader.from_file(str(cached_xml), "xml")
            _data_source_info = f"Loaded from cache: {cached_xml.name}"
        else:
            _session_data = DataLoader.from_flex(
                FLEX_TOKEN, QUERY_ID, proxy=PROXY or None,
                dump_xml=str(cached_xml),
            )
            _data_source_info = f"Fetched from Flex API ({today_str})"
    elif mode == "file":
        if not source:
            raise RuntimeError("File path is required for file mode")
        _session_data = DataLoader.from_file(source)
        _data_source_info = f"Loaded from file: {source}"
    else:
        raise RuntimeError(f"Unknown mode: {mode}. Use 'flex' or 'file'.")

    _session_loaded_at = time.time()
    return _session_data


def _json_safe(obj: Any) -> Any:
    """Make objects JSON-serializable."""
    import datetime as _dt
    import math
    if isinstance(obj, float):
        if math.isinf(obj):
            return None
        if math.isnan(obj):
            return None
    if isinstance(obj, _dt.datetime):
        return obj.isoformat()
    if isinstance(obj, _dt.date):
        return obj.isoformat()
    if isinstance(obj, Path):
        return str(obj)
    if hasattr(obj, "to_dict"):
        return obj.to_dict()
    if hasattr(obj, "__dataclass_fields__"):
        from dataclasses import asdict
        return asdict(obj)
    return obj


def _sanitize_floats(obj: Any) -> Any:
    """Replace inf/nan with None recursively before JSON serialization."""
    import math
    if isinstance(obj, float):
        if math.isinf(obj) or math.isnan(obj):
            return None
        return obj
    if isinstance(obj, dict):
        return {k: _sanitize_floats(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize_floats(v) for v in obj]
    return obj


def _serialize(data: Any) -> str:
    """Serialize data to JSON string."""
    return json.dumps(_sanitize_floats(data), default=_json_safe, ensure_ascii=False, indent=2)


# --- MCP Server ---

server = Server("ibkr-analyzer")


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="ibkr_fetch_data",
            description=(
                "Fetch IBKR trading data from Flex Web Service API or load from a local file. "
                "Returns a summary of loaded data (trade count, position count, date range). "
                "Data is cached in memory for subsequent tool calls within the session."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "mode": {
                        "type": "string",
                        "enum": ["flex", "file"],
                        "description": "Data source: 'flex' for Flex Web Service API, 'file' for local CSV/XML",
                        "default": "flex",
                    },
                    "source": {
                        "type": "string",
                        "description": "File path (required for file mode, ignored for flex mode)",
                    },
                    "force_refresh": {
                        "type": "boolean",
                        "description": "Force re-fetch even if today's data is cached",
                        "default": False,
                    },
                },
            },
        ),
        Tool(
            name="ibkr_analyze",
            description=(
                "Run full or partial analysis on loaded IBKR data. "
                "Returns structured JSON with results from selected analyzers. "
                "Data must be loaded first via ibkr_fetch_data."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "sections": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": ["trade", "pnl", "portfolio", "cost", "fx", "diluted_cost", "china_tax"],
                        },
                        "description": "Which analysis sections to run. Default: all.",
                    },
                    "period": {
                        "type": "string",
                        "description": "Date range filter, e.g. '2025-01-01:2025-12-31'",
                    },
                    "asset_types": {
                        "type": "string",
                        "description": "Filter by asset types, e.g. 'STK,OPT'",
                    },
                    "tax_year": {
                        "type": "integer",
                        "description": "Annual calculation year for china_tax section",
                    },
                    "china_iit_dividend_rate": {
                        "type": "number",
                        "description": "China IIT estimate rate for china_tax section. Default: 0.20",
                        "default": 0.20,
                    },
                    "include_realized_pnl": {
                        "type": "boolean",
                        "description": "Include opt-in STK realized P&L evidence for china_tax section. Default: false",
                        "default": False,
                    },
                    "realized_pnl_asset_types": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Asset categories to include for realized P&L evidence. Default: ['STK']",
                    },
                    "china_iit_property_transfer_rate": {
                        "type": "number",
                        "description": "China IIT estimate rate for property transfer income candidates. Default: 0.20",
                        "default": 0.20,
                    },
                },
            },
        ),
        Tool(
            name="ibkr_portfolio",
            description=(
                "Quick portfolio snapshot: current positions, cash balances, "
                "asset allocation, risk score, and concentration metrics."
            ),
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="ibkr_pnl_summary",
            description=(
                "P&L overview: total realized P&L, Sharpe ratio, max drawdown, "
                "monthly returns, top winners/losers, equity curve data."
            ),
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="ibkr_trade_patterns",
            description=(
                "Trading behavior analysis: win rate, trade frequency, "
                "holding periods, time-of-day patterns, profit factor, size distribution."
            ),
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="ibkr_fx_analysis",
            description=(
                "FX conversion analysis: currency pair history, average rates, "
                "rate ranges, FX commissions, current rate comparison."
            ),
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="ibkr_cost_analysis",
            description=(
                "Fee and commission breakdown: total commissions, per-trade costs, "
                "interest income/expense, dividend income, fee-to-PnL ratio."
            ),
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="ibkr_china_tax_annual_calc",
            description=(
                "Prepare an informational China resident annual overseas investment tax estimate "
                "from loaded IBKR Flex dividends, withholding tax, and IBKR FX evidence."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "tax_year": {
                        "type": "integer",
                        "description": "Annual calculation year",
                    },
                    "china_iit_dividend_rate": {
                        "type": "number",
                        "description": "China IIT estimate rate for interest/dividends/bonus income. Default: 0.20",
                        "default": 0.20,
                    },
                    "include_realized_pnl": {
                        "type": "boolean",
                        "description": "Include opt-in STK realized P&L evidence. Default: false",
                        "default": False,
                    },
                    "realized_pnl_asset_types": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Asset categories to include for realized P&L evidence. Default: ['STK']",
                    },
                    "china_iit_property_transfer_rate": {
                        "type": "number",
                        "description": "China IIT estimate rate for property transfer income candidates. Default: 0.20",
                        "default": 0.20,
                    },
                    "output_csv": {
                        "type": "string",
                        "description": "Optional directory for CSV evidence tables",
                    },
                },
                "required": ["tax_year"],
            },
        ),
        Tool(
            name="ibkr_generate_report",
            description=(
                "Generate full HTML and Markdown report files. "
                "Returns file paths to the generated reports."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "output_dir": {
                        "type": "string",
                        "description": "Output directory for reports. Default: 'reports/'",
                        "default": "reports/",
                    },
                    "sections": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": ["trade", "pnl", "portfolio", "cost", "fx", "diluted_cost", "price"],
                        },
                        "description": "Which sections to include. Default: all.",
                    },
                },
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    try:
        result = await _handle_tool(name, arguments)
        return [TextContent(type="text", text=result)]
    except Exception as exc:
        return [TextContent(type="text", text=json.dumps({"error": str(exc)}))]


async def _handle_tool(name: str, args: dict[str, Any]) -> str:
    global _session_data

    if name == "ibkr_fetch_data":
        mode = args.get("mode", "flex")
        source = args.get("source")
        force = args.get("force_refresh", False)
        data = _load_data(mode=mode, source=source, force_refresh=force)
        # Build summary
        date_range = ""
        if data.trades:
            dates = [t.date_time for t in data.trades if t.date_time]
            if dates:
                date_range = f"{min(dates).strftime('%Y-%m-%d')} to {max(dates).strftime('%Y-%m-%d')}"
        summary = {
            "status": "ok",
            "source": _data_source_info,
            "account_id": data.account_id,
            "base_currency": data.base_currency,
            "trades": len(data.trades),
            "cash_transactions": len(data.cash_transactions),
            "open_positions": len(data.open_positions),
            "cash_balances": len(data.cash_balances),
            "date_range": date_range,
        }
        return _serialize(summary)

    # All other tools require data to be loaded
    if _session_data is None:
        # Auto-load from flex if credentials available
        _load_data(mode="flex")
    data = _session_data
    assert data is not None

    if name == "ibkr_analyze":
        return await _handle_analyze(data, args)
    elif name == "ibkr_portfolio":
        return _handle_portfolio(data)
    elif name == "ibkr_pnl_summary":
        return _handle_pnl(data)
    elif name == "ibkr_trade_patterns":
        return _handle_trade_patterns(data)
    elif name == "ibkr_fx_analysis":
        return _handle_fx(data)
    elif name == "ibkr_cost_analysis":
        return _handle_cost(data)
    elif name == "ibkr_china_tax_annual_calc":
        return _handle_china_tax(data, args)
    elif name == "ibkr_generate_report":
        return _handle_report(data, args)
    else:
        raise RuntimeError(f"Unknown tool: {name}")


def _apply_filters(data: AccountData, args: dict[str, Any]) -> AccountData:
    """Apply period and asset_types filters, returning a shallow copy."""
    from dataclasses import replace
    filtered = replace(data)

    period = args.get("period")
    if period:
        parts = period.split(":")
        if len(parts) == 2:
            start = datetime.strptime(parts[0], "%Y-%m-%d")
            end = datetime.strptime(parts[1], "%Y-%m-%d")
            filtered.trades = [t for t in filtered.trades if t.date_time and start <= t.date_time <= end]
            filtered.cash_transactions = [
                ct for ct in filtered.cash_transactions if ct.date_time and start <= ct.date_time <= end
            ]

    asset_types = args.get("asset_types")
    if asset_types:
        types = set(asset_types.split(","))
        filtered.trades = [t for t in filtered.trades if t.asset_category in types]
        filtered.open_positions = [p for p in filtered.open_positions if p.asset_category in types]

    return filtered


async def _handle_analyze(data: AccountData, args: dict[str, Any]) -> str:
    """Run selected analyzers and return combined results."""
    all_sections = {"trade", "pnl", "portfolio", "cost", "fx", "diluted_cost"}
    sections = set(args.get("sections", [])) or all_sections
    filtered = _apply_filters(data, args)

    results: dict[str, Any] = {}

    if "trade" in sections:
        ta = TradeAnalyzer(filtered.trades)
        results["trade"] = ta.summary()

    if "pnl" in sections:
        pa = PnLAnalyzer(filtered.trades)
        results["pnl"] = pa.summary()

    if "portfolio" in sections:
        porta = PortfolioAnalyzer(
            filtered.open_positions, filtered.trades,
            cash_balances=filtered.cash_balances,
            conversion_rates=filtered.conversion_rates,
            base_currency=filtered.base_currency,
        )
        results["portfolio"] = porta.summary()

    if "cost" in sections:
        ca = CostAnalyzer(filtered.trades, filtered.cash_transactions)
        results["cost"] = ca.summary()

    if "fx" in sections:
        fxa = FxAnalyzer(
            filtered.trades, base_currency=filtered.base_currency,
            conversion_rates=filtered.conversion_rates,
        )
        results["fx"] = fxa.summary()

    if "diluted_cost" in sections:
        dca = DilutedCostAnalyzer(filtered.trades, filtered.open_positions)
        lifo = LifoAnalyzer(filtered.trades, filtered.open_positions)
        results["diluted_cost"] = dca.summary()
        results["lifo"] = lifo.summary()

    if "china_tax" in sections:
        results["china_tax"] = _china_tax_summary(filtered, args)

    return _serialize(results)


def _handle_portfolio(data: AccountData) -> str:
    """Portfolio snapshot."""
    porta = PortfolioAnalyzer(
        data.open_positions, data.trades,
        cash_balances=data.cash_balances,
        conversion_rates=data.conversion_rates,
        base_currency=data.base_currency,
    )
    return _serialize(porta.summary())


def _handle_pnl(data: AccountData) -> str:
    """P&L summary."""
    pa = PnLAnalyzer(data.trades)
    summary = pa.summary()
    summary["equity_curve"] = pa.equity_curve_data()
    return _serialize(summary)


def _handle_trade_patterns(data: AccountData) -> str:
    """Trade patterns."""
    ta = TradeAnalyzer(data.trades)
    return _serialize(ta.summary())


def _handle_fx(data: AccountData) -> str:
    """FX analysis."""
    fxa = FxAnalyzer(
        data.trades, base_currency=data.base_currency,
        conversion_rates=data.conversion_rates,
    )
    return _serialize(fxa.summary())


def _handle_cost(data: AccountData) -> str:
    """Cost analysis."""
    ca = CostAnalyzer(data.trades, data.cash_transactions)
    return _serialize(ca.summary())


def _china_tax_summary(data: AccountData, args: dict[str, Any]) -> dict[str, Any]:
    tax_year = args.get("tax_year")
    if tax_year is None:
        dated = [ct.date_time.year for ct in data.cash_transactions if ct.date_time]
        if not dated:
            raise RuntimeError("tax_year is required when loaded data has no dated cash transactions")
        tax_year = max(dated)
    config = ChinaTaxConfig(
        tax_year=int(tax_year),
        china_iit_dividend_rate=float(args.get("china_iit_dividend_rate", 0.20)),
        china_iit_property_transfer_rate=float(args.get("china_iit_property_transfer_rate", 0.20)),
        include_realized_pnl=bool(args.get("include_realized_pnl", False)),
        realized_pnl_asset_types=tuple(args.get("realized_pnl_asset_types", ["STK"])),
    )
    return ChinaTaxAnalyzer(data, config).summary()


def _handle_china_tax(data: AccountData, args: dict[str, Any]) -> str:
    summary = _china_tax_summary(data, args)
    output_csv = args.get("output_csv")
    if output_csv:
        summary["csv_files"] = _write_china_tax_csv_files(summary["csv_rows"], Path(output_csv))
    return _serialize(summary)


def _write_china_tax_csv_files(csv_rows: dict[str, list[dict[str, Any]]], output_dir: Path) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    files = {}
    for name, rows in csv_rows.items():
        path = output_dir / f"china-tax-{name}.csv"
        fieldnames = sorted({key for row in rows for key in row}) if rows else []
        with path.open("w", newline="", encoding="utf-8") as handle:
            if fieldnames:
                writer = csv.DictWriter(handle, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
        files[name] = str(path)
    return files


def _handle_report(data: AccountData, args: dict[str, Any]) -> str:
    """Generate full reports."""
    import pandas as pd

    output_dir = Path(args.get("output_dir", "reports/"))
    output_dir.mkdir(parents=True, exist_ok=True)

    all_sections = {"trade", "pnl", "portfolio", "cost", "fx", "diluted_cost", "price"}
    sections = set(args.get("sections", [])) or all_sections

    ta = TradeAnalyzer(data.trades) if "trade" in sections else None
    pa = PnLAnalyzer(data.trades) if "pnl" in sections else None
    porta = PortfolioAnalyzer(
        data.open_positions, data.trades,
        cash_balances=data.cash_balances,
        conversion_rates=data.conversion_rates,
        base_currency=data.base_currency,
    ) if "portfolio" in sections else None
    ca = CostAnalyzer(data.trades, data.cash_transactions) if "cost" in sections else None
    dca = DilutedCostAnalyzer(data.trades, data.open_positions) if "diluted_cost" in sections else None
    lifo = LifoAnalyzer(data.trades, data.open_positions) if "diluted_cost" in sections else None
    fxa = FxAnalyzer(
        data.trades, base_currency=data.base_currency,
        conversion_rates=data.conversion_rates,
    ) if "fx" in sections else None

    # Price charts (skip by default in MCP to avoid slow yfinance calls)
    price_charts: list[dict] = []

    rg = ReportGenerator(
        trade_summary=ta.summary() if ta else {},
        pnl_summary=pa.summary() if pa else {},
        portfolio_summary=porta.summary() if porta else {},
        cost_summary=ca.summary() if ca else {},
        diluted_cost_summary=dca.summary() if dca else {},
        lifo_summary=lifo.summary() if lifo else {},
        equity_curve=pa.equity_curve_data() if pa else [],
        trade_df=ta.df if ta else pd.DataFrame(),
        output_dir=output_dir,
        price_charts=price_charts,
        fx_summary=fxa.summary() if fxa else {},
        enabled_sections=sections,
    )

    md_path = rg.write_markdown()
    html_path = rg.write_html()

    return _serialize({
        "status": "ok",
        "markdown_report": str(md_path),
        "html_report": str(html_path),
    })


# --- Entry point ---

async def main():
    async with stdio_server() as (read_stream, write_stream):
        init_options = server.create_initialization_options()
        await server.run(read_stream, write_stream, init_options)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())

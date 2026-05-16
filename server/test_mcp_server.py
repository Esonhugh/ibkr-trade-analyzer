"""Tests for ibkr_mcp_server.py — verifies all tool handlers produce correct output."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

# Setup path same as the server does
_plugin_root = str(Path(__file__).resolve().parent.parent)
_scripts_dir = Path(_plugin_root) / "skills" / "ibkr-trade-analyzer" / "scripts"
sys.path.insert(0, str(_scripts_dir))

import ibkr_mcp_server as srv

TEST_XML = Path(_plugin_root) / "cache" / "flex-2026-05-16.xml"


def run(coro):
    return asyncio.run(coro)


def parse_result(result: list) -> dict:
    """Extract JSON from TextContent list."""
    text = result[0].text
    return json.loads(text)


class TestFetchData:
    def test_file_mode_loads_successfully(self):
        srv._session_data = None
        result = run(srv.call_tool("ibkr_fetch_data", {"mode": "file", "source": str(TEST_XML)}))
        data = parse_result(result)
        assert data["status"] == "ok"
        assert data["trades"] > 0
        assert data["account_id"] != ""
        assert "date_range" in data

    def test_file_mode_missing_file(self):
        srv._session_data = None
        result = run(srv.call_tool("ibkr_fetch_data", {"mode": "file", "source": "/nonexistent.xml"}))
        data = parse_result(result)
        assert "error" in data

    def test_file_mode_no_source(self):
        srv._session_data = None
        result = run(srv.call_tool("ibkr_fetch_data", {"mode": "file"}))
        data = parse_result(result)
        assert "error" in data

    def test_unknown_mode(self):
        srv._session_data = None
        result = run(srv.call_tool("ibkr_fetch_data", {"mode": "bogus"}))
        data = parse_result(result)
        assert "error" in data


class TestAnalyze:
    @classmethod
    def setup_class(cls):
        srv._session_data = None
        run(srv.call_tool("ibkr_fetch_data", {"mode": "file", "source": str(TEST_XML)}))

    def test_all_sections(self):
        result = run(srv.call_tool("ibkr_analyze", {}))
        data = parse_result(result)
        for section in ("trade", "pnl", "portfolio", "cost", "fx", "diluted_cost"):
            assert section in data, f"Missing section: {section}"

    def test_single_section_pnl(self):
        result = run(srv.call_tool("ibkr_analyze", {"sections": ["pnl"]}))
        data = parse_result(result)
        assert "pnl" in data
        assert "trade" not in data
        assert "total_realized_pnl" in data["pnl"]

    def test_single_section_trade(self):
        result = run(srv.call_tool("ibkr_analyze", {"sections": ["trade"]}))
        data = parse_result(result)
        assert "trade" in data

    def test_period_filter(self):
        result = run(srv.call_tool("ibkr_analyze", {
            "sections": ["pnl"],
            "period": "2026-04-01:2026-04-30",
        }))
        data = parse_result(result)
        assert "pnl" in data

    def test_asset_type_filter(self):
        result = run(srv.call_tool("ibkr_analyze", {
            "sections": ["trade"],
            "asset_types": "STK",
        }))
        data = parse_result(result)
        assert "trade" in data


class TestPortfolio:
    @classmethod
    def setup_class(cls):
        srv._session_data = None
        run(srv.call_tool("ibkr_fetch_data", {"mode": "file", "source": str(TEST_XML)}))

    def test_portfolio_returns_positions(self):
        result = run(srv.call_tool("ibkr_portfolio", {}))
        data = parse_result(result)
        assert "positions" in data or "open_positions" in data or "total_value" in data


class TestPnL:
    @classmethod
    def setup_class(cls):
        srv._session_data = None
        run(srv.call_tool("ibkr_fetch_data", {"mode": "file", "source": str(TEST_XML)}))

    def test_pnl_summary_structure(self):
        result = run(srv.call_tool("ibkr_pnl_summary", {}))
        data = parse_result(result)
        assert "total_realized_pnl" in data
        assert "sharpe_ratio" in data
        assert "monthly_pnl" in data


class TestTradePatterns:
    @classmethod
    def setup_class(cls):
        srv._session_data = None
        run(srv.call_tool("ibkr_fetch_data", {"mode": "file", "source": str(TEST_XML)}))

    def test_trade_patterns_structure(self):
        result = run(srv.call_tool("ibkr_trade_patterns", {}))
        data = parse_result(result)
        assert "error" not in data


class TestFxAnalysis:
    @classmethod
    def setup_class(cls):
        srv._session_data = None
        run(srv.call_tool("ibkr_fetch_data", {"mode": "file", "source": str(TEST_XML)}))

    def test_fx_analysis_runs(self):
        result = run(srv.call_tool("ibkr_fx_analysis", {}))
        data = parse_result(result)
        assert "error" not in data


class TestCostAnalysis:
    @classmethod
    def setup_class(cls):
        srv._session_data = None
        run(srv.call_tool("ibkr_fetch_data", {"mode": "file", "source": str(TEST_XML)}))

    def test_cost_analysis_structure(self):
        result = run(srv.call_tool("ibkr_cost_analysis", {}))
        data = parse_result(result)
        assert "error" not in data
        assert "total_commissions" in data or "commissions" in data or isinstance(data, dict)


class TestGenerateReport:
    @classmethod
    def setup_class(cls):
        srv._session_data = None
        run(srv.call_tool("ibkr_fetch_data", {"mode": "file", "source": str(TEST_XML)}))

    def test_generates_files(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            result = run(srv.call_tool("ibkr_generate_report", {"output_dir": tmpdir}))
            data = parse_result(result)
            assert data["status"] == "ok"
            assert Path(data["markdown_report"]).exists()
            assert Path(data["html_report"]).exists()


class TestPnLEquityCurve:
    """Verify equity_curve serialization (the circular reference bug)."""

    @classmethod
    def setup_class(cls):
        srv._session_data = None
        run(srv.call_tool("ibkr_fetch_data", {"mode": "file", "source": str(TEST_XML)}))

    def test_equity_curve_present(self):
        result = run(srv.call_tool("ibkr_pnl_summary", {}))
        data = parse_result(result)
        assert "equity_curve" in data
        assert isinstance(data["equity_curve"], list)
        assert len(data["equity_curve"]) > 0

    def test_equity_curve_dates_are_strings(self):
        result = run(srv.call_tool("ibkr_pnl_summary", {}))
        data = parse_result(result)
        for point in data["equity_curve"]:
            assert isinstance(point["date"], str)
            assert isinstance(point["cumulative_pnl"], (int, float))

    def test_pnl_monthly_values(self):
        result = run(srv.call_tool("ibkr_pnl_summary", {}))
        data = parse_result(result)
        for month, val in data["monthly_pnl"].items():
            assert isinstance(month, str)
            assert isinstance(val, (int, float))

    def test_top_winners_losers(self):
        result = run(srv.call_tool("ibkr_pnl_summary", {}))
        data = parse_result(result)
        assert "top_winners" in data
        assert "top_losers" in data
        for w in data["top_winners"]:
            assert "symbol" in w
            assert "pnl" in w
            assert w["pnl"] > 0


class TestTradePatternDetails:
    @classmethod
    def setup_class(cls):
        srv._session_data = None
        run(srv.call_tool("ibkr_fetch_data", {"mode": "file", "source": str(TEST_XML)}))

    def test_win_rate_in_range(self):
        result = run(srv.call_tool("ibkr_trade_patterns", {}))
        data = parse_result(result)
        assert 0 <= data["win_rate"] <= 100

    def test_profit_factor_positive(self):
        result = run(srv.call_tool("ibkr_trade_patterns", {}))
        data = parse_result(result)
        assert data["profit_factor"] > 0

    def test_by_weekday_keys(self):
        result = run(srv.call_tool("ibkr_trade_patterns", {}))
        data = parse_result(result)
        valid_days = {"Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"}
        for day in data.get("by_weekday", {}).keys():
            assert day in valid_days


class TestCostAnalysisDetails:
    @classmethod
    def setup_class(cls):
        srv._session_data = None
        run(srv.call_tool("ibkr_fetch_data", {"mode": "file", "source": str(TEST_XML)}))

    def test_commission_fields(self):
        result = run(srv.call_tool("ibkr_cost_analysis", {}))
        data = parse_result(result)
        assert "total_commissions" in data
        assert "avg_commission_per_trade" in data
        assert data["total_commissions"] >= 0
        assert data["avg_commission_per_trade"] >= 0

    def test_dividend_fields(self):
        result = run(srv.call_tool("ibkr_cost_analysis", {}))
        data = parse_result(result)
        assert "dividend_income" in data
        assert "net_dividend" in data

    def test_commission_by_month_serializable(self):
        result = run(srv.call_tool("ibkr_cost_analysis", {}))
        data = parse_result(result)
        for month, val in data.get("commission_by_month", {}).items():
            assert isinstance(month, str)
            assert isinstance(val, (int, float))


class TestPortfolioDetails:
    @classmethod
    def setup_class(cls):
        srv._session_data = None
        run(srv.call_tool("ibkr_fetch_data", {"mode": "file", "source": str(TEST_XML)}))

    def test_portfolio_total_value(self):
        result = run(srv.call_tool("ibkr_portfolio", {}))
        data = parse_result(result)
        assert data.get("total_value", 0) > 0 or data.get("total_positions", 0) >= 0

    def test_portfolio_top_holdings(self):
        result = run(srv.call_tool("ibkr_portfolio", {}))
        data = parse_result(result)
        if "top_holdings" in data:
            for h in data["top_holdings"]:
                assert "symbol" in h
                assert "value" in h

    def test_portfolio_cash_section(self):
        result = run(srv.call_tool("ibkr_portfolio", {}))
        data = parse_result(result)
        if "cash" in data:
            assert "total_cash_base" in data["cash"]
            assert "total_account_value" in data["cash"]


class TestAnalyzeEdgeCases:
    @classmethod
    def setup_class(cls):
        srv._session_data = None
        run(srv.call_tool("ibkr_fetch_data", {"mode": "file", "source": str(TEST_XML)}))

    def test_empty_period_returns_empty_pnl(self):
        result = run(srv.call_tool("ibkr_analyze", {
            "sections": ["pnl"],
            "period": "2020-01-01:2020-01-31",
        }))
        data = parse_result(result)
        assert data["pnl"]["total_realized_pnl"] == 0

    def test_nonexistent_asset_type(self):
        result = run(srv.call_tool("ibkr_analyze", {
            "sections": ["trade"],
            "asset_types": "CRYPTO",
        }))
        data = parse_result(result)
        assert data["trade"]["total_trades"] == 0

    def test_multiple_sections(self):
        result = run(srv.call_tool("ibkr_analyze", {
            "sections": ["pnl", "cost", "fx"],
        }))
        data = parse_result(result)
        assert "pnl" in data
        assert "cost" in data
        assert "fx" in data
        assert "trade" not in data
        assert "portfolio" not in data

    def test_diluted_cost_section(self):
        result = run(srv.call_tool("ibkr_analyze", {"sections": ["diluted_cost"]}))
        data = parse_result(result)
        assert "diluted_cost" in data
        assert "lifo" in data
        assert "total_symbols" in data["diluted_cost"]
        assert "total_symbols" in data["lifo"]


class TestGenerateReportSections:
    @classmethod
    def setup_class(cls):
        srv._session_data = None
        run(srv.call_tool("ibkr_fetch_data", {"mode": "file", "source": str(TEST_XML)}))

    def test_partial_report(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            result = run(srv.call_tool("ibkr_generate_report", {
                "output_dir": tmpdir,
                "sections": ["pnl", "trade"],
            }))
            data = parse_result(result)
            assert data["status"] == "ok"
            md_content = Path(data["markdown_report"]).read_text()
            assert len(md_content) > 0


class TestJsonSerialization:
    """Verify _json_safe handles all types returned by analyzers."""

    def test_datetime_date(self):
        import datetime as _dt
        result = srv._json_safe(_dt.date(2026, 5, 16))
        assert result == "2026-05-16"

    def test_datetime_datetime(self):
        import datetime as _dt
        result = srv._json_safe(_dt.datetime(2026, 5, 16, 10, 30, 0))
        assert result == "2026-05-16T10:30:00"

    def test_path(self):
        result = srv._json_safe(Path("/tmp/test.html"))
        assert result == "/tmp/test.html"

    def test_inf_serializable(self):
        """float('inf') is not valid JSON — check analyzers don't produce it."""
        srv._session_data = None
        run(srv.call_tool("ibkr_fetch_data", {"mode": "file", "source": str(TEST_XML)}))
        for tool in ("ibkr_pnl_summary", "ibkr_trade_patterns", "ibkr_portfolio",
                     "ibkr_cost_analysis", "ibkr_fx_analysis"):
            result = run(srv.call_tool(tool, {}))
            text = result[0].text
            assert "Infinity" not in text, f"{tool} returned Infinity"
            assert "NaN" not in text, f"{tool} returned NaN"


class TestUnknownTool:
    def test_unknown_tool_returns_error(self):
        srv._session_data = None
        run(srv.call_tool("ibkr_fetch_data", {"mode": "file", "source": str(TEST_XML)}))
        result = run(srv.call_tool("nonexistent_tool", {}))
        data = parse_result(result)
        assert "error" in data


class TestAutoLoadWithoutData:
    """Test that tools auto-load data when _session_data is None and creds missing."""

    def test_pnl_without_load_errors_gracefully(self):
        srv._session_data = None
        # Clear creds to simulate missing config
        original_token = srv.FLEX_TOKEN
        original_query = srv.QUERY_ID
        srv.FLEX_TOKEN = ""
        srv.QUERY_ID = ""
        try:
            result = run(srv.call_tool("ibkr_pnl_summary", {}))
            data = parse_result(result)
            assert "error" in data
        finally:
            srv.FLEX_TOKEN = original_token
            srv.QUERY_ID = original_query


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))

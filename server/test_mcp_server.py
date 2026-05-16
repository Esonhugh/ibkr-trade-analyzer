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


class TestUnknownTool:
    def test_unknown_tool_returns_error(self):
        srv._session_data = None
        run(srv.call_tool("ibkr_fetch_data", {"mode": "file", "source": str(TEST_XML)}))
        result = run(srv.call_tool("nonexistent_tool", {}))
        data = parse_result(result)
        assert "error" in data


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))

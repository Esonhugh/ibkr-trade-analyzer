from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

_plugin_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_plugin_root / "server"))

import ibkr_mcp_server as srv
from ibkr_analyzer_lib.models import AccountData, CashTransaction, Trade


def run(coro):
    return asyncio.run(coro)


def parse_result(result: list) -> dict:
    return json.loads(result[0].text)


def _sample_data() -> AccountData:
    return AccountData(
        trades=[
            Trade(
                asset_category="CASH",
                symbol="USD.CNH",
                currency="CNH",
                date_time=datetime(2025, 12, 31, 10, 0),
                quantity=1000,
                proceeds=-7000,
            ),
            Trade(
                asset_category="STK",
                symbol="AAPL",
                currency="USD",
                date_time=datetime(2025, 6, 1, 10, 0),
                quantity=10,
                trade_price=100,
                proceeds=-1000,
                buy_sell="BUY",
                realized_pnl=0,
            ),
            Trade(
                asset_category="STK",
                symbol="AAPL",
                currency="USD",
                date_time=datetime(2025, 7, 1, 10, 0),
                quantity=-10,
                trade_price=120,
                proceeds=1200,
                buy_sell="SELL",
                realized_pnl=200,
            ),
        ],
        cash_transactions=[
            CashTransaction(
                date_time=datetime(2025, 3, 1),
                type="Dividends",
                symbol="AAPL",
                currency="USD",
                amount=100,
                description="AAPL dividend",
            ),
            CashTransaction(
                date_time=datetime(2025, 3, 2),
                type="Withholding Tax",
                symbol="AAPL",
                currency="USD",
                amount=-10,
                description="US tax withheld on AAPL dividend",
            ),
        ],
        base_currency="USD",
    )


def setup_function():
    srv._session_data = _sample_data()


def test_lists_china_tax_tool():
    tools = run(srv.list_tools())

    assert "ibkr_china_tax_annual_calc" in {tool.name for tool in tools}


def test_analyze_schema_exposes_china_tax_parameters():
    tools = {tool.name: tool for tool in run(srv.list_tools())}
    properties = tools["ibkr_analyze"].inputSchema["properties"]

    assert "tax_year" in properties
    assert "china_iit_dividend_rate" in properties
    assert "include_realized_pnl" in properties
    assert "realized_pnl_asset_types" in properties
    assert "china_iit_property_transfer_rate" in properties


def test_china_tax_tool_schema_exposes_phase2_realized_pnl_parameters():
    tools = {tool.name: tool for tool in run(srv.list_tools())}
    properties = tools["ibkr_china_tax_annual_calc"].inputSchema["properties"]

    assert "include_realized_pnl" in properties
    assert "realized_pnl_asset_types" in properties
    assert "china_iit_property_transfer_rate" in properties


def test_china_tax_tool_returns_markdown_and_csv_rows():
    result = run(srv.call_tool("ibkr_china_tax_annual_calc", {"tax_year": 2025}))
    data = parse_result(result)

    assert data["status"] == "informational_estimate"
    assert data["china_iit_estimate"][0]["estimated_topup"] == 70
    assert "markdown" in data
    assert data["csv_rows"]["evidence_summary"][0]["source"] == "IBKR Flex"


def test_china_tax_tool_passes_phase2_realized_pnl_parameters():
    result = run(srv.call_tool("ibkr_china_tax_annual_calc", {
        "tax_year": 2025,
        "include_realized_pnl": True,
        "realized_pnl_asset_types": ["STK"],
        "china_iit_property_transfer_rate": 0.25,
    }))
    data = parse_result(result)

    assert data["property_transfer_income_estimate"][0]["ibkr_realized_pnl_original"] == 200
    assert data["property_transfer_income_estimate"][0]["income_rmb"] == 1400
    assert data["property_transfer_income_estimate"][0]["china_rate"] == 0.25
    assert data["property_transfer_income_estimate"][0]["estimated_tax_rmb"] == 350


def test_analyze_china_tax_passes_phase2_realized_pnl_parameters():
    result = run(srv.call_tool("ibkr_analyze", {
        "sections": ["china_tax"],
        "tax_year": 2025,
        "include_realized_pnl": True,
        "realized_pnl_asset_types": ["STK"],
        "china_iit_property_transfer_rate": 0.25,
    }))
    data = parse_result(result)

    estimate = data["china_tax"]["property_transfer_income_estimate"][0]
    assert estimate["ibkr_realized_pnl_original"] == 200
    assert estimate["china_rate"] == 0.25
    assert estimate["estimated_tax_rmb"] == 350


def test_china_tax_tool_writes_csv_files(tmp_path):
    result = run(srv.call_tool("ibkr_china_tax_annual_calc", {
        "tax_year": 2025,
        "output_csv": str(tmp_path),
    }))
    data = parse_result(result)

    evidence_path = Path(data["csv_files"]["evidence_summary"])
    estimate_path = Path(data["csv_files"]["china_iit_estimate"])
    assert evidence_path.exists()
    assert estimate_path.exists()
    assert "IBKR Flex" in evidence_path.read_text()
    assert "estimated_topup" in estimate_path.read_text()


def test_analyze_supports_china_tax_section():
    result = run(srv.call_tool("ibkr_analyze", {"sections": ["china_tax"], "tax_year": 2025}))
    data = parse_result(result)

    assert "china_tax" in data
    assert data["china_tax"]["china_iit_estimate"][0]["creditable_tax"] == 70

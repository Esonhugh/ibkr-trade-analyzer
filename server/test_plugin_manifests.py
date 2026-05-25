"""Plugin manifest checks for Claude Code packaging."""

from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KNOWN_IBKR_MCP_TOOLS = {
    "mcp__plugin_ibkr-trade-analyzer_ibkr-analyzer__ibkr_fetch_data",
    "mcp__plugin_ibkr-trade-analyzer_ibkr-analyzer__ibkr_analyze",
    "mcp__plugin_ibkr-trade-analyzer_ibkr-analyzer__ibkr_portfolio",
    "mcp__plugin_ibkr-trade-analyzer_ibkr-analyzer__ibkr_pnl_summary",
    "mcp__plugin_ibkr-trade-analyzer_ibkr-analyzer__ibkr_trade_patterns",
    "mcp__plugin_ibkr-trade-analyzer_ibkr-analyzer__ibkr_fx_analysis",
    "mcp__plugin_ibkr-trade-analyzer_ibkr-analyzer__ibkr_cost_analysis",
    "mcp__plugin_ibkr-trade-analyzer_ibkr-analyzer__ibkr_china_tax_annual_calc",
    "mcp__plugin_ibkr-trade-analyzer_ibkr-analyzer__ibkr_generate_report",
}


def load_json(relative_path: str) -> dict:
    return json.loads((ROOT / relative_path).read_text())


def test_claude_plugin_manifest() -> None:
    manifest = load_json(".claude-plugin/plugin.json")

    assert manifest["name"] == "ibkr-trade-analyzer"
    assert manifest["version"] == "2.1.0"
    assert manifest["userConfig"]["ibkr_flex_token"]["sensitive"] is True
    assert manifest["userConfig"]["ibkr_query_id"]["required"] is True


def test_claude_marketplace_manifest() -> None:
    marketplace = load_json(".claude-plugin/marketplace.json")

    assert marketplace["name"] == "ibkr-trade-analyzer"
    assert marketplace["metadata"]["version"] == "2.1.0"
    assert marketplace["plugins"][0]["name"] == "ibkr-trade-analyzer"
    assert marketplace["plugins"][0]["source"] == "./"


def test_command_docs_exist() -> None:
    commands_dir = ROOT / "commands"
    expected_commands = {
        "summary.md",
        "portfolio.md",
        "cash-fx.md",
        "report.md",
        "analyze.md",
        "china-tax-annual.md",
        "china-tax-year-end-plan.md",
    }

    assert commands_dir.is_dir()
    assert expected_commands.issubset({path.name for path in commands_dir.glob("*.md")})

    for command_name in expected_commands:
        content = (commands_dir / command_name).read_text()
        lines = content.splitlines()

        assert lines[:1] == ["---"], f"{command_name} is missing opening frontmatter delimiter"
        assert "---" in lines[1:], f"{command_name} is missing closing frontmatter delimiter"

        closing_delimiter_index = lines[1:].index("---") + 1
        frontmatter_lines = lines[1:closing_delimiter_index]
        frontmatter = "\n".join(frontmatter_lines)

        for required_field in ("description:", "argument-hint:", "allowed-tools:"):
            assert required_field in frontmatter, f"{command_name} is missing {required_field} frontmatter"

        allowed_tools_line = next(
            line for line in frontmatter_lines if line.startswith("allowed-tools:")
        )
        allowed_tools = ast.literal_eval(allowed_tools_line.split("allowed-tools:", 1)[1].strip())

        assert isinstance(allowed_tools, list), f"{command_name} allowed-tools must be a list"
        assert set(allowed_tools).issubset(KNOWN_IBKR_MCP_TOOLS), (
            f"{command_name} has unknown allowed-tools: "
            f"{sorted(set(allowed_tools) - KNOWN_IBKR_MCP_TOOLS)}"
        )

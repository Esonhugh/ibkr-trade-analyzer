"""Plugin manifest checks for Claude Code and Codex packaging."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def load_json(relative_path: str) -> dict:
    return json.loads((ROOT / relative_path).read_text())


def test_claude_plugin_manifest() -> None:
    manifest = load_json(".claude-plugin/plugin.json")

    assert manifest["name"] == "ibkr-trade-analyzer"
    assert manifest["version"] == "2.0.0"
    assert manifest["userConfig"]["ibkr_flex_token"]["sensitive"] is True
    assert manifest["userConfig"]["ibkr_query_id"]["required"] is True


def test_claude_marketplace_manifest() -> None:
    marketplace = load_json(".claude-plugin/marketplace.json")

    assert marketplace["name"] == "ibkr-trade-analyzer"
    assert marketplace["metadata"]["version"] == "2.0.0"
    assert marketplace["plugins"][0]["name"] == "ibkr-trade-analyzer"
    assert marketplace["plugins"][0]["source"] == "./"


def test_codex_plugin_manifest() -> None:
    manifest = load_json(".codex-plugin/plugin.json")

    assert manifest["name"] == "ibkr-trade-analyzer"
    assert manifest["version"] == "2.0.0"
    assert manifest["skills"] == "./skills/"
    assert manifest["mcpServers"] == "./.codex-mcp.json"
    assert manifest["interface"]["displayName"] == "IBKR Trade Analyzer"
    assert len(manifest["interface"]["defaultPrompt"]) <= 3
    assert all(len(prompt) <= 128 for prompt in manifest["interface"]["defaultPrompt"])


def test_codex_marketplace_manifest() -> None:
    marketplace = load_json(".agents/plugins/marketplace.json")
    plugin = marketplace["plugins"][0]

    assert marketplace["name"] == "esonhugh-ibkr-trade-analyzer"
    assert plugin["name"] == "ibkr-trade-analyzer"
    assert plugin["source"] == {"source": "local", "path": "./"}
    assert plugin["policy"] == {
        "installation": "AVAILABLE",
        "authentication": "ON_INSTALL",
    }
    assert plugin["category"] == "Finance"


def test_codex_mcp_config() -> None:
    config = load_json(".codex-mcp.json")
    server = config["mcp_servers"]["ibkr-analyzer"]

    assert server["type"] == "stdio"
    assert server["command"] == "bash"
    assert "PLUGIN_ROOT" in server["args"][1]
    assert "CODEX_PLUGIN_ROOT" in server["args"][1]
    assert "CLAUDE_PLUGIN_ROOT" in server["args"][1]
    assert "server/ibkr_mcp_server.py" in server["args"][1]

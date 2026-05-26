# IBKR Analyzer Shared Library Refactor Design

## Scope

This refactor moves reusable IBKR analyzer logic into a stable project-root package named `ibkr_analyzer_lib` and leaves MCP/CLI entry points as thin wrappers. It also removes runtime compatibility with `CODEX_*` environment variables so the plugin uses Claude/plugin host environment names consistently.

The refactor must preserve existing analyzer behavior, report outputs, plugin command packaging, and China tax workflows.

## Goals

- Create `ibkr_analyzer_lib` as the single importable implementation library for models, loading, analyzers, reports, and China tax self-check logic.
- Make `server/ibkr_mcp_server.py` import shared implementation from `ibkr_analyzer_lib` instead of `skills/ibkr-trade-analyzer/scripts`.
- Make `skills/ibkr-trade-analyzer/scripts/ibkr_analyzer.py` a standalone CLI wrapper that keeps its PEP 723 dependency metadata and imports library classes.
- Make `skills/china-tax/scripts/china_tax_self_check.py` a standalone wrapper around `ibkr_analyzer_lib.china_tax_self_check.main`.
- Remove `CODEX_*` root, data, credential, and proxy fallbacks from runtime code.
- Keep plugin docs and packaging tests aligned with the new structure.

## Non-Goals

- Do not delete legacy analyzer implementation files under `skills/ibkr-trade-analyzer/scripts/` in this refactor.
- Do not redesign analyzer APIs, report formats, or China tax calculation semantics.
- Do not change Flex API behavior or credential storage.
- Do not add trading/order execution capabilities.

## Target File Structure

```text
ibkr_analyzer_lib/
├── __init__.py
├── models.py
├── loader.py
├── report.py
├── china_tax_self_check.py
└── analyzers/
    ├── __init__.py
    ├── trade.py
    ├── pnl.py
    ├── portfolio.py
    ├── cost.py
    ├── fx.py
    ├── diluted_cost.py
    ├── lifo.py
    ├── price.py
    └── china_tax.py
```

Wrappers remain at:

```text
server/ibkr_mcp_server.py
skills/ibkr-trade-analyzer/scripts/ibkr_analyzer.py
skills/china-tax/scripts/china_tax_self_check.py
```

## Runtime Import Rules

Library modules must use package imports such as:

```python
from ibkr_analyzer_lib.models import AccountData, Trade
from ibkr_analyzer_lib.analyzers.diluted_cost import DilutedCostAnalyzer
```

Wrappers may insert the project root into `sys.path` only when needed so direct script execution and MCP server imports work from plugin host subprocesses.

Tests should import implementation code from `ibkr_analyzer_lib` or import wrapper modules directly. Tests must not add `skills/ibkr-trade-analyzer/scripts` to `sys.path`.

## Environment Variable Rules

Runtime code may use these root/data names:

```python
_ROOT_ENV_NAMES = ("PLUGIN_ROOT", "CLAUDE_PLUGIN_ROOT")
_DATA_ENV_NAMES = ("PLUGIN_DATA", "CLAUDE_PLUGIN_DATA")
```

Runtime code may use these credential/proxy names:

```python
_FLEX_TOKEN_ENV_NAMES = ("IBKR_FLEX_TOKEN", "CLAUDE_PLUGIN_OPTION_IBKR_FLEX_TOKEN")
_QUERY_ID_ENV_NAMES = ("IBKR_QUERY_ID", "CLAUDE_PLUGIN_OPTION_IBKR_QUERY_ID")
_PROXY_ENV_NAMES = (
    "PROXY",
    "CLAUDE_PLUGIN_OPTION_PROXY",
    "ALL_PROXY",
    "HTTPS_PROXY",
    "HTTP_PROXY",
)
```

No `CODEX_*` names should remain in runtime fallback lists.

## Documentation Updates

Docs that mention implementation paths should describe:

```text
ibkr_analyzer_lib/ — shared implementation library for loaders, models, analyzers, reporting, and China tax self-check logic.
server/ibkr_mcp_server.py — MCP wrapper.
skills/ibkr-trade-analyzer/scripts/ibkr_analyzer.py — standalone analyzer CLI wrapper.
skills/china-tax/scripts/china_tax_self_check.py — China tax self-check CLI wrapper.
```

## Acceptance Tests

Run the focused suite from the plugin root:

```bash
uv run --python 3.14 --with pytest --with mcp --with plotly --with pandas --with numpy --with requests python -m pytest server/test_china_tax_analyzer.py server/test_china_tax_mcp.py server/test_china_tax_self_check.py server/test_mcp_server.py server/test_plugin_manifests.py -q
```

Expected: all selected tests pass.

Run wrapper smoke tests:

```bash
uv run skills/ibkr-trade-analyzer/scripts/ibkr_analyzer.py --help
uv run skills/china-tax/scripts/china_tax_self_check.py --tax-year 2025 --output /tmp/china-tax-self-check-smoke.md
```

Expected: analyzer help prints successfully, and the China tax self-check writes the report path.

## Review Checks

- Runtime MCP server imports from `ibkr_analyzer_lib`.
- Standalone CLIs still run directly via `uv run`.
- Plugin command docs have valid frontmatter and allowed MCP tool names.
- `CODEX_*` references remain only in tests or planning/design docs where they verify or describe the removed compatibility behavior.
- Legacy direct imports under `skills/ibkr-trade-analyzer/scripts/` are acceptable because those files remain as legacy copies outside the active wrappers.

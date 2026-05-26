# IBKR Analyzer Shared Library Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove remaining `CODEX_*` compatibility variables and migrate shared IBKR analyzer logic into a fixed internal library package so MCP and CLI files become thin wrappers.

**Architecture:** Create a project-root Python package named `ibkr_analyzer_lib` as the single home for reusable models, loaders, report generation, analyzers, and China tax self-check logic. Keep existing executable entry points (`server/ibkr_mcp_server.py`, `skills/ibkr-trade-analyzer/scripts/ibkr_analyzer.py`, `skills/china-tax/scripts/china_tax_self_check.py`) as wrappers that add the project root to `sys.path` only when needed, parse entry-point arguments, and call the library. Remove all user-facing and runtime fallback use of `CODEX_*` variables.

**Tech Stack:** Python 3.10+, standard library, existing pytest suite, existing PEP 723 script execution through `uv run`, MCP Python SDK.

---

## File Structure

Create:

- `ibkr_analyzer_lib/__init__.py` — package marker and public package metadata.
- `ibkr_analyzer_lib/models.py` — copied shared dataclasses from `skills/ibkr-trade-analyzer/scripts/models.py`.
- `ibkr_analyzer_lib/loader.py` — copied `DataLoader` with imports changed to package imports.
- `ibkr_analyzer_lib/report.py` — copied `ReportGenerator` with imports changed to package imports.
- `ibkr_analyzer_lib/analyzers/__init__.py` — copied analyzer exports.
- `ibkr_analyzer_lib/analyzers/*.py` — copied analyzer implementations with imports changed to package imports.
- `ibkr_analyzer_lib/china_tax_self_check.py` — shared local-file China tax self-check functions currently in `skills/china-tax/scripts/china_tax_self_check.py`, without CLI parsing.

Modify:

- `server/ibkr_mcp_server.py` — remove `CODEX_*` env names, import shared library package, stop importing from `skills/.../scripts`.
- `skills/ibkr-trade-analyzer/scripts/ibkr_analyzer.py` — wrapper around `ibkr_analyzer_lib` classes.
- `skills/china-tax/scripts/china_tax_self_check.py` — wrapper around `ibkr_analyzer_lib.china_tax_self_check` CLI function.
- `server/test_china_tax_analyzer.py`, `server/test_china_tax_mcp.py`, `server/test_mcp_server.py`, `server/test_china_tax_self_check.py` — import from `ibkr_analyzer_lib` or project-root wrappers instead of skill script paths.
- `skills/ibkr-trade-analyzer/scripts/USAGE.md`, `README.md`, `README-zh.md`, `skills/china-tax/references/official-tax-rules-and-implementation-plan.md` — update paths to mention `ibkr_analyzer_lib` as the implementation library and scripts as wrappers where needed.

Do not delete the old core files under `skills/ibkr-trade-analyzer/scripts/` in this plan. Keep them until all tests and docs pass; wrappers can replace entry-point files only. Avoid destructive cleanup.

---

### Task 1: Remove `CODEX_*` runtime fallback variables

**Files:**
- Modify: `server/ibkr_mcp_server.py`
- Modify: `server/test_mcp_server.py`

- [x] **Step 1: Add a failing test that CODEX root/data env vars are ignored**

Append this test to `server/test_mcp_server.py`:

```python
def test_mcp_server_does_not_use_codex_env_vars(monkeypatch):
    monkeypatch.setenv("CODEX_PLUGIN_ROOT", "/tmp/codex-root-should-not-be-used")
    monkeypatch.setenv("CODEX_PLUGIN_DATA", "/tmp/codex-data-should-not-be-used")
    monkeypatch.delenv("PLUGIN_ROOT", raising=False)
    monkeypatch.delenv("PLUGIN_DATA", raising=False)
    monkeypatch.delenv("CLAUDE_PLUGIN_ROOT", raising=False)
    monkeypatch.delenv("CLAUDE_PLUGIN_DATA", raising=False)

    assert "CODEX_PLUGIN_ROOT" not in srv._ROOT_ENV_NAMES
    assert "CODEX_PLUGIN_DATA" not in srv._DATA_ENV_NAMES
```

- [x] **Step 2: Run the failing test**

Run:

```bash
uv run --with pytest pytest server/test_mcp_server.py::test_mcp_server_does_not_use_codex_env_vars -q
```

Expected: FAIL because `_ROOT_ENV_NAMES` and `_DATA_ENV_NAMES` do not exist yet.

- [x] **Step 3: Define env-name constants and remove CODEX fallbacks**

In `server/ibkr_mcp_server.py`, replace the current plugin root/data env selection and credential env tuples with explicit constants:

```python
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

_plugin_root = _first_env(*_ROOT_ENV_NAMES) or str(Path(__file__).resolve().parent.parent)
_plugin_data = _first_env(*_DATA_ENV_NAMES)

FLEX_TOKEN = _first_env(*_FLEX_TOKEN_ENV_NAMES)
QUERY_ID = _first_env(*_QUERY_ID_ENV_NAMES)
PROXY = _first_env(*_PROXY_ENV_NAMES)
```

Remove every `CODEX_*` string from `server/ibkr_mcp_server.py`.

- [x] **Step 4: Run the targeted test**

Run:

```bash
uv run --with pytest pytest server/test_mcp_server.py::test_mcp_server_does_not_use_codex_env_vars -q
```

Expected: PASS.

- [x] **Step 5: Run the MCP tests**

Run:

```bash
uv run --with pytest pytest server/test_mcp_server.py server/test_china_tax_mcp.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

Do not commit unless the user explicitly asks. If asked:

```bash
git add server/ibkr_mcp_server.py server/test_mcp_server.py
git commit -m "refactor: remove Codex env fallbacks"
```

---

### Task 2: Create `ibkr_analyzer_lib` package from existing core modules

**Files:**
- Create: `ibkr_analyzer_lib/__init__.py`
- Create: `ibkr_analyzer_lib/models.py`
- Create: `ibkr_analyzer_lib/loader.py`
- Create: `ibkr_analyzer_lib/report.py`
- Create: `ibkr_analyzer_lib/analyzers/__init__.py`
- Create: `ibkr_analyzer_lib/analyzers/trade.py`
- Create: `ibkr_analyzer_lib/analyzers/pnl.py`
- Create: `ibkr_analyzer_lib/analyzers/portfolio.py`
- Create: `ibkr_analyzer_lib/analyzers/cost.py`
- Create: `ibkr_analyzer_lib/analyzers/fx.py`
- Create: `ibkr_analyzer_lib/analyzers/diluted_cost.py`
- Create: `ibkr_analyzer_lib/analyzers/lifo.py`
- Create: `ibkr_analyzer_lib/analyzers/price.py`
- Create: `ibkr_analyzer_lib/analyzers/china_tax.py`
- Modify: `server/test_china_tax_analyzer.py`

- [x] **Step 1: Add a failing direct-library import test**

At the top of `server/test_china_tax_analyzer.py`, replace the current `sys.path.insert` + `from analyzers...` imports with:

```python
from ibkr_analyzer_lib.analyzers.china_tax import ChinaTaxAnalyzer, ChinaTaxConfig, MissingFxRateError
from ibkr_analyzer_lib.analyzers.diluted_cost import DilutedCostAnalyzer
from ibkr_analyzer_lib.models import AccountData, CashTransaction, Trade
```

Remove the now-unused `sys` and `_scripts_dir` setup lines from that file.

- [x] **Step 2: Run the failing import test**

Run:

```bash
uv run --with pytest pytest server/test_china_tax_analyzer.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'ibkr_analyzer_lib'`.

- [x] **Step 3: Copy core modules into `ibkr_analyzer_lib`**

Create `ibkr_analyzer_lib/__init__.py`:

```python
"""Shared implementation library for the IBKR Trade Analyzer plugin."""
```

Copy these files exactly first:

```bash
mkdir -p ibkr_analyzer_lib/analyzers
cp skills/ibkr-trade-analyzer/scripts/models.py ibkr_analyzer_lib/models.py
cp skills/ibkr-trade-analyzer/scripts/loader.py ibkr_analyzer_lib/loader.py
cp skills/ibkr-trade-analyzer/scripts/report.py ibkr_analyzer_lib/report.py
cp skills/ibkr-trade-analyzer/scripts/analyzers/*.py ibkr_analyzer_lib/analyzers/
```

- [x] **Step 4: Update imports in copied library files**

In `ibkr_analyzer_lib/loader.py`, replace:

```python
from models import AccountData, CashBalance, CashTransaction, OpenPosition, Trade
```

with:

```python
from ibkr_analyzer_lib.models import AccountData, CashBalance, CashTransaction, OpenPosition, Trade
```

In every `ibkr_analyzer_lib/analyzers/*.py`, replace imports like:

```python
from models import Trade
from models import CashTransaction, Trade
from models import AccountData, CashTransaction, Trade
from analyzers.diluted_cost import DilutedCostAnalyzer
```

with package imports:

```python
from ibkr_analyzer_lib.models import Trade
from ibkr_analyzer_lib.models import CashTransaction, Trade
from ibkr_analyzer_lib.models import AccountData, CashTransaction, Trade
from ibkr_analyzer_lib.analyzers.diluted_cost import DilutedCostAnalyzer
```

In `ibkr_analyzer_lib/report.py`, replace any imports from `models` with `ibkr_analyzer_lib.models`.

- [x] **Step 5: Run the analyzer tests**

Run:

```bash
uv run --with pytest pytest server/test_china_tax_analyzer.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

Do not commit unless the user explicitly asks. If asked:

```bash
git add ibkr_analyzer_lib server/test_china_tax_analyzer.py
git commit -m "refactor: add shared IBKR analyzer library"
```

---

### Task 3: Move MCP server imports to shared library

**Files:**
- Modify: `server/ibkr_mcp_server.py`
- Modify: `server/test_mcp_server.py`
- Modify: `server/test_china_tax_mcp.py`

- [x] **Step 1: Add a failing assertion that MCP server uses the library package**

Add this test to `server/test_mcp_server.py`:

```python
def test_mcp_server_imports_shared_library_models():
    assert srv.DataLoader.__module__ == "ibkr_analyzer_lib.loader"
    assert srv.AccountData.__module__ == "ibkr_analyzer_lib.models"
    assert srv.ChinaTaxAnalyzer.__module__ == "ibkr_analyzer_lib.analyzers.china_tax"
```

- [x] **Step 2: Run the failing test**

Run:

```bash
uv run --with pytest pytest server/test_mcp_server.py::test_mcp_server_imports_shared_library_models -q
```

Expected: FAIL because the MCP server still imports from `skills/ibkr-trade-analyzer/scripts`.

- [x] **Step 3: Update MCP server imports**

In `server/ibkr_mcp_server.py`, remove `_scripts_dir = ...` and `sys.path.insert(0, str(_scripts_dir))`.

Replace:

```python
from analyzers import (
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
from loader import DataLoader
from models import AccountData
from report import ReportGenerator
```

with:

```python
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
```

Keep `sys` only if still needed elsewhere; otherwise remove it.

- [x] **Step 4: Update MCP tests to stop inserting scripts path**

In `server/test_mcp_server.py`, remove:

```python
import sys
_scripts_dir = Path(_plugin_root) / "skills" / "ibkr-trade-analyzer" / "scripts"
sys.path.insert(0, str(_scripts_dir))
```

In `server/test_china_tax_mcp.py`, remove the `sys.path.insert` for `skills/ibkr-trade-analyzer/scripts` if present. Keep the `server` path insertion only if needed to import `ibkr_mcp_server`.

- [x] **Step 5: Run MCP tests**

Run:

```bash
uv run --with pytest pytest server/test_mcp_server.py server/test_china_tax_mcp.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

Do not commit unless the user explicitly asks. If asked:

```bash
git add server/ibkr_mcp_server.py server/test_mcp_server.py server/test_china_tax_mcp.py
git commit -m "refactor: use shared library in MCP server"
```

---

### Task 4: Move standalone analyzer CLI to shared library imports

**Files:**
- Modify: `skills/ibkr-trade-analyzer/scripts/ibkr_analyzer.py`
- Modify: `skills/ibkr-trade-analyzer/scripts/USAGE.md`

- [x] **Step 1: Add a failing CLI smoke test command**

Run the current CLI help command to establish baseline:

```bash
uv run skills/ibkr-trade-analyzer/scripts/ibkr_analyzer.py --help
```

Expected before changes: PASS and output includes `IBKR Trading History Analyzer`.

Then temporarily change imports in `ibkr_analyzer.py` in the next step; the failing condition will be caught if project root is not on `sys.path`.

- [x] **Step 2: Update `ibkr_analyzer.py` wrapper imports**

At the top of `skills/ibkr-trade-analyzer/scripts/ibkr_analyzer.py`, after standard imports, add:

```python
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))
```

Replace:

```python
from analyzers import CostAnalyzer, DilutedCostAnalyzer, FxAnalyzer, LifoAnalyzer, PnLAnalyzer, PortfolioAnalyzer, PriceAnalyzer, TradeAnalyzer
from loader import DataLoader
from report import ReportGenerator
```

with:

```python
from ibkr_analyzer_lib.analyzers import CostAnalyzer, DilutedCostAnalyzer, FxAnalyzer, LifoAnalyzer, PnLAnalyzer, PortfolioAnalyzer, PriceAnalyzer, TradeAnalyzer
from ibkr_analyzer_lib.loader import DataLoader
from ibkr_analyzer_lib.report import ReportGenerator
```

- [x] **Step 3: Run CLI help**

Run:

```bash
uv run skills/ibkr-trade-analyzer/scripts/ibkr_analyzer.py --help
```

Expected: PASS and output includes `IBKR Trading History Analyzer`.

- [x] **Step 4: Update usage docs**

In `skills/ibkr-trade-analyzer/scripts/USAGE.md`, update the module overview tree to show:

```text
ibkr_analyzer_lib/
├── models.py
├── loader.py
├── report.py
└── analyzers/
```

and state that `skills/ibkr-trade-analyzer/scripts/ibkr_analyzer.py` is the CLI wrapper.

- [x] **Step 5: Run targeted tests**

Run:

```bash
uv run --with pytest pytest server/test_plugin_manifests.py -q
uv run skills/ibkr-trade-analyzer/scripts/ibkr_analyzer.py --help
```

Expected: both PASS.

- [ ] **Step 6: Commit**

Do not commit unless the user explicitly asks. If asked:

```bash
git add skills/ibkr-trade-analyzer/scripts/ibkr_analyzer.py skills/ibkr-trade-analyzer/scripts/USAGE.md
git commit -m "refactor: make analyzer CLI a library wrapper"
```

---

### Task 5: Move China tax self-check core into shared library

**Files:**
- Create: `ibkr_analyzer_lib/china_tax_self_check.py`
- Modify: `skills/china-tax/scripts/china_tax_self_check.py`
- Modify: `server/test_china_tax_self_check.py`

- [x] **Step 1: Change tests to import shared library module**

In `server/test_china_tax_self_check.py`, replace path setup and imports:

Remove:

```python
import sys
CHINA_TAX_SCRIPTS = ROOT / "skills" / "china-tax" / "scripts"
sys.path.insert(0, str(CHINA_TAX_SCRIPTS))
import china_tax_self_check
from china_tax_self_check import (...)
```

Use:

```python
from ibkr_analyzer_lib import china_tax_self_check
from ibkr_analyzer_lib.china_tax_self_check import (
    TaxEvidenceItem,
    build_markdown_report,
    calculate_iit_estimate,
    extract_flex_evidence,
    inspect_ibkr_tax_zip,
    load_1042s_csv,
    load_fx_rates_csv,
)

CHINA_TAX_SCRIPT = ROOT / "skills" / "china-tax" / "scripts" / "china_tax_self_check.py"
```

Update subprocess CLI tests to use `CHINA_TAX_SCRIPT` instead of `CHINA_TAX_SCRIPTS / "china_tax_self_check.py"`.

- [x] **Step 2: Run the failing test**

Run:

```bash
uv run --with pytest pytest server/test_china_tax_self_check.py -q
```

Expected: FAIL with `ModuleNotFoundError` or missing `ibkr_analyzer_lib.china_tax_self_check`.

- [x] **Step 3: Create shared China tax self-check module**

Copy the non-wrapper contents of `skills/china-tax/scripts/china_tax_self_check.py` into `ibkr_analyzer_lib/china_tax_self_check.py`.

In the copied module, remove `_ibkr_scripts_dir()` and `_load_data_loader()` path manipulation. Replace them with:

```python
from ibkr_analyzer_lib.loader import DataLoader
```

Update `extract_flex_evidence`:

```python
def extract_flex_evidence(path: Path, tax_year: int) -> dict[str, object]:
    account = DataLoader.from_file(str(path))
    ...
```

Keep `parse_args()` and `main()` in the shared module so the wrapper can call `main()`.

- [x] **Step 4: Replace skill script with wrapper**

Replace `skills/china-tax/scripts/china_tax_self_check.py` with:

```python
#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from ibkr_analyzer_lib.china_tax_self_check import main


if __name__ == "__main__":
    raise SystemExit(main())
```

- [x] **Step 5: Run self-check tests**

Run:

```bash
uv run --with pytest pytest server/test_china_tax_self_check.py -q
```

Expected: PASS.

- [x] **Step 6: Run CLI help/path smoke test**

Run:

```bash
uv run skills/china-tax/scripts/china_tax_self_check.py --tax-year 2025 --output /tmp/china-tax-self-check-smoke.md
```

Expected: PASS, output includes `Wrote China tax self-check report: /tmp/china-tax-self-check-smoke.md`, and the file exists.

- [ ] **Step 7: Commit**

Do not commit unless the user explicitly asks. If asked:

```bash
git add ibkr_analyzer_lib/china_tax_self_check.py skills/china-tax/scripts/china_tax_self_check.py server/test_china_tax_self_check.py
git commit -m "refactor: move China tax self-check core to shared library"
```

---

### Task 6: Update docs and verify no stale imports or CODEX references remain

**Files:**
- Modify: `README.md`
- Modify: `README-zh.md`
- Modify: `skills/ibkr-trade-analyzer/SKILL.md`
- Modify: `skills/china-tax/SKILL.md`
- Modify: `skills/china-tax/references/official-tax-rules-and-implementation-plan.md`
- Modify: `skills/ibkr-trade-analyzer/scripts/USAGE.md`

- [x] **Step 1: Update docs to describe the shared library**

In docs that mention implementation paths, use:

```text
ibkr_analyzer_lib/ — shared implementation library for loaders, models, analyzers, reporting, and China tax self-check logic.
server/ibkr_mcp_server.py — MCP wrapper.
skills/ibkr-trade-analyzer/scripts/ibkr_analyzer.py — standalone analyzer CLI wrapper.
skills/china-tax/scripts/china_tax_self_check.py — China tax self-check CLI wrapper.
```

- [x] **Step 2: Search for stale CODEX references**

Run:

```bash
grep -RIn "Codex\|codex\|CODEX" . --exclude-dir=.git --exclude-dir=.pytest_cache --exclude-dir=__pycache__ --exclude-dir=cache --exclude-dir=reports
```

Expected: no output.

If output remains in `server/ibkr_mcp_server.py`, remove the `CODEX_*` env names from constants and tests. Do not remove unrelated historical generated files outside this plugin.

- [x] **Step 3: Search for stale direct script imports**

Run:

```bash
grep -RIn "sys.path.insert\|from loader\|from models\|from analyzers\|import loader\|import models" . --include='*.py' --exclude-dir=.git --exclude-dir=.pytest_cache --exclude-dir=__pycache__ --exclude-dir=cache --exclude-dir=reports
```

Expected remaining matches only in wrapper files where project root is inserted:

- `skills/ibkr-trade-analyzer/scripts/ibkr_analyzer.py`
- `skills/china-tax/scripts/china_tax_self_check.py`

No tests or MCP server should insert the old skill scripts directory.

- [x] **Step 4: Run final targeted tests**

Run:

```bash
uv run --with pytest pytest server/test_china_tax_analyzer.py server/test_china_tax_mcp.py server/test_china_tax_self_check.py server/test_mcp_server.py server/test_plugin_manifests.py -q
```

Expected: PASS.

- [x] **Step 5: Run wrapper smoke tests**

Run:

```bash
uv run skills/ibkr-trade-analyzer/scripts/ibkr_analyzer.py --help
uv run skills/china-tax/scripts/china_tax_self_check.py --tax-year 2025 --output /tmp/china-tax-self-check-smoke.md
```

Expected: both PASS.

- [ ] **Step 6: Commit**

Do not commit unless the user explicitly asks. If asked:

```bash
git add README.md README-zh.md skills/ibkr-trade-analyzer/SKILL.md skills/china-tax/SKILL.md skills/china-tax/references/official-tax-rules-and-implementation-plan.md skills/ibkr-trade-analyzer/scripts/USAGE.md
git commit -m "docs: document shared analyzer library"
```

---

## Self-Review

Spec coverage:

- Remove remaining `CODEX_*` compatibility variables: Task 1 and Task 6 grep verification.
- Introduce fixed shared library directory: Task 2 creates `ibkr_analyzer_lib`.
- Make MCP and external scripts wrappers: Tasks 3, 4, and 5.
- Preserve existing functionality and tests: each task includes targeted tests; Task 6 runs full relevant suite.
- Library directory name: fixed as `ibkr_analyzer_lib`, matching the approved design.

Placeholder scan:

- No `TBD`, `TODO`, or unspecified implementation steps remain.
- Every code-changing task includes exact file paths and concrete code/import transformations.
- Every verification step includes exact command and expected result.

Type consistency:

- `DataLoader`, `AccountData`, `ChinaTaxAnalyzer`, and `ChinaTaxConfig` move under `ibkr_analyzer_lib` consistently.
- China tax self-check exports keep existing function/class names so tests and wrappers can migrate without API redesign.
- Entry point wrappers use project root insertion only; library modules use package imports.

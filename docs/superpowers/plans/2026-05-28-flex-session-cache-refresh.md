# Flex Session Cache Refresh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make MCP session data reusable only when it was loaded on the current local day, and add `/ibkr-trade-analyzer:portfolio --ff` for forced Flex refresh.

**Architecture:** Keep the existing two-layer cache design: in-memory session first, then today's XML cache, then Flex API. Add one timestamp field and one freshness helper in `server/ibkr_mcp_server.py`; keep command behavior documented in `commands/portfolio.md`.

**Tech Stack:** Python 3.10+, MCP stdio server, pytest, Markdown command frontmatter.

---

## File Structure

- Modify `server/ibkr_mcp_server.py`
  - Add `time` import.
  - Add `_session_loaded_at` module state.
  - Add `_is_session_cache_fresh()` helper.
  - Update `_load_data()` to reuse session only when loaded today and to timestamp successful loads.
- Modify `server/test_mcp_server.py`
  - Add focused tests for stale session miss, force refresh bypass, and successful load timestamping.
- Modify `commands/portfolio.md`
  - Add `--ff` to argument hints.
  - Document force-fresh workflow.
- Modify `server/test_plugin_manifests.py`
  - Add a command documentation test ensuring `portfolio.md` documents `--ff` and `force_refresh=true`.

---

### Task 1: Add failing server cache freshness tests

**Files:**
- Modify: `server/test_mcp_server.py:9`
- Modify: `server/test_mcp_server.py:460-477`
- Test: `server/test_mcp_server.py`

- [ ] **Step 1: Write failing tests for stale session and timestamp behavior**

In `server/test_mcp_server.py`, change the import at line 9 from:

```python
from datetime import datetime
```

to:

```python
from datetime import datetime, timedelta
```

Then add this test class before `class TestAutoLoadWithoutData:`:

```python
class TestSessionCacheFreshness:
    def setup_method(self):
        srv._session_data = None
        srv._session_loaded_at = None

    def test_stale_session_loads_todays_cache(self, monkeypatch, tmp_path):
        stale_data = srv.AccountData(account_id="STALE")
        fresh_data = srv.AccountData(account_id="FRESH")
        srv._session_data = stale_data
        srv._session_loaded_at = (datetime.now() - timedelta(days=1)).timestamp()

        today = datetime.now().strftime("%Y-%m-%d")
        cached_xml = tmp_path / f"flex-{today}.xml"
        cached_xml.write_text("<FlexStatement />", encoding="utf-8")

        monkeypatch.setattr(srv, "FLEX_TOKEN", "token")
        monkeypatch.setattr(srv, "QUERY_ID", "query")
        monkeypatch.setattr(srv, "_data_dir", lambda: tmp_path)
        monkeypatch.setattr(srv.DataLoader, "from_file", lambda path, fmt=None: fresh_data)

        def fail_from_flex(*args, **kwargs):
            raise AssertionError("stale session should load today's XML cache before Flex API")

        monkeypatch.setattr(srv.DataLoader, "from_flex", fail_from_flex)

        result = srv._load_data(mode="flex")

        assert result is fresh_data
        assert srv._session_data is fresh_data
        assert srv._data_source_info == f"Loaded from cache: {cached_xml.name}"

    def test_force_refresh_bypasses_fresh_session_and_updates_timestamp(self, monkeypatch, tmp_path):
        session_data = srv.AccountData(account_id="SESSION")
        fresh_data = srv.AccountData(account_id="FRESH")
        fake_now = datetime.now().replace(hour=12, minute=0, second=0, microsecond=0).timestamp()
        srv._session_data = session_data
        srv._session_loaded_at = fake_now

        monkeypatch.setattr(srv, "FLEX_TOKEN", "token")
        monkeypatch.setattr(srv, "QUERY_ID", "query")
        monkeypatch.setattr(srv, "_data_dir", lambda: tmp_path)
        monkeypatch.setattr(srv.time, "time", lambda: fake_now + 60)
        monkeypatch.setattr(srv.DataLoader, "from_flex", lambda *args, **kwargs: fresh_data)

        result = srv._load_data(mode="flex", force_refresh=True)

        assert result is fresh_data
        assert srv._session_data is fresh_data
        assert srv._session_loaded_at == fake_now + 60
        assert srv._data_source_info == f"Fetched from Flex API ({datetime.now().strftime('%Y-%m-%d')})"

    def test_file_mode_updates_session_timestamp(self, monkeypatch):
        loaded_data = srv.AccountData(account_id="FILE")
        fake_now = datetime.now().replace(hour=13, minute=0, second=0, microsecond=0).timestamp()

        monkeypatch.setattr(srv.time, "time", lambda: fake_now)
        monkeypatch.setattr(srv.DataLoader, "from_file", lambda source: loaded_data)

        result = srv._load_data(mode="file", source="/tmp/activity.xml")

        assert result is loaded_data
        assert srv._session_data is loaded_data
        assert srv._session_loaded_at == fake_now
        assert srv._data_source_info == "Loaded from file: /tmp/activity.xml"
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run:

```bash
python -m pytest server/test_mcp_server.py::TestSessionCacheFreshness -v
```

Expected: FAIL before implementation. At least one failure should mention `AttributeError: module 'ibkr_mcp_server' has no attribute '_session_loaded_at'` or `AttributeError: module 'ibkr_mcp_server' has no attribute 'time'`, or the stale-session test should fail because stale `_session_data` was returned.

- [ ] **Step 3: Commit the failing tests**

```bash
git add server/test_mcp_server.py
git commit -m "test: cover flex session cache freshness"
```

---

### Task 2: Implement date-aware session freshness

**Files:**
- Modify: `server/ibkr_mcp_server.py:21-26`
- Modify: `server/ibkr_mcp_server.py:77-100`
- Modify: `server/ibkr_mcp_server.py:96-136`
- Test: `server/test_mcp_server.py`

- [ ] **Step 1: Add `time` import**

In `server/ibkr_mcp_server.py`, change the imports near the top from:

```python
import csv
import json
import os
import sys
from datetime import datetime
```

to:

```python
import csv
import json
import os
import sys
import time
from datetime import datetime
```

- [ ] **Step 2: Add session timestamp state and freshness helper**

Replace the session state block:

```python
# --- Session state ---
_session_data: AccountData | None = None
_data_source_info: str = ""
```

with:

```python
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
```

- [ ] **Step 3: Use freshness helper in `_load_data()` and timestamp successful loads**

In `server/ibkr_mcp_server.py`, replace the full `_load_data()` function with:

```python
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
```

- [ ] **Step 4: Run the focused cache freshness tests**

Run:

```bash
python -m pytest server/test_mcp_server.py::TestSessionCacheFreshness -v
```

Expected: PASS. The stale session test should load the fake daily XML cache, force refresh should call the fake Flex loader, and file mode should record the fake timestamp.

- [ ] **Step 5: Run existing server tests that rely on cached session state**

Run:

```bash
python -m pytest server/test_mcp_server.py -v
```

Expected: PASS. Existing file-mode setup and tool calls should continue to work with `_session_loaded_at` present.

- [ ] **Step 6: Commit the implementation**

```bash
git add server/ibkr_mcp_server.py server/test_mcp_server.py
git commit -m "fix: refresh stale flex session cache by date"
```

---

### Task 3: Document portfolio `--ff` and test command documentation

**Files:**
- Modify: `commands/portfolio.md:1-13`
- Modify: `server/test_plugin_manifests.py:108-147`
- Test: `server/test_plugin_manifests.py`

- [ ] **Step 1: Add a failing documentation test**

In `server/test_plugin_manifests.py`, add this test after `test_command_docs_exist()`:

```python
def test_portfolio_command_documents_force_fresh_flag() -> None:
    content = (ROOT / "commands" / "portfolio.md").read_text()

    assert "--ff" in content
    assert 'ibkr_fetch_data(mode="flex", force_refresh=true)' in content
```

- [ ] **Step 2: Run the new documentation test to verify it fails**

Run:

```bash
python -m pytest server/test_plugin_manifests.py::test_portfolio_command_documents_force_fresh_flag -v
```

Expected: FAIL because `commands/portfolio.md` does not yet mention `--ff` or `force_refresh=true`.

- [ ] **Step 3: Update portfolio command frontmatter and workflow**

Replace `commands/portfolio.md` lines 1-13 with:

```markdown
---
description: "Calculate IBKR portfolio holdings, allocation, concentration, cash, and position sizing"
argument-hint: "[--mode=flex|file] [--source=/path/activity.xml] [--asset-types=STK,OPT] [--ff]"
allowed-tools: ["mcp__plugin_ibkr-trade-analyzer_ibkr-analyzer__ibkr_fetch_data", "mcp__plugin_ibkr-trade-analyzer_ibkr-analyzer__ibkr_portfolio", "mcp__plugin_ibkr-trade-analyzer_ibkr-analyzer__ibkr_analyze"]
---

Review IBKR portfolio structure using read-only reporting data.

## Workflow

1. Ensure data is loaded:
   - If the user provided `--ff`, call `ibkr_fetch_data(mode="flex", force_refresh=true)`.
   - If the user provided a local file, call `ibkr_fetch_data(mode="file", source="<path>")`.
   - Otherwise call `ibkr_fetch_data(mode="flex")`.
2. Call `ibkr_portfolio` for the full snapshot.
3. If the user requested asset-type filtering, call `ibkr_analyze(sections=["portfolio"], asset_types="<types>")`.
```

- [ ] **Step 4: Run the documentation test**

Run:

```bash
python -m pytest server/test_plugin_manifests.py::test_portfolio_command_documents_force_fresh_flag -v
```

Expected: PASS.

- [ ] **Step 5: Run all manifest checks**

Run:

```bash
python -m pytest server/test_plugin_manifests.py -v
```

Expected: PASS. The command frontmatter should still contain `description:`, `argument-hint:`, and `allowed-tools:`, and all allowed tools should remain known.

- [ ] **Step 6: Commit the command update**

```bash
git add commands/portfolio.md server/test_plugin_manifests.py
git commit -m "feat: add portfolio force refresh flag"
```

---

### Task 4: Final verification

**Files:**
- Verify: `server/ibkr_mcp_server.py`
- Verify: `server/test_mcp_server.py`
- Verify: `commands/portfolio.md`
- Verify: `server/test_plugin_manifests.py`

- [ ] **Step 1: Run server and manifest test suites**

Run:

```bash
python -m pytest server/test_mcp_server.py server/test_plugin_manifests.py -v
```

Expected: PASS for all tests in both files.

- [ ] **Step 2: Check git diff for intended scope only**

Run:

```bash
git diff -- server/ibkr_mcp_server.py server/test_mcp_server.py commands/portfolio.md server/test_plugin_manifests.py
```

Expected: diff only includes session timestamp freshness logic, tests for that logic, `portfolio --ff` command docs, and the docs test.

- [ ] **Step 3: Check working tree status**

Run:

```bash
git status --short
```

Expected: no unexpected files. If implementation commits were created, the working tree should be clean except for any uncommitted plan/spec docs intentionally left for the current workflow.

- [ ] **Step 4: Report verification evidence**

Summarize:

```text
Implemented date-aware Flex session cache refresh and portfolio --ff documentation.
Verification:
- python -m pytest server/test_mcp_server.py server/test_plugin_manifests.py -v: PASS
```

---

## Self-Review

- Spec coverage: date-aware session cache is covered by Task 2; stale-session miss, force-refresh bypass, and timestamp updates are covered by Tasks 1-2; portfolio `--ff` is covered by Task 3; final verification is covered by Task 4.
- Placeholder scan: no TBD/TODO/fill-in-later steps remain; every code change includes concrete code.
- Type consistency: `_session_loaded_at` is consistently `float | None`; `_is_session_cache_fresh(now: float | None = None)` uses local dates; command docs use `force_refresh=true` exactly as tested.

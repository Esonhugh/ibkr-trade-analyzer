# Flex Session Cache Refresh Design

## Goal

Make IBKR Flex session caching date-aware. A loaded MCP session should reuse in-memory data only when that data was loaded on the current local day. If the session data is older than today, the next flex load should treat the session cache as missed, then try the normal daily XML cache before making one Flex API request.

Also add a portfolio command shortcut: `/ibkr-trade-analyzer:portfolio --ff` should force a fresh Flex fetch by calling `ibkr_fetch_data(mode="flex", force_refresh=true)`.

## Current Behavior

`server/ibkr_mcp_server.py::_load_data()` stores loaded account data in `_session_data`. If `_session_data` is set and `force_refresh` is false, `_load_data()` returns it immediately. This means a long-lived MCP server can keep using yesterday's in-memory data even when today's XML cache or Flex API data is available.

Flex mode already has a second cache layer: today's XML file in the plugin cache directory. If no in-memory session is reused, `_load_data(mode="flex")` checks today's `flex-YYYY-MM-DD.xml` or `*-flex-ibkr-YYYY-MM-DD.xml` before calling `DataLoader.from_flex()`.

## Design

### Session freshness metadata

Add a module-level timestamp:

```python
_session_loaded_at: float | None = None
```

Update it with `time.time()` whenever `_load_data()` successfully loads data into `_session_data`, whether the source is today's XML cache, Flex API, or explicit file mode.

### Freshness rule

Add a helper that compares local calendar dates:

```python
def _is_session_cache_fresh(now: float | None = None) -> bool:
    if _session_data is None or _session_loaded_at is None:
        return False
    current = datetime.fromtimestamp(now or time.time()).date()
    loaded = datetime.fromtimestamp(_session_loaded_at).date()
    return loaded == current
```

The session cache is reusable only when:

- `_session_data` exists;
- `force_refresh` is false;
- `_is_session_cache_fresh()` is true.

If the session cache is stale, `_load_data(mode="flex")` continues into the existing flex path. That path first checks today's XML cache, then calls the Flex API only if today's XML is absent or `force_refresh=True`.

### Force-refresh behavior

Keep current `force_refresh` semantics: it bypasses both in-memory session reuse and today's XML cache. In flex mode it should call `DataLoader.from_flex()` and overwrite the expected `flex-YYYY-MM-DD.xml` dump path.

### File mode behavior

Explicit file mode still loads the requested file and records `_session_loaded_at`. The date-aware session freshness rule is generic, but it does not automatically switch file mode data to flex data. A caller only gets flex refresh behavior when it calls `_load_data(mode="flex")` directly or when an analysis tool auto-loads because no reusable session data is present.

## Portfolio command change

Update `commands/portfolio.md`:

- Add `--ff` to `argument-hint`.
- Document that `--ff` means force fresh Flex data.
- In the workflow, if `--ff` is present, call `ibkr_fetch_data(mode="flex", force_refresh=true)` before `ibkr_portfolio`.
- Without `--ff`, keep the existing default `ibkr_fetch_data` flow.

## Data flow

```text
ibkr_fetch_data(mode="flex") or auto-load from analysis tool
  -> _load_data(mode="flex", force_refresh=false)
  -> if in-memory session was loaded today: return _session_data
  -> otherwise check today's XML cache
  -> if today's XML exists: load XML into _session_data and timestamp it
  -> otherwise call DataLoader.from_flex(), parse XML, timestamp session
```

For `/portfolio --ff`:

```text
portfolio command sees --ff
  -> ibkr_fetch_data(mode="flex", force_refresh=true)
  -> bypass session and XML cache
  -> DataLoader.from_flex()
  -> ibkr_portfolio
```

## Error handling

No new external error states are introduced. If stale session data exists but credentials are missing and no fresh flex load can happen, the existing credential error remains visible. The stale session should not silently mask that error, because the request is now asking for current-day data.

## Tests

Add or update server tests for:

1. Fresh session reuse: `_session_loaded_at` is today, `_session_data` exists, `force_refresh=False`; `_load_data()` returns existing data without loading file/API.
2. Stale session miss: `_session_loaded_at` is yesterday; `_load_data(mode="flex")` does not return stale data and continues to the flex cache/API path.
3. Force refresh bypass: `_session_loaded_at` is today but `force_refresh=True`; `_load_data(mode="flex")` does not return session data.
4. Successful load timestamp: file mode or flex cache load updates `_session_loaded_at`.

Update command tests or manifest checks if they validate argument hints or workflow text for `commands/portfolio.md`.

## Out of scope

- No configurable TTL beyond the local calendar-day freshness check.
- No background refresh.
- No automatic retry loop beyond existing Flex polling.
- No changes to credential storage or Flex API endpoints.

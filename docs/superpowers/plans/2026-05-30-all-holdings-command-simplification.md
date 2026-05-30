# All Holdings and Command Simplification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace portfolio `top_holdings` with sorted `all_holdings`, and simplify the `report` and `summary` slash command instructions.

**Architecture:** The analyzer remains the source of truth for holdings output. MCP handlers keep passing analyzer summaries through unchanged, while report rendering and command docs consume the renamed field. The duplicated standalone script copies under `skills/ibkr-trade-analyzer/scripts/` must stay in sync with `ibkr_analyzer_lib`.

**Tech Stack:** Python 3.10+, pytest, MCP server stdio tools, Claude Code plugin command markdown.

---

## File Structure

- Modify: `ibkr_analyzer_lib/analyzers/portfolio.py`
  - Replace the structured summary field `top_holdings` with `all_holdings`.
  - Preserve per-symbol aggregation and sort by descending portfolio percentage.
- Modify: `skills/ibkr-trade-analyzer/scripts/analyzers/portfolio.py`
  - Mirror the shared analyzer change for the standalone plugin script copy.
- Modify: `ibkr_analyzer_lib/report.py`
  - Replace report consumers of `top_holdings` with `all_holdings`.
  - Rename headings from top-only wording to all-holdings wording where the table renders all rows.
  - Keep charts/risk/style using the full `all_holdings` list unless a display slice already exists for non-holdings sections.
- Modify: `skills/ibkr-trade-analyzer/scripts/report.py`
  - Mirror the report changes for the standalone script copy.
- Modify: `server/test_mcp_server.py`
  - Add regression coverage proving `ibkr_portfolio` exposes `all_holdings` and omits `top_holdings`.
  - Add a unit-level synthetic portfolio test proving all holdings are sorted by descending `pct` and all rows are returned.
- Modify: `commands/portfolio.md`
  - Update slash command output instructions from Top Positions to All Holdings.
- Modify: `commands/report.md`
  - Simplify workflow and output guidance while preserving tool usage and guardrails.
- Modify: `commands/summary.md`
  - Simplify workflow and output guidance while preserving tool usage and guardrails.

## Task 1: Add failing tests for all_holdings contract

**Files:**
- Modify: `server/test_mcp_server.py`
- Test: `server/test_mcp_server.py`

- [ ] **Step 1: Add imports for synthetic portfolio test**

At the top of `server/test_mcp_server.py`, change the existing import block from:

```python
from datetime import datetime, timedelta
from pathlib import Path
```

to:

```python
from datetime import datetime, timedelta
from pathlib import Path

from ibkr_analyzer_lib.analyzers.portfolio import PortfolioAnalyzer
from ibkr_analyzer_lib.models import OpenPosition
```

- [ ] **Step 2: Replace the existing portfolio top-holdings MCP test**

In `server/test_mcp_server.py`, replace the body of `TestPortfolioDetails.test_portfolio_top_holdings` with this renamed test:

```python
    def test_portfolio_all_holdings_contract(self):
        result = run(srv.call_tool("ibkr_portfolio", {}))
        data = parse_result(result)
        assert "all_holdings" in data
        assert "top_holdings" not in data
        for h in data["all_holdings"]:
            assert "symbol" in h
            assert "value" in h
            assert "pct" in h
```

- [ ] **Step 3: Add a synthetic unit test for full sorted holdings**

Append this new test class after `TestPortfolioDetails` in `server/test_mcp_server.py`:

```python
class TestPortfolioAnalyzerHoldingsContract:
    def test_all_holdings_returns_every_symbol_sorted_by_pct_desc(self):
        positions = [
            OpenPosition(symbol="SMALL", asset_category="STK", quantity=1, position_value=100),
            OpenPosition(symbol="LARGE", asset_category="STK", quantity=1, position_value=300),
            OpenPosition(symbol="MEDIUM", asset_category="STK", quantity=1, position_value=200),
        ]

        summary = PortfolioAnalyzer(positions, []).summary()

        assert "all_holdings" in summary
        assert "top_holdings" not in summary
        assert [h["symbol"] for h in summary["all_holdings"]] == ["LARGE", "MEDIUM", "SMALL"]
        assert [round(h["pct"], 2) for h in summary["all_holdings"]] == [50.0, 33.33, 16.67]
```

- [ ] **Step 4: Run the focused tests and verify they fail**

Run:

```bash
pytest server/test_mcp_server.py::TestPortfolioDetails::test_portfolio_all_holdings_contract server/test_mcp_server.py::TestPortfolioAnalyzerHoldingsContract::test_all_holdings_returns_every_symbol_sorted_by_pct_desc -q
```

Expected: FAIL because current code still returns `top_holdings` and does not return `all_holdings`.

## Task 2: Replace portfolio top_holdings with all_holdings

**Files:**
- Modify: `ibkr_analyzer_lib/analyzers/portfolio.py:42-66`
- Modify: `skills/ibkr-trade-analyzer/scripts/analyzers/portfolio.py:42-66`
- Test: `server/test_mcp_server.py`

- [ ] **Step 1: Update shared portfolio analyzer output**

In `ibkr_analyzer_lib/analyzers/portfolio.py`, replace the `top_holdings` list in `summary()` with `all_holdings` and remove the `[:10]` slice:

```python
            "all_holdings": [
                {
                    "symbol": s,
                    "value": v,
                    "pct": v / total_value * 100,
                    "quantity": next((p.quantity for p in self.positions if p.symbol == s), 0),
                    "cost_basis": next((p.cost_basis_price for p in self.positions if p.symbol == s), 0),
                    "unrealized_pnl": next((p.unrealized_pnl for p in self.positions if p.symbol == s), 0),
                }
                for s, v in sorted_symbols
            ],
```

The concentration metrics stay unchanged:

```python
        top5_pct = sum(v for _, v in sorted_symbols[:5]) / total_value * 100
        top10_pct = sum(v for _, v in sorted_symbols[:10]) / total_value * 100
```

- [ ] **Step 2: Update standalone portfolio analyzer copy**

Make the same replacement in `skills/ibkr-trade-analyzer/scripts/analyzers/portfolio.py`:

```python
            "all_holdings": [
                {
                    "symbol": s,
                    "value": v,
                    "pct": v / total_value * 100,
                    "quantity": next((p.quantity for p in self.positions if p.symbol == s), 0),
                    "cost_basis": next((p.cost_basis_price for p in self.positions if p.symbol == s), 0),
                    "unrealized_pnl": next((p.unrealized_pnl for p in self.positions if p.symbol == s), 0),
                }
                for s, v in sorted_symbols
            ],
```

- [ ] **Step 3: Run focused holdings tests and verify they pass**

Run:

```bash
pytest server/test_mcp_server.py::TestPortfolioDetails::test_portfolio_all_holdings_contract server/test_mcp_server.py::TestPortfolioAnalyzerHoldingsContract::test_all_holdings_returns_every_symbol_sorted_by_pct_desc -q
```

Expected: PASS.

## Task 3: Update report consumers to all_holdings

**Files:**
- Modify: `ibkr_analyzer_lib/report.py`
- Modify: `skills/ibkr-trade-analyzer/scripts/report.py`
- Test: `server/test_mcp_server.py`

- [ ] **Step 1: Replace shared report field lookups and holdings labels**

In `ibkr_analyzer_lib/report.py`, replace every `self.port_s.get("top_holdings", [])` and `pa.get("top_holdings", [])` lookup with `all_holdings`:

```python
holdings = self.port_s.get("all_holdings", [])
```

or, in the markdown portfolio section:

```python
                holdings = pa.get("all_holdings", [])
                if holdings:
                    s += ["### All Holdings\n",
                          "| Symbol | Qty | Cost Basis | Market Value | Unrealized P&L | % |",
                          "|--------|-----|-----------|-------------|----------------|---|"]
```

Also update the chart title at the existing concentration chart from:

```python
fig.update_layout(title="Top Holdings: Concentration & Unrealized P&L", template="plotly_white", height=400, showlegend=False)
```

to:

```python
fig.update_layout(title="Holdings: Concentration & Unrealized P&L", template="plotly_white", height=400, showlegend=False)
```

- [ ] **Step 2: Replace standalone report field lookups and holdings labels**

Make the same changes in `skills/ibkr-trade-analyzer/scripts/report.py`:

```python
holdings = self.port_s.get("all_holdings", [])
```

```python
                holdings = pa.get("all_holdings", [])
                if holdings:
                    s += ["### All Holdings\n",
                          "| Symbol | Qty | Cost Basis | Market Value | Unrealized P&L | % |",
                          "|--------|-----|-----------|-------------|----------------|---|"]
```

```python
fig.update_layout(title="Holdings: Concentration & Unrealized P&L", template="plotly_white", height=400, showlegend=False)
```

- [ ] **Step 3: Search for stale top_holdings references**

Run:

```bash
grep -RIn "top_holdings\|Top Holdings" ibkr_analyzer_lib server commands skills/ibkr-trade-analyzer --exclude-dir=__pycache__
```

Expected: no stale references remain, except historical docs if any are intentionally outside this change. If command docs still contain them, complete Task 4 before the final verification.

## Task 4: Update command markdown files

**Files:**
- Modify: `commands/portfolio.md`
- Modify: `commands/report.md`
- Modify: `commands/summary.md`

- [ ] **Step 1: Update portfolio command output contract**

In `commands/portfolio.md`, replace the output section with:

```markdown
## Output Format

Return Markdown with these sections:

1. **Portfolio Snapshot** — base currency, position count, cash balance count, and total value when available.
2. **All Holdings** — table of every holding sorted by portfolio percentage from largest to smallest.
3. **Allocation** — asset class, long/short, sector, and currency allocation when present.
4. **Concentration Review** — largest position share, top-5 share, and risk score when available.
5. **Position Sizing Notes** — neutral observations about oversize, illiquid, or concentrated positions.
```

- [ ] **Step 2: Simplify report command**

Replace the body of `commands/report.md` after frontmatter with:

```markdown
Generate Markdown and HTML IBKR analysis reports from read-only reporting data.

## Workflow

1. Load data with `ibkr_fetch_data` using the requested mode/source, or Flex by default.
2. Call `ibkr_generate_report`, passing `sections` and `output_dir` only when the user supplied them.
3. Return the generated Markdown and HTML paths.

## Output Format

- **Report Generated** — Markdown path and HTML path.
- **Included Sections** — requested sections, or `all default sections`.
- **Next Step** — suggest opening the HTML for charts or the Markdown for notes.

## Guardrails

- Do not claim files were generated unless `ibkr_generate_report` returns `status: ok` and paths.
- If generation fails, show the exact error and the smallest next diagnostic step.
```

- [ ] **Step 3: Simplify summary command**

Replace the body of `commands/summary.md` after frontmatter with:

```markdown
Generate a concise IBKR account summary using read-only reporting data.

## Workflow

1. Load data with `ibkr_fetch_data` using the requested mode/source, or Flex by default.
2. Call `ibkr_pnl_summary`, `ibkr_portfolio`, and `ibkr_cost_analysis`.
3. Call `ibkr_trade_patterns` only if the user asks for behavior/style detail.

## Output Format

- **Executive Summary** — 5 bullets maximum.
- **Key Metrics** — compact table for available P&L, drawdown, Sharpe, positions, cash, and fees.
- **Portfolio & Costs** — concentration, cash/currency exposure, commissions, interest, and dividends.
- **Watch Items** — up to 3 neutral review items, not trade instructions.

## Guardrails

- State that this is informational analysis, not investment or tax advice.
- Show exact tool errors and the next setup/diagnostic step.
- Do not invent missing account totals or metrics.
```

## Task 5: Final verification

**Files:**
- Verify all modified files.

- [ ] **Step 1: Run focused tests**

Run:

```bash
pytest server/test_mcp_server.py::TestPortfolioDetails::test_portfolio_all_holdings_contract server/test_mcp_server.py::TestPortfolioAnalyzerHoldingsContract::test_all_holdings_returns_every_symbol_sorted_by_pct_desc -q
```

Expected: PASS.

- [ ] **Step 2: Run full server test file**

Run:

```bash
pytest server/test_mcp_server.py -q
```

Expected: PASS.

- [ ] **Step 3: Verify no stale portfolio top-holdings contract remains**

Run:

```bash
grep -RIn "top_holdings\|Top Holdings" ibkr_analyzer_lib server commands skills/ibkr-trade-analyzer --exclude-dir=__pycache__
```

Expected: no output.

- [ ] **Step 4: Verify all_holdings appears in the expected files**

Run:

```bash
grep -RIn "all_holdings\|All Holdings" ibkr_analyzer_lib server commands skills/ibkr-trade-analyzer --exclude-dir=__pycache__
```

Expected: references in portfolio analyzers, reports, command docs, and tests.

- [ ] **Step 5: Review git diff**

Run:

```bash
git diff -- ibkr_analyzer_lib/analyzers/portfolio.py skills/ibkr-trade-analyzer/scripts/analyzers/portfolio.py ibkr_analyzer_lib/report.py skills/ibkr-trade-analyzer/scripts/report.py server/test_mcp_server.py commands/portfolio.md commands/report.md commands/summary.md
```

Expected: diff only contains the holdings contract replacement, report consumers, command simplification, and regression tests.

## Self-Review

- Spec coverage: Plan covers replacing `top_holdings` with sorted full `all_holdings`, updating report consumers, simplifying `report` and `summary` commands, updating portfolio command docs, and testing the new contract.
- Placeholder scan: No placeholders remain; every code and command step includes concrete content.
- Type consistency: The new field name is consistently `all_holdings`; existing holding item fields remain `symbol`, `value`, `pct`, `quantity`, `cost_basis`, and `unrealized_pnl`.

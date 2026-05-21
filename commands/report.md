---
description: "Generate full IBKR Markdown and HTML analysis reports"
argument-hint: "[--mode=flex|file] [--source=/path/activity.xml] [--sections=pnl,portfolio,cost,fx] [--output-dir=reports/]"
allowed-tools: ["mcp__plugin_ibkr-trade-analyzer_ibkr-analyzer__ibkr_fetch_data", "mcp__plugin_ibkr-trade-analyzer_ibkr-analyzer__ibkr_generate_report", "mcp__plugin_ibkr-trade-analyzer_ibkr-analyzer__ibkr_pnl_summary", "mcp__plugin_ibkr-trade-analyzer_ibkr-analyzer__ibkr_portfolio"]
---

Generate complete IBKR analysis report files from read-only reporting data.

## Workflow

1. Ensure data is loaded with `ibkr_fetch_data`.
2. If the user supplied sections, pass them to `ibkr_generate_report(sections=[...])`.
3. If the user supplied an output directory, pass it as `output_dir`.
4. After report generation, call `ibkr_pnl_summary` and `ibkr_portfolio` only when a short chat summary is useful.

## Output Format

Return Markdown with these sections:

1. **Report Generated** — Markdown path and HTML path from the tool output.
2. **Included Sections** — list the requested sections or say `all default sections`.
3. **Quick Readout** — 3 bullets with the most important findings when summary tools were called.
4. **Next Steps** — suggest opening the HTML for charts and the Markdown for copying into notes.

## Guardrails

- Do not claim a report exists unless `ibkr_generate_report` returns `status: ok` and file paths.
- If generation fails, show the error exactly and recommend the smallest next diagnostic step.

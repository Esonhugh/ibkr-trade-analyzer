---
description: "Generate full IBKR Markdown and HTML analysis reports"
argument-hint: "[--mode=flex|file] [--source=/path/activity.xml] [--sections=pnl,portfolio,cost,fx] [--output-dir=reports/]"
allowed-tools: ["mcp__plugin_ibkr-trade-analyzer_ibkr-analyzer__ibkr_fetch_data", "mcp__plugin_ibkr-trade-analyzer_ibkr-analyzer__ibkr_generate_report", "mcp__plugin_ibkr-trade-analyzer_ibkr-analyzer__ibkr_pnl_summary", "mcp__plugin_ibkr-trade-analyzer_ibkr-analyzer__ibkr_portfolio"]
---

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

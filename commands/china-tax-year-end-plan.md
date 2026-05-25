---
description: Review IBKR portfolio and tax evidence for year-end China resident overseas investment tax planning considerations
argument-hint: "[tax year] [optional planning focus]"
allowed-tools: ["mcp__plugin_ibkr-trade-analyzer_ibkr-analyzer__ibkr_fetch_data", "mcp__plugin_ibkr-trade-analyzer_ibkr-analyzer__ibkr_portfolio", "mcp__plugin_ibkr-trade-analyzer_ibkr-analyzer__ibkr_cost_analysis", "mcp__plugin_ibkr-trade-analyzer_ibkr-analyzer__ibkr_pnl_summary", "mcp__plugin_ibkr-trade-analyzer_ibkr-analyzer__ibkr_analyze"]
---

Use the `china-tax` skill as the primary official-source evidence and tax-planning workflow reference.

Generate a year-end tax planning review for China resident overseas brokerage activity. Focus on documentation, evidence gaps, foreign tax credit readiness, withholding sanity checks, cost-basis quality, and scenario modeling. This is not final tax or investment advice.

## Workflow

1. Consult `skills/china-tax/references/official-tax-rules-and-implementation-plan.md` for official-source rules, overseas income management considerations, foreign tax credit constraints, and planning guardrails.
2. Determine the tax year and planning focus from `$ARGUMENTS`; if absent, ask one clarifying question before choosing a tax year.
3. Confirm or state the user-provided assumption that the review is for a China tax resident individual; do not determine residency independently.
4. Recheck official-source freshness for the relevant tax year, or flag the reference date as a limitation.
5. Load current IBKR data:
   - If the user provided a local file path, call `ibkr_fetch_data(mode="file", source="<path>")`.
   - Otherwise call `ibkr_fetch_data(mode="flex")`.
6. Call:
   - `ibkr_portfolio` for current holdings, cash, concentration, and currency exposure.
   - `ibkr_cost_analysis` for dividends, withholding tax, interest, fees, and tax-evidence readiness.
   - `ibkr_pnl_summary` for realized P&L context.
   - `ibkr_analyze(sections=["diluted_cost"])` if cost basis or breakeven quality is important.
5. Separate observations into:
   - Evidence readiness
   - Foreign tax credit readiness
   - Treaty withholding sanity checks
   - Cost-basis / tax-lot review
   - Year-end scenario modeling items
6. Phrase every planning item as a neutral review point, not a buy/sell or filing directive.

## Script Usage

When the user provides local evidence files, use planning mode in `skills/china-tax/scripts/china_tax_self_check.py`:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/china-tax/scripts/china_tax_self_check.py" \
  --tax-year 2025 \
  --flex-file "/path/to/flex.xml" \
  --fx-rates "/path/to/fx-rates.csv" \
  --tax-report-zip "/path/to/2025 税务报告.zip" \
  --planning \
  --output "reports/china-tax-year-end-plan-2025.md"
```

Quote all paths because tax report paths may contain spaces.

## Output Format

Return Markdown with these sections:

1. **Scope & Assumptions** — tax year, data source, user-provided residency assumption, official-source freshness, and limitations; state this is not tax or investment advice.
2. **Evidence Readiness** — missing or useful documents such as 1042-S, annual statements, Flex exports, RMB FX source, cost-basis support.
3. **Income & Withholding Review** — dividends, withholding tax, interest, fees, and treaty-rate sanity checks when available.
4. **Realized / Unrealized Position Review** — realized P&L context and positions that may require tax-lot/cost-basis review; no trading instructions.
5. **Foreign Tax Credit Readiness** — country/category grouping, credit-limit issues, excess tax carryforward review.
6. **Year-End Planning Checklist** — neutral actions to review with a tax professional.

## Guardrails

- State that the output is planning support, not tax filing advice or investment advice.
- Do not recommend buying, selling, realizing gains/losses, or changing positions as a directive.
- Do not invent missing tax records, cost basis, or FX rates.
- Do not provide tax evasion, concealment, or false reporting advice.

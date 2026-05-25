---
description: Generate an annual China resident overseas investment tax evidence review and informational calculation from IBKR Flex data
argument-hint: "[tax year] [optional local IBKR activity file]"
allowed-tools: ["mcp__plugin_ibkr-trade-analyzer_ibkr-analyzer__ibkr_fetch_data", "mcp__plugin_ibkr-trade-analyzer_ibkr-analyzer__ibkr_china_tax_annual_calc", "mcp__plugin_ibkr-trade-analyzer_ibkr-analyzer__ibkr_cost_analysis", "mcp__plugin_ibkr-trade-analyzer_ibkr-analyzer__ibkr_pnl_summary"]
---

Use the `china-tax` skill as the primary official-source evidence and calculation workflow reference.

Generate a China resident annual overseas investment tax evidence review and informational calculation. This is not final filing advice.

## Workflow

1. Consult `skills/china-tax/references/official-tax-rules-and-implementation-plan.md` for official-source rules, treaty references, foreign tax credit method, RMB conversion caveats, and guardrails.
2. Determine the tax year from `$ARGUMENTS`; if absent, ask one clarifying question.
3. Confirm or state the user-provided assumption that the calculation is for a China tax resident individual; do not determine residency independently.
4. Ensure IBKR data is loaded:
   - If the user provided a local file path, call `ibkr_fetch_data(mode="file", source="<path>")`.
   - Otherwise call `ibkr_fetch_data(mode="flex")`.
5. Filter and reconcile evidence to the selected tax year; mark out-of-year records separately.
6. Call `ibkr_china_tax_annual_calc(tax_year=<year>)` for the Phase 1 IBKR Flex dividend/withholding estimate using IBKR FX evidence.
7. Call `ibkr_cost_analysis` only when extra fee, interest, or dividend reconciliation detail is needed.
8. Call `ibkr_pnl_summary` only if the user explicitly requests realized gain planning; do not include realized gains in the Phase 1 dividend/withholding estimate by default.
9. If official 1042-S reconciliation is needed, mark it as a manual review item outside the Phase 1 automated calculator. Do not invent RMB rates.
10. Produce Markdown using the `china-tax` output templates:
   - Evidence Summary
   - China IIT Estimate
   - Treaty Withholding Sanity Check
   - Missing Inputs / Review Required
   - Filing Support Checklist

## Guardrails

- State that the output is an informational estimate and evidence organizer, not tax filing advice.
- Recommend confirmation with a qualified tax professional or competent tax authority before filing.
- Recheck official-source freshness for the selected tax year when the user is preparing an actual filing.
- Do not state final tax payable as definitive.
- Mark unsupported or ambiguous categories as `review_required`.
- Keep U.S. withholding/treaty sanity checks separate from China IIT foreign tax credit calculation.
- Do not recommend tax evasion, concealment, or false reporting.

---
name: china-tax
description: Use for China tax-resident individual overseas brokerage evidence questions, especially IBKR Flex dividends, U.S. withholding tax, foreign tax credit, RMB FX evidence, 美股分红预扣税, 境外所得抵免, 年度报税工具, and year-end China tax planning. Use as an official-source workflow reference, not final filing advice.
version: 0.1.0
---

# China Tax Reference and Planning for Overseas Brokerage Data

Prepare official-source evidence reviews, informational annual China individual income tax estimates, and year-end planning reviews for China tax residents using IBKR/Flex data first. Focus on overseas income management, foreign tax credit, treaty withholding sanity checks, RMB conversion assumptions, filing evidence, and tax-planning review items.

## Safety Boundary

- Provide informational estimates, evidence organization, and planning checklists only; never state a final tax payable amount or filing position as definitive.
- Recommend confirmation with a qualified tax professional or competent tax authority before filing.
- Do not determine China tax residency conclusively; use only explicit user-provided residency assumptions and mark them for review.
- Recheck official sources and effective dates for the relevant tax year before relying on rules or forms.
- Treat default rates such as 20% for dividend estimates as configurable assumptions, not final law application.
- Do not invent missing 1042-S amounts, brokerage gross income, withholding tax, country allocation, income category, cost basis, realized gains, or RMB exchange rates.
- Keep U.S. treaty withholding checks separate from China IIT calculation.
- Mark ambiguous or unsupported tax treatment as `review_required`.
- Do not provide tax evasion, concealment, false reporting, or illegal avoidance advice.

## Reference First

Consult `references/official-tax-rules-and-implementation-plan.md` before answering detailed calculation, treaty, overseas-income management, CRS, foreign-tax-credit, or implementation questions. It contains official-source links, rule summaries, formulas, output tables, a web-app pattern review, and a staged implementation plan.

## Current Capability

Handle these tasks as research, design, evidence preparation, and manual estimate workflows:

1. Explain how Form 1042-S, brokerage data, China resident IIT, treaty withholding, and foreign tax credit fit together.
2. Build evidence tables from loaded IBKR Flex cash transactions.
3. Draft annual filing calculation workflows for dividends, withholding tax, and later-phase 1042-S reconciliation or realized gains.
4. Produce year-end planning reviews that identify evidence gaps, possible withholding-rate issues, tax-lot/cost-basis issues, currency assumptions, and timing considerations.
5. Produce implementation plans for deterministic code and tests.

The automated `ibkr_china_tax_annual_calc` MCP tool supports Phase 1 IBKR Flex U.S. dividend/withholding estimates using same-tax-year IBKR USD/RMB FX trade evidence. 1042-S reconciliation, activity-statement reconciliation beyond loaded Flex cash transactions, realized gains, options, derivatives, cost basis, and non-USD dividends remain manual/review-required.

## Annual Filing Calculation Workflow

Use this workflow for annual reporting / 年度报税工具 requests:

1. Clarify tax year, residency assumption, brokerage source, and available documents.
2. Load IBKR data when available with `ibkr_fetch_data`; call `ibkr_china_tax_annual_calc` for Phase 1 dividend, withholding, RMB conversion, and foreign-tax-credit estimates.
3. Mark 1042-S reconciliation as a manual review item when official tax-form reconciliation is required.
4. Require same-tax-year IBKR USD/RMB FX trade evidence before producing automated RMB amounts; do not present it as an official SAFE/PBOC/state-tax exchange-rate determination.
5. Compute only categories with explicit data and assumptions.
6. Return evidence summary, China IIT estimate, treaty sanity check, missing inputs, and filing support checklist.

Start Phase 1 with U.S.-source dividends and withholding tax. Defer realized securities gains, options, complex derivatives, and FX gain/loss unless the user explicitly asks for planning treatment.

## Year-End Tax Planning Workflow

Use this workflow for 年前税务优化建议 / year-end planning requests:

1. Load current portfolio, realized P&L, dividends, withholding, cash, FX, and cost-basis data when available.
2. Separate compliance evidence issues from planning observations.
3. Identify review items: missing 1042-S, unexpected withholding rates, missing historical statements, missing cost basis, concentrated unrealized gains/losses, and FX conversion assumptions.
4. Provide neutral planning scenarios, not instructions to trade. Phrase items as “review”, “confirm”, “model”, or “ask a tax professional”.
5. Avoid recommending tax-loss harvesting or transaction timing as a directive; present only calculation impacts and documentation needs.

## Output Templates

### Evidence Summary

| Source | Tax year | Country | Income type | Gross original | Tax withheld original | Currency | Notes |
|---|---:|---|---|---:|---:|---|---|

### China IIT Estimate

| Country | Category | Income RMB | China rate | China tax before credit | Foreign tax paid RMB | Creditable tax | Estimated top-up | Excess carryforward |
|---|---|---:|---:|---:|---:|---:|---:|---:|

### Treaty Withholding Sanity Check

| Country | Income type | Gross | Withheld | Actual rate | Treaty reference | Review note |
|---|---|---:|---:|---:|---|---|

### Year-End Planning Review

| Area | Evidence / metric | Review point | Possible next step |
|---|---|---|---|

## Implementation Planning Guidance

When asked to implement commands or calculators, follow test-first development:

- Add deterministic pure functions for dividend/withholding aggregation, RMB translation, treaty sanity checks, and foreign tax credit calculation.
- Require failing fixture tests before implementation.
- Start with dividend/withholding Phase 1.
- Add realized-gain and cost-basis support only after brokerage fixtures are validated.
- Preserve evidence records in output rather than only returning totals.

## Additional Resources

- `references/official-tax-rules-and-implementation-plan.md` — official-source rule summary, formulas, web-app pattern review, output tables, and staged implementation plan.

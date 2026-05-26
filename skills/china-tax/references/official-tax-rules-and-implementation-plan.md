# China Tax Annual Calculation Reference for Overseas Brokerage Data

Last reviewed: 2026-05-24. Recheck official IRS, State Taxation Administration, and treaty sources for the relevant tax year before preparing an actual filing.

Implementation status: Phase 1 dividend/withholding calculator exists; Phase 2 STK realized-gain support is implemented as an opt-in evidence/estimate workflow with IBKR realized P&L primary口径 and FIFO/diluted comparisons. Advanced realized-gain tax treatment beyond STK, options/derivatives, corporate-action hazards, and final filing positions remain review-required.

This reference summarizes official-source rules and implementation guidance for China resident overseas-investment tax evidence workflows. It is a tax-data preparation and calculation reference, not legal, tax, or investment advice. Always label output as an informational estimate and recommend confirmation with a qualified tax professional or the competent tax authority before filing.

## Official Source Baseline

### U.S. Form 1042-S

Use the IRS About Form 1042-S page as the durable entry point. Treat specific instruction PDFs, such as the 2025 instructions, as year-specific sources that must be rechecked for the filing year.

- IRS describes Form 1042-S as reporting income and withholding for foreign persons receiving U.S.-source payments.
- Use Form 1042-S as evidence of U.S.-source income and U.S. federal tax withheld, especially dividends and similar withholding-tax items.
- Treat 1042-S as a withholding certificate, not as a complete China resident annual tax calculation. It usually does not cover all realized securities gains, all non-U.S. income, or China RMB conversion requirements.

Official references:
- IRS About Form 1042-S: https://www.irs.gov/forms-pubs/about-form-1042-s
- 2025 IRS Instructions for Form 1042-S PDF: https://www.irs.gov/pub/irs-pdf/i1042s--2025.pdf

### U.S.–China Income Tax Treaty

- IRS treaty page links the 1984 U.S.–China income tax treaty and technical explanation.
- Treaty entered into force in 1986 and generally became effective from 1987.
- Article 10, Dividends: source-state tax on dividends paid to a resident of the other contracting state is capped at 10% of the gross dividend amount when treaty conditions apply.
- Article 11, Interest: source-state tax on interest paid to a resident of the other contracting state is capped at 10% of the gross interest amount when treaty conditions apply.
- Treaty reduced rates do not apply where the income is effectively connected with a permanent establishment or fixed base in the source state; then the treaty business/professional article can control.
- IRS Publication 901 notes the U.S.–China treaty does not apply to Hong Kong.

Official references:
- IRS China tax treaty documents: https://www.irs.gov/businesses/international-businesses/china-tax-treaty-documents
- U.S.–China income tax treaty PDF: https://www.irs.gov/pub/irs-trty/china.pdf
- IRS Tax Treaty Tables: https://www.irs.gov/individuals/international-taxpayers/tax-treaty-tables
- IRS Publication 901: https://www.irs.gov/publications/p901

### China Individual Income Tax Law

- Article 1: a resident individual is subject to China individual income tax on income derived from both inside and outside China.
- Article 7: for foreign-source income, individual income tax paid overseas may be credited against China tax payable, but the credit cannot exceed the China tax payable on that foreign-source income.

Official references:
- State Taxation Administration Individual Income Tax Law: https://www.chinatax.gov.cn/chinatax/n810219/n810744/n3752930/n3752974/c3970366/content.html
- 12366 Individual Income Tax Law mirror: https://12366.chinatax.gov.cn/bzds/069/069-5-1.html

### China IIT Implementing Regulations

- Article 21: resident individuals may credit foreign individual income tax paid overseas; credit limits are calculated by country/region, combining comprehensive income, business income, and other income credit limits for the same country/region.
- Article 21: foreign tax paid above the country/region credit limit may be carried forward to later years for the same country/region; carryforward period cannot exceed five years.
- Article 32: non-RMB income is converted using the RMB central parity rate on the last day of the previous month for withholding or declaration.
- Article 32: for annual settlement, foreign-currency income that has already been prepaid monthly/quarterly/per occurrence is not re-translated; tax payable on unpaid portions uses the last day of the previous tax year RMB central parity rate.

Official reference:
- State Taxation Administration IIT Implementing Regulations: https://www.chinatax.gov.cn/n810219/n810744/n3752930/n3752974/c3963364/content.html

### Overseas Income IIT Policy Announcement

The Ministry of Finance and State Taxation Administration announcement on overseas income provides investment-relevant rules:

- Overseas income categories include interest, dividends, bonus income; property transfer income; incidental income; and other categories.
- Resident individuals with overseas income should declare and pay tax from March 1 to June 30 of the following year.
- Foreign tax credit is computed against a credit limit. If actual foreign tax is lower than the limit, credit actual foreign tax. If actual foreign tax is higher than the limit, credit up to the limit and carry excess forward for five tax years.
- Non-creditable foreign taxes include taxes paid in error, taxes not payable under treaties, penalties and late fees, refunded or compensated taxes, and taxes related to exempt income.
- Exchange conversion follows the IIT Implementing Regulations Article 32.

Official references:
- STA policy announcement on overseas income IIT: https://www.chinatax.gov.cn/chinatax/n810219/n810744/n3752930/n3752974/c5143076/content.html
- STA policy database explanation: https://fgk.chinatax.gov.cn/zcfgk/c100024/c5236736/content.html

### Foreign Income Tax Credit Detail Form

- The official “境外所得个人所得税抵免明细表” is used by resident individuals with overseas income to report foreign income and calculate foreign tax credit details.
- The form separates income categories such as comprehensive income, business income, interest/dividends/bonus income, lease income, transfer income, incidental income, equity incentives, and other income.
- The calculation compares current-year credit limit and foreign tax paid, then derives current-year creditable tax and carryforward amounts.

Official references:
- 12366 foreign income IIT credit detail form: https://12366.chinatax.gov.cn/bzds/082/082.html
- Shanghai Tax Bureau form/instructions page: https://shanghai.chinatax.gov.cn/tax/bsfw/xzzx/bgxz/sbzsl/202302/t466192.html

## Calculation Scope for `china-tax-annual-calc`

Start with an annual calculation for China tax residents holding overseas brokerage accounts, with IBKR as the first supported brokerage. Keep the skill usable as a general overseas-tax-management reference while requiring broker-specific parsers for actual calculations.

### Phase 1 Scope

Implement these categories first:

1. U.S.-source dividends from IBKR Flex cash transactions as the primary data source.
2. U.S. federal withholding tax from IBKR Flex withholding-tax cash transactions as the primary data source.
3. China IIT estimate for interest/dividends/bonus income using a configurable rate, default 20% for estimate only.
4. Foreign tax credit limit and estimated China top-up tax for dividends.
5. RMB translation using auditable FX evidence; Phase 1 can use same-tax-year IBKR USD/RMB FX trade evidence when available, without silently inventing rates.
6. Markdown and CSV output for evidence review.
7. 1042-S is optional follow-up reconciliation/evidence check, not a required Phase 1 input.

### Phase 2 Scope

Implemented as an opt-in STK-only evidence/estimate workflow:

1. Realized stock gains as property transfer income candidates using IBKR realized P&L as the primary口径.
2. Security-by-security FIFO and diluted/breakeven comparison rows for review.
3. Review-required records for losses, non-STK realized P&L, non-USD gains, missing FX evidence, and incomplete lot history.

Still future work:

1. Country/region credit-limit grouping beyond current dividend/withholding estimate outputs.
2. Excess foreign tax carryforward schedule.
3. 1042-S PDF/text import or manual 1042-S CSV reconciliation if reliable extraction is available.
4. Annual tax package generation matching “境外所得个人所得税抵免明细表” columns.

## Data Mapping

### IBKR Flex / Activity Fields

Map available IBKR data into tax categories:

| IBKR data | Tax calculation use | Notes |
|---|---|---|
| Dividends | Interest/dividends/bonus income | Use gross dividend where available. |
| Withholding tax | Foreign tax paid | Separate by country/source when possible. |
| Interest income/expense | Interest income or financing cost review | Treaty and China category treatment require confirmation. |
| Realized P&L | Property transfer income candidate | Opt-in Phase 2 STK evidence/estimate only; avoid assuming final filing treatment. |
| Commissions | Cost/expense evidence | Treatment depends on category and filing practice. |
| FX conversions | Evidence for currency movement | Do not treat all FX movements as taxable without explicit design. |
| Cash balances | Reconciliation | Not income by itself. |

### 1042-S Fields

Map 1042-S fields where available:

| 1042-S field concept | Use |
|---|---|
| Tax year | Annual calculation year |
| Income code | Income category mapping |
| Gross income | U.S.-source payment amount; foreign-source only from the China resident filing perspective |
| Chapter 3 tax withheld / federal tax withheld | Foreign tax paid candidate |
| Tax rate | Treaty/rate sanity check |
| Recipient country | Treaty/country grouping evidence |

## Core Formulas

### Dividend IIT Estimate

For each country/region and income category:

```text
china_tax_before_credit_rmb = taxable_income_rmb * china_iit_rate
foreign_tax_paid_rmb = translated foreign withholding tax
creditable_foreign_tax_rmb = min(foreign_tax_paid_rmb, china_tax_before_credit_rmb)
estimated_china_topup_rmb = max(china_tax_before_credit_rmb - creditable_foreign_tax_rmb, 0)
excess_foreign_tax_rmb = max(foreign_tax_paid_rmb - china_tax_before_credit_rmb, 0)
```

### Treaty Withholding Check

For U.S.-source dividends for a China treaty resident:

```text
expected_us_withholding_rate = 10% when treaty conditions apply
actual_us_withholding_rate = us_tax_withheld / gross_us_dividend
```

Flag only as review item:

- `actual_us_withholding_rate` near 10%: appears consistent with treaty dividend cap.
- `actual_us_withholding_rate` near 30%: review W-8BEN / treaty benefit status.
- Any other rate: review income code, country, treaty eligibility, and withholding agent records.

Do not assert entitlement to a treaty rate without reviewing account tax forms and treaty conditions.

## Output Design

### Evidence Summary

Produce a table:

| Source | Tax year | Country | Income type | Gross original | Tax withheld original | Currency | Notes |
|---|---:|---|---|---:|---:|---|---|

### China IIT Estimate

Produce a table:

| Country | Category | Income RMB | China rate | China tax before credit | Foreign tax paid RMB | Creditable tax | Estimated top-up | Excess carryforward |
|---|---|---:|---:|---:|---:|---:|---:|---:|

### Treaty Sanity Check

Produce a table:

| Country | Income type | Gross | Withheld | Actual rate | Treaty reference | Review note |
|---|---|---:|---:|---:|---|---|

### Filing Support Checklist

Include neutral checklist items:

- Obtain official 1042-S for the tax year.
- Export IBKR annual Activity Statement / Flex Query including Trades, Dividends, Withholding Tax, Cash Transactions, Realized P&L, and FX.
- Preserve exchange-rate source and chosen conversion method.
- Review W-8BEN/treaty withholding status where withholding rate differs from expected treaty cap.
- Confirm final tax treatment with a qualified tax professional or competent tax authority.

## Non-Official Product Pattern Review

Observed as of 2026-05-24. A comparable CRS overseas stock income calculator at `https://app-blqg6my2bvup.appmiaoda.com/` uses a browser-only workflow. It is useful as a product-design reference, not as an official tax source.

Observed behavior:

- Targets Futu annual tax/account statements, not IBKR.
- Parses `.xlsx`, `.xls`, and `.csv` files locally in browser memory with SheetJS/PapaParse-style logic.
- Reads sheets named like `证券-资金进出`, `证券-持仓总览`, `证券-交易流水`, and `证券-资产进出`.
- Splits data into cash flows, initial positions, transactions, and asset-transfer events.
- Detects dividends, withholding/tax cash-flow rows, normal trades, and special asset events such as IPO, split, transfer-in, and external transfer.
- Requires uploading the target year plus historical statements to reconstruct historical cost basis.
- Prompts manual cost-basis input when splits, transfers, option exercise, or incomplete history causes missing lots.
- Provides preset USD/CNY annual filing rates and links to ChinaMoney/PBOC-style RMB central parity lookup.
- Uses a USD/HKD reference rate and an option to allow Hong Kong stock losses to offset U.S. stock gains in its model.
- Computes currency-level buckets like gains, losses, fees, dividends, tax, and net, then converts USD/HKD totals into CNY.

Design takeaways for this plugin:

- Preserve 100% local/offline parsing for uploaded statements where possible.
- Require all historical statements or explicit manual cost-basis overrides before relying on realized-gain calculations.
- Treat transfers, splits, IPOs, and option exercise as cost-basis hazard events.
- Keep FX rates explicit and auditable; link to official rate sources rather than silently fetching unverified rates.
- Separate tax-law authority from calculator convenience. The web app is an implementation pattern, not an authority.
- Expose assumptions such as cross-market loss offset as configurable review scenarios, not default legal conclusions.

## Current Implementation Surfaces

### Analyzer Module

The shared analyzer module `ibkr_analyzer_lib/analyzers/china_tax.py` provides deterministic dividend/withholding evidence functions and opt-in STK realized-gain evidence for loaded IBKR data:

- `ChinaTaxConfig`: tax year, China tax rates, realized P&L opt-in flags, FX mode, and treaty sanity-check options.
- Dividend and withholding collection from loaded IBKR cash transactions.
- Country/category grouping, RMB translation from IBKR FX evidence, foreign-tax-credit estimates, and Markdown/CSV-ready report structures.
- STK realized-gain property-transfer candidate estimates with IBKR realized P&L primary口径 plus FIFO/diluted comparison rows.

The local-file self-check CLI `skills/china-tax/scripts/china_tax_self_check.py` wraps `ibkr_analyzer_lib.china_tax_self_check` for offline evidence parsing and report generation from Flex XML/CSV, 1042-S CSV, explicit RMB FX CSV, and IBKR tax-report ZIP evidence.

Keep functions deterministic and testable. Avoid network FX calls unless explicitly requested.

### CLI / MCP Surface

Current surfaces:

- MCP tool: `ibkr_china_tax_annual_calc` for loaded Flex data dividend/withholding estimates and opt-in STK realized-gain evidence.
- Local-file CLI: `skills/china-tax/scripts/china_tax_self_check.py` for offline evidence reports.
- Commands: `commands/china-tax-annual.md` and `commands/china-tax-year-end-plan.md`.

Key parameters and inputs:

| Surface | Parameter / input | Purpose |
|---|---|---|
| MCP | `tax_year` | Annual calculation year |
| MCP | `china_iit_dividend_rate` | Default 0.20 informational estimate |
| MCP | `include_realized_pnl` | Opt into Phase 2 STK realized-gain evidence |
| MCP | `realized_pnl_asset_types` | Supported realized P&L asset types; currently STK |
| MCP | `china_iit_property_transfer_rate` | Default 0.20 property-transfer candidate estimate |
| MCP | `output_csv` | Optional CSV evidence output directory |
| CLI | `--form-1042s` | Optional structured 1042-S CSV reconciliation evidence |
| CLI | `--fx-rates` | Optional explicit currency-to-RMB CSV evidence |
| CLI | `--tax-report-zip` | Optional IBKR tax-report ZIP inspection |
| CLI | `--planning` | Year-end planning/evidence-readiness report mode |

Annual command workflow:

1. Load Flex data as the primary calculation source or use local files through the CLI.
2. Ask for tax year if absent.
3. Ask for RMB FX conversion source only if same-tax-year IBKR USD/RMB FX trade evidence is unavailable or the user wants a different documented rate source.
4. Run the dividend/withholding calculator, opt into realized P&L only when requested, or use the local-file self-check script; mark 1042-S as optional reconciliation/evidence check.
5. Return Markdown report with official-source disclaimer and filing checklist.

### Test Coverage

Current tests cover small fixture data and safety paths:

- U.S. dividend 100 USD, U.S. withholding 10 USD, China rate 20%, RMB rate 7.0 → China tax 140 RMB, credit 70 RMB, top-up 70 RMB.
- U.S. dividend 100 USD, U.S. withholding 30 USD, China rate 20%, RMB rate 7.0 → China tax 140 RMB, credit 140 RMB, top-up 0, excess 70 RMB.
- Missing FX rate → `review_required`, no invented RMB amount.
- STK realized gain/loss estimate and review-required behavior when `include_realized_pnl=True`.
- FIFO and diluted/breakeven comparison rows for realized P&L.
- MCP schema and handler wiring for Phase 2 realized P&L parameters.
- Local-file CLI path handling, including paths containing spaces.
- Deterministic Markdown output ordering.

### Guardrails

- Never state that a calculated amount is the final tax payable.
- Never invent missing gross income, withholding, or RMB exchange rates.
- Mark ambiguous categories as `review_required`.
- Keep U.S. treaty withholding check separate from China IIT calculation.
- Preserve all source records in evidence output.

## Implementation Decisions

Resolved decisions:

1. Use IBKR Flex data as the primary calculation source; 1042-S is optional follow-up reconciliation/evidence check, not required input.
2. Use same-tax-year IBKR USD/RMB FX trade evidence first when available; require explicit documented rates when unavailable or when the user chooses another method.
3. Keep realized P&L support opt-in, STK-only, and evidence-oriented; non-STK, non-USD, incomplete lots, losses, and complex events remain `review_required`.
4. Required output formats are Markdown plus CSV evidence tables.
5. Group dividend calculations by source country/category while preserving source-record evidence rows for audit traceability.

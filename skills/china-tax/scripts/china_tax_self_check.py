from __future__ import annotations

import argparse
import csv
import importlib
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional


@dataclass(frozen=True)
class TaxEvidenceItem:
    source: str
    tax_year: int
    country: str
    category: str
    currency: str
    gross_income: float
    foreign_tax_paid: float
    description: str
    review_note: Optional[str] = None


@dataclass(frozen=True)
class TaxEstimateGroup:
    country: str
    category: str
    currency: str
    income_rmb: Optional[float]
    china_tax_before_credit: Optional[float]
    foreign_tax_paid_rmb: Optional[float]
    creditable_foreign_tax: Optional[float]
    estimated_topup_tax: Optional[float]
    excess_foreign_tax: Optional[float]
    review_required: bool = False
    review_note: Optional[str] = None


@dataclass(frozen=True)
class TaxEstimateResult:
    groups: list[TaxEstimateGroup]


def _ibkr_scripts_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "ibkr-trade-analyzer" / "scripts"


def _load_data_loader():
    scripts_dir = _ibkr_scripts_dir()
    inserted = False
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
        inserted = True
    try:
        return importlib.import_module("loader").DataLoader
    finally:
        if inserted:
            try:
                sys.path.remove(str(scripts_dir))
            except ValueError:
                pass


def _parse_positive_float(value: str) -> Optional[float]:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _map_income_category(income_code: str, description: str) -> tuple[str, Optional[str]]:
    normalized_code = (income_code or "").strip()
    normalized_text = (description or "").strip().lower()

    if normalized_code == "06" or any(token in normalized_text for token in ("dividend", "股息", "红利")):
        return "dividend", None
    if normalized_code == "01" or any(token in normalized_text for token in ("interest", "利息")):
        return "interest", None
    return "review_required", f"unmapped_1042s_income_code:{normalized_code or 'unknown'}"


def load_1042s_csv(path: Path) -> list[TaxEvidenceItem]:
    items: list[TaxEvidenceItem] = []
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            category, review_note = _map_income_category(
                row.get("income_code", ""),
                row.get("description", ""),
            )
            items.append(
                TaxEvidenceItem(
                    source="1042-S",
                    tax_year=int(row["tax_year"]),
                    country=(row.get("country") or "US").strip().upper() or "US",
                    category=category,
                    currency=(row.get("currency") or "USD").strip().upper() or "USD",
                    gross_income=float(row["gross_income"]),
                    foreign_tax_paid=float(row["federal_tax_withheld"]),
                    description=row.get("description", ""),
                    review_note=review_note,
                )
            )
    return items


def load_fx_rates_csv(path: Path) -> dict[str, float]:
    rates: dict[str, float] = {}
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            currency = (row.get("currency") or "").strip().upper()
            rate = _parse_positive_float(row.get("rate_to_cny", ""))
            if currency and rate is not None:
                rates[currency] = rate
    return rates


def inspect_ibkr_tax_zip(path: Path) -> dict[str, object]:
    notes: list[str] = []
    files: list[str] = []
    dividend_report_available: Optional[bool] = None

    with zipfile.ZipFile(path) as archive:
        files = sorted(archive.namelist())
        for name in files:
            lowered = name.lower()
            if lowered.endswith(".html") and "dividend" in lowered:
                dividend_report_available = True
                text = archive.read(name).decode("utf-8", errors="ignore")
                if "there is no dividend report available" in text.lower():
                    dividend_report_available = False
                    notes.append("Dividend Report unavailable for selected account/date")
            elif lowered.endswith(".pdf") and "fx" in lowered:
                notes.append("FX PDF found; text extraction not implemented")

    if dividend_report_available is None:
        notes.append("No Dividend Report file found")

    return {
        "files": files,
        "dividend_report_available": dividend_report_available,
        "notes": notes,
    }


def extract_flex_evidence(path: Path, tax_year: int) -> dict[str, object]:
    DataLoader = _load_data_loader()
    account = DataLoader.from_file(str(path))

    dividend_income = 0.0
    withholding_tax = 0.0
    interest_net = 0.0
    realized_pnl = 0.0
    sell_proceeds = 0.0
    commissions = 0.0
    cash_by_currency: dict[str, dict[str, float]] = {}

    for transaction in account.cash_transactions:
        if transaction.date_time is None or transaction.date_time.year != tax_year:
            continue
        transaction_text = f"{transaction.type or ''} {transaction.description or ''}".strip().lower()
        amount = float(transaction.amount)
        currency = (getattr(transaction, "currency", "") or "UNKNOWN").strip().upper() or "UNKNOWN"
        currency_metrics = cash_by_currency.setdefault(
            currency,
            {"dividend_income": 0.0, "withholding_tax": 0.0, "interest_net": 0.0},
        )
        if "withholding" in transaction_text or "withholding tax" in transaction_text or "tax withheld" in transaction_text:
            withholding_tax += abs(amount)
            currency_metrics["withholding_tax"] += abs(amount)
        elif "dividend" in transaction_text and "withholding" not in transaction_text and "tax" not in transaction_text:
            dividend_income += amount
            currency_metrics["dividend_income"] += amount
        elif "interest" in transaction_text:
            interest_net += amount
            currency_metrics["interest_net"] += amount

    for trade in account.trades:
        if trade.date_time is None or trade.date_time.year != tax_year:
            continue
        realized_pnl += float(trade.realized_pnl)
        commissions += abs(float(trade.commission))
        if (trade.buy_sell or "").strip().upper() in {"SELL", "SLD"}:
            sell_proceeds += abs(float(trade.proceeds))

    review_notes: list[str] = []
    if dividend_income > 0 and withholding_tax == 0:
        review_notes.append("Dividend evidence found without explicit withholding cash transactions; reconcile against 1042-S or broker tax forms.")
    if realized_pnl != 0:
        review_notes.append("Realized P&L from Flex is evidence-only and may require manual China tax characterization before filing.")

    return {
        "account_id": account.account_id,
        "base_currency": account.base_currency,
        "dividend_income": dividend_income,
        "withholding_tax": withholding_tax,
        "interest_net": interest_net,
        "cash_by_currency": dict(sorted(cash_by_currency.items())),
        "realized_pnl": realized_pnl,
        "sell_proceeds": sell_proceeds,
        "commissions": commissions,
        "review_notes": review_notes,
    }


def _format_amount(value: Optional[float], currency: str = "RMB") -> str:
    if value is None:
        return "review required"
    return f"{value:.2f} {currency}"


def build_markdown_report(
    *,
    tax_year: int,
    estimate: TaxEstimateResult,
    evidence_items: Iterable[TaxEvidenceItem],
    flex_evidence: dict[str, object],
    tax_zip_summary: dict[str, object],
    output_path: Optional[Path] = None,
    planning: bool = False,
) -> str:
    evidence_list = sorted(
        (item for item in evidence_items if item.tax_year == tax_year),
        key=lambda item: (
            item.source,
            item.tax_year,
            item.country,
            item.category,
            item.currency,
            item.description,
            item.gross_income,
            item.foreign_tax_paid,
        ),
    )
    total_gross = sum(item.gross_income for item in evidence_list)
    total_withholding = sum(item.foreign_tax_paid for item in evidence_list)
    report_lines = [
        "# China Tax Self-Check Report",
        "",
        f"Tax year: {tax_year}",
        "",
        "This report is an informational evidence organizer and rough estimate only. It is not tax filing advice, legal advice, or a substitute for professional review.",
        "",
        "## Scope & Assumptions",
        "",
        f"- Planning mode: {'yes' if planning else 'no'}",
        "- Assumes the current estimate only auto-calculates dividend items and flags other categories for manual review.",
        "- Uses supplied FX rates and broker evidence as inputs; users should reconcile final filings with official tax documents.",
        "",
        "## Evidence Summary",
        "",
        f"- 1042-S / manual evidence items in scope: {len(evidence_list)}",
        f"- Gross income from evidence items: {total_gross:.2f}",
        f"- Foreign tax paid from evidence items: {total_withholding:.2f}",
        "",
        "### Flex Evidence",
        "",
        f"- Account ID: {flex_evidence.get('account_id', '') or 'unknown'}",
        f"- Base currency: {flex_evidence.get('base_currency', '') or 'unknown'}",
        f"- Dividend income: {float(flex_evidence.get('dividend_income', 0.0)):.2f}",
        f"- Withholding tax: {float(flex_evidence.get('withholding_tax', 0.0)):.2f}",
        f"- Interest net: {float(flex_evidence.get('interest_net', 0.0)):.2f}",
        f"- Realized P&L: {float(flex_evidence.get('realized_pnl', 0.0)):.2f}",
        f"- Sell proceeds: {float(flex_evidence.get('sell_proceeds', 0.0)):.2f}",
        f"- Commissions: {float(flex_evidence.get('commissions', 0.0)):.2f}",
    ]
    cash_by_currency = flex_evidence.get("cash_by_currency", {})
    if cash_by_currency:
        report_lines.extend([
            "",
            "| Currency | Dividend income | Withholding tax | Interest net |",
            "| --- | ---: | ---: | ---: |",
        ])
        for currency, metrics in sorted(cash_by_currency.items()):
            report_lines.append(
                f"| {currency} | {float(metrics.get('dividend_income', 0.0)):.2f} | {float(metrics.get('withholding_tax', 0.0)):.2f} | {float(metrics.get('interest_net', 0.0)):.2f} |"
            )
    review_notes = list(flex_evidence.get("review_notes", []))
    if review_notes:
        report_lines.extend(["- Flex review notes:"] + [f"  - {note}" for note in review_notes])
    else:
        report_lines.append("- Flex review notes: none")

    report_lines.extend([
        "",
        "## China IIT Estimate",
        "",
        "| Country | Category | Currency | Income (RMB) | China tax before credit | Foreign tax paid (RMB) | Creditable foreign tax | Estimated top-up tax | Excess foreign tax | Review |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ])
    for group in sorted(estimate.groups, key=lambda group: (group.country, group.category, group.currency)):
        report_lines.append(
            f"| {group.country} | {group.category} | {group.currency} | {_format_amount(group.income_rmb).replace(' RMB', '')} | {_format_amount(group.china_tax_before_credit).replace(' RMB', '')} | {_format_amount(group.foreign_tax_paid_rmb).replace(' RMB', '')} | {_format_amount(group.creditable_foreign_tax).replace(' RMB', '')} | {_format_amount(group.estimated_topup_tax).replace(' RMB', '')} | {_format_amount(group.excess_foreign_tax).replace(' RMB', '')} | {group.review_note or 'none'} |"
        )

    report_lines.extend([
        "",
        "## 1042-S Reconciliation",
        "",
        f"- Evidence item gross total: {total_gross:.2f}",
        f"- Flex dividend income total: {float(flex_evidence.get('dividend_income', 0.0)):.2f}",
        f"- Evidence item withholding total: {total_withholding:.2f}",
        f"- Flex withholding total: {float(flex_evidence.get('withholding_tax', 0.0)):.2f}",
        "- Differences should be reviewed against 1042-S forms, dividend reports, and broker cash activity before filing.",
        "",
        "## IBKR Tax Report ZIP",
        "",
        f"- Dividend report available: {tax_zip_summary.get('dividend_report_available')}",
        f"- Files: {', '.join(sorted(tax_zip_summary.get('files', []))) or 'none'}",
    ])
    zip_notes = list(tax_zip_summary.get("notes", []))
    if zip_notes:
        report_lines.extend(["- ZIP notes:"] + [f"  - {note}" for note in zip_notes])
    else:
        report_lines.append("- ZIP notes: none")

    report_lines.extend([
        "",
        "## Review Checklist",
        "",
        "- Confirm all dividend records and any withholding match official 1042-S forms.",
        "- Confirm Flex realized P&L and sell proceeds are used only as supporting evidence unless a qualified advisor confirms treatment.",
        "- Confirm FX rates and China IIT treatment used for filing match the taxpayer's final method and records.",
    ])

    report = "\n".join(report_lines) + "\n"
    if output_path is not None:
        Path(output_path).write_text(report, encoding="utf-8")
    return report


def calculate_iit_estimate(
    items: Iterable[TaxEvidenceItem],
    *,
    tax_year: int,
    fx_rates: dict[str, float],
    dividend_rate: float,
) -> TaxEstimateResult:
    totals: dict[tuple[str, str, str], tuple[float, float]] = {}

    for item in items:
        if item.tax_year != tax_year:
            continue

        key = (item.country, item.category, item.currency)
        gross_income, foreign_tax_paid = totals.get(key, (0.0, 0.0))
        totals[key] = (
            gross_income + item.gross_income,
            foreign_tax_paid + item.foreign_tax_paid,
        )

    groups: list[TaxEstimateGroup] = []
    for (country, category, currency), (gross_income, foreign_tax_paid) in totals.items():
        if category != "dividend":
            groups.append(
                TaxEstimateGroup(
                    country=country,
                    category=category,
                    currency=currency,
                    income_rmb=None,
                    china_tax_before_credit=None,
                    foreign_tax_paid_rmb=None,
                    creditable_foreign_tax=None,
                    estimated_topup_tax=None,
                    excess_foreign_tax=None,
                    review_required=True,
                    review_note="category_requires_review",
                )
            )
            continue

        rate = fx_rates.get(currency)
        if rate is None:
            groups.append(
                TaxEstimateGroup(
                    country=country,
                    category=category,
                    currency=currency,
                    income_rmb=None,
                    china_tax_before_credit=None,
                    foreign_tax_paid_rmb=None,
                    creditable_foreign_tax=None,
                    estimated_topup_tax=None,
                    excess_foreign_tax=None,
                    review_required=True,
                    review_note=f"missing_fx_rate:{currency}",
                )
            )
            continue

        income_rmb = gross_income * rate
        china_tax_before_credit = income_rmb * dividend_rate
        foreign_tax_paid_rmb = foreign_tax_paid * rate
        creditable_foreign_tax = min(china_tax_before_credit, foreign_tax_paid_rmb)
        estimated_topup_tax = max(0.0, china_tax_before_credit - creditable_foreign_tax)
        excess_foreign_tax = max(0.0, foreign_tax_paid_rmb - creditable_foreign_tax)

        groups.append(
            TaxEstimateGroup(
                country=country,
                category=category,
                currency=currency,
                income_rmb=income_rmb,
                china_tax_before_credit=china_tax_before_credit,
                foreign_tax_paid_rmb=foreign_tax_paid_rmb,
                creditable_foreign_tax=creditable_foreign_tax,
                estimated_topup_tax=estimated_topup_tax,
                excess_foreign_tax=excess_foreign_tax,
            )
        )

    return TaxEstimateResult(groups=groups)


def parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a China tax self-check report.")
    parser.add_argument("--tax-year", required=True, type=int)
    parser.add_argument("--flex-file")
    parser.add_argument("--form-1042s")
    parser.add_argument("--fx-rates")
    parser.add_argument("--tax-report-zip")
    parser.add_argument("--output", required=True)
    parser.add_argument("--dividend-rate", type=float, default=0.20)
    parser.add_argument("--planning", action="store_true")
    return parser.parse_args(list(argv) if argv is not None else None)


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = parse_args(argv)
    evidence_items = load_1042s_csv(Path(args.form_1042s)) if args.form_1042s else []
    fx_rates = load_fx_rates_csv(Path(args.fx_rates)) if args.fx_rates else {}
    estimate = calculate_iit_estimate(
        evidence_items,
        tax_year=args.tax_year,
        fx_rates=fx_rates,
        dividend_rate=args.dividend_rate,
    )
    flex_evidence = (
        extract_flex_evidence(Path(args.flex_file), tax_year=args.tax_year)
        if args.flex_file
        else {
            "account_id": "",
            "base_currency": "",
            "dividend_income": 0.0,
            "withholding_tax": 0.0,
            "interest_net": 0.0,
            "realized_pnl": 0.0,
            "sell_proceeds": 0.0,
            "commissions": 0.0,
            "cash_by_currency": {},
            "review_notes": [],
        }
    )
    tax_zip_summary = (
        inspect_ibkr_tax_zip(Path(args.tax_report_zip))
        if args.tax_report_zip
        else {"files": [], "dividend_report_available": None, "notes": []}
    )
    build_markdown_report(
        tax_year=args.tax_year,
        estimate=estimate,
        evidence_items=evidence_items,
        flex_evidence=flex_evidence,
        tax_zip_summary=tax_zip_summary,
        output_path=Path(args.output),
        planning=args.planning,
    )
    print(f"Wrote China tax self-check report: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

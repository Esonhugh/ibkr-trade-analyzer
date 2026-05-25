from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from models import AccountData, CashTransaction, Trade


class MissingFxRateError(RuntimeError):
    pass


@dataclass(frozen=True)
class ChinaTaxConfig:
    tax_year: int
    resident_country: str = "CN"
    china_iit_dividend_rate: float = 0.20
    fx_mode: str = "ibkr_evidence"
    dividend_country: str = "US"


class ChinaTaxAnalyzer:
    def __init__(self, data: AccountData, config: ChinaTaxConfig):
        self.data = data
        self.config = config

    def summary(self) -> dict[str, Any]:
        dividend_items = self.collect_dividend_items()
        fx_rates, fx_evidence = self._ibkr_rmb_rates()
        evidence_rows = []
        grouped: dict[tuple[str, str, str], dict[str, Any]] = {}

        for item in dividend_items:
            currency = item["currency"]
            evidence_rows.append({
                "source": "IBKR Flex",
                "tax_year": self.config.tax_year,
                "country": item["country"],
                "income_type": "dividend",
                "gross_original": item["gross_original"],
                "tax_withheld_original": item["withheld_original"],
                "currency": currency,
                "notes": item["notes"],
            })
            if item["country"] == "review_required":
                continue
            rate = fx_rates.get(currency)
            if rate is None:
                raise MissingFxRateError(f"Missing IBKR RMB FX evidence for {currency}")
            key = (item["country"], item["category"], currency)
            group = grouped.setdefault(key, {
                "country": item["country"],
                "category": item["category"],
                "currency": currency,
                "gross_original": 0.0,
                "withheld_original": 0.0,
                "income_rmb": 0.0,
                "foreign_tax_paid_rmb": 0.0,
            })
            group["gross_original"] += item["gross_original"]
            group["withheld_original"] += item["withheld_original"]
            group["income_rmb"] += item["gross_original"] * rate
            group["foreign_tax_paid_rmb"] += item["withheld_original"] * rate

        estimates = [self._estimate_group(group) for group in grouped.values()]
        treaty_rows = [self._treaty_row(group) for group in grouped.values() if group["country"] == "US"]
        markdown = self.build_markdown(evidence_rows, estimates, treaty_rows)

        return {
            "tax_year": self.config.tax_year,
            "status": "informational_estimate",
            "disclaimer": "Informational estimate and evidence organizer only; not tax filing advice.",
            "evidence_summary": evidence_rows,
            "china_iit_estimate": estimates,
            "treaty_sanity_check": treaty_rows,
            "fx_evidence": fx_evidence,
            "markdown": markdown,
            "csv_rows": {
                "evidence_summary": evidence_rows,
                "china_iit_estimate": estimates,
                "treaty_sanity_check": treaty_rows,
            },
        }

    def collect_dividend_items(self) -> list[dict[str, Any]]:
        dividends = [ct for ct in self.data.cash_transactions if self._in_tax_year(ct) and self._is_dividend(ct)]
        withholding = [ct for ct in self.data.cash_transactions if self._in_tax_year(ct) and self._is_withholding_tax(ct)]
        used_withholding: set[int] = set()
        items = []

        for dividend in dividends:
            withheld = 0.0
            best_index = self._nearest_withholding_index(dividend, withholding, used_withholding)
            if best_index is not None:
                withheld = abs(withholding[best_index].amount)
                used_withholding.add(best_index)
            country = self.config.dividend_country if dividend.currency == "USD" else "review_required"
            notes = dividend.description or dividend.symbol
            if country == "review_required":
                notes = f"{notes}; non-USD dividend country/source requires review"
            items.append({
                "country": country,
                "category": "interest_dividends_bonus",
                "currency": dividend.currency,
                "gross_original": abs(dividend.amount),
                "withheld_original": withheld,
                "notes": notes,
            })

        return items

    @staticmethod
    def _nearest_withholding_index(
        dividend: CashTransaction,
        withholding: list[CashTransaction],
        used_withholding: set[int],
    ) -> int | None:
        candidates = []
        for index, tax in enumerate(withholding):
            if index in used_withholding or tax.currency != dividend.currency or tax.symbol != dividend.symbol:
                continue
            if dividend.date_time and tax.date_time:
                distance = abs((tax.date_time - dividend.date_time).total_seconds())
            else:
                distance = 0
            candidates.append((distance, index))
        if not candidates:
            return None
        return min(candidates)[1]

    @staticmethod
    def build_markdown(
        evidence_rows: list[dict[str, Any]],
        estimates: list[dict[str, Any]],
        treaty_rows: list[dict[str, Any]],
    ) -> str:
        lines = [
            "# China Resident Overseas Investment Tax Evidence Review",
            "",
            "This is an informational estimate and evidence organizer, not tax filing advice.",
            "Confirm final treatment with a qualified tax professional or competent tax authority before filing.",
            "",
            "## Evidence Summary",
            "",
            "| Source | Tax Year | Country | Income Type | Gross Original | Tax Withheld Original | Currency | Notes |",
            "|---|---:|---|---|---:|---:|---|---|",
        ]
        for row in evidence_rows:
            lines.append(
                f"| {row['source']} | {row['tax_year']} | {row['country']} | {row['income_type']} | "
                f"{row['gross_original']:.2f} | {row['tax_withheld_original']:.2f} | {row['currency']} | {row['notes']} |"
            )

        lines += [
            "",
            "## China IIT Estimate",
            "",
            "| Country | Category | Income RMB | China Rate | China Tax Before Credit | Foreign Tax Paid RMB | Creditable Tax | Estimated Top-up | Excess Carryforward |",
            "|---|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
        for row in estimates:
            lines.append(
                f"| {row['country']} | {row['category']} | {row['income_rmb']:.2f} | {row['china_rate']:.2%} | "
                f"{row['china_tax_before_credit']:.2f} | {row['foreign_tax_paid_rmb']:.2f} | "
                f"{row['creditable_tax']:.2f} | {row['estimated_topup']:.2f} | {row['excess_carryforward']:.2f} |"
            )

        lines += [
            "",
            "## Treaty Withholding Sanity Check",
            "",
            "| Country | Income Type | Gross | Withheld | Actual Rate | Treaty Reference | Review Note |",
            "|---|---|---:|---:|---:|---|---|",
        ]
        for row in treaty_rows:
            lines.append(
                f"| {row['country']} | {row['income_type']} | {row['gross']:.2f} | {row['withheld']:.2f} | "
                f"{row['actual_rate']:.2%} | {row['treaty_reference']} | {row['review_note']} |"
            )
        return "\n".join(lines) + "\n"

    def _estimate_group(self, group: dict[str, Any]) -> dict[str, Any]:
        income_rmb = self._round_money(group["income_rmb"])
        foreign_tax_paid_rmb = self._round_money(group["foreign_tax_paid_rmb"])
        china_tax = self._round_money(income_rmb * self.config.china_iit_dividend_rate)
        creditable = min(foreign_tax_paid_rmb, china_tax)
        return {
            "country": group["country"],
            "category": group["category"],
            "income_rmb": income_rmb,
            "china_rate": self.config.china_iit_dividend_rate,
            "china_tax_before_credit": china_tax,
            "foreign_tax_paid_rmb": foreign_tax_paid_rmb,
            "creditable_tax": self._round_money(creditable),
            "estimated_topup": self._round_money(max(china_tax - creditable, 0)),
            "excess_carryforward": self._round_money(max(foreign_tax_paid_rmb - china_tax, 0)),
        }

    @staticmethod
    def _treaty_row(group: dict[str, Any]) -> dict[str, Any]:
        gross = group["gross_original"]
        withheld = group["withheld_original"]
        actual_rate = withheld / gross if gross else 0.0
        if abs(actual_rate - 0.10) <= 0.01:
            note = "appears_consistent_with_treaty_dividend_cap"
        elif abs(actual_rate - 0.30) <= 0.01:
            note = "review_w8ben_or_treaty_benefit_status"
        else:
            note = "review_income_code_country_treaty_eligibility_and_withholding_records"
        return {
            "country": group["country"],
            "income_type": "dividend",
            "gross": ChinaTaxAnalyzer._round_money(gross),
            "withheld": ChinaTaxAnalyzer._round_money(withheld),
            "actual_rate": round(actual_rate, 4),
            "treaty_reference": "U.S.–China treaty Article 10 dividend cap review",
            "review_note": note,
        }

    def _ibkr_rmb_rates(self) -> tuple[dict[str, float], list[dict[str, Any]]]:
        rates = {"CNY": 1.0, "CNH": 1.0}
        entries = []
        for trade in self.data.trades:
            if not trade.date_time or trade.date_time.year != self.config.tax_year:
                continue
            extracted = self._extract_usd_rmb_rate(trade)
            if extracted is None:
                continue
            _, rate = extracted
            usd_amount = abs(trade.quantity) if trade.symbol.startswith("USD.") else abs(trade.proceeds)
            rmb_amount = usd_amount * rate
            entries.append((trade, usd_amount, rmb_amount))

        evidence = []
        if entries:
            total_usd = sum(entry[1] for entry in entries)
            total_rmb = sum(entry[2] for entry in entries)
            weighted_rate = total_rmb / total_usd if total_usd else 0.0
            rates["USD"] = weighted_rate
            evidence.append({
                "source": "IBKR Flex FX trade",
                "currency": "USD",
                "rate_rmb_per_unit": self._round_money(weighted_rate),
                "date": f"{self.config.tax_year}",
                "symbol": "USD.CNH/USD.CNY",
                "method": "tax_year_weighted_average_ibkr_fx_trades",
                "n_trades": len(entries),
            })
        return rates, evidence

    @staticmethod
    def _extract_usd_rmb_rate(trade: Trade) -> tuple[str, float] | None:
        if trade.asset_category != "CASH":
            return None
        parts = trade.symbol.split(".")
        if len(parts) != 2:
            return None
        base, quote = parts
        if base == "USD" and quote in {"CNH", "CNY"} and abs(trade.quantity) > 0:
            return quote, abs(trade.proceeds) / abs(trade.quantity)
        if quote == "USD" and base in {"CNH", "CNY"} and abs(trade.proceeds) > 0:
            return base, abs(trade.quantity) / abs(trade.proceeds)
        return None

    def _in_tax_year(self, ct: CashTransaction) -> bool:
        return bool(ct.date_time and ct.date_time.year == self.config.tax_year)

    @staticmethod
    def _is_dividend(ct: CashTransaction) -> bool:
        text = f"{ct.type} {ct.description}".lower()
        return "dividend" in text and "withholding" not in text and "tax" not in text

    @staticmethod
    def _is_withholding_tax(ct: CashTransaction) -> bool:
        text = f"{ct.type} {ct.description}".lower()
        return "withholding" in text or "withholding tax" in text or "tax withheld" in text

    @staticmethod
    def _round_money(value: float) -> float:
        return round(value + 0.0, 2)

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

_scripts_dir = Path(__file__).resolve().parent.parent / "skills" / "ibkr-trade-analyzer" / "scripts"
sys.path.insert(0, str(_scripts_dir))

from analyzers.china_tax import ChinaTaxAnalyzer, ChinaTaxConfig, MissingFxRateError
from models import AccountData, CashTransaction, Trade


def _sample_data() -> AccountData:
    return AccountData(
        trades=[
            Trade(
                asset_category="CASH",
                symbol="USD.CNH",
                currency="CNH",
                date_time=datetime(2025, 12, 31, 10, 0),
                quantity=1000,
                proceeds=-7000,
                commission=0,
            )
        ],
        cash_transactions=[
            CashTransaction(
                date_time=datetime(2025, 3, 1),
                type="Dividends",
                symbol="AAPL",
                currency="USD",
                amount=100,
                description="AAPL dividend",
            ),
            CashTransaction(
                date_time=datetime(2025, 3, 2),
                type="Withholding Tax",
                symbol="AAPL",
                currency="USD",
                amount=-10,
                description="US tax withheld on AAPL dividend",
            ),
        ],
        base_currency="USD",
    )


def test_calculates_dividend_tax_credit_from_ibkr_fx_evidence():
    analyzer = ChinaTaxAnalyzer(_sample_data(), ChinaTaxConfig(tax_year=2025))

    result = analyzer.summary()

    assert result["tax_year"] == 2025
    assert result["status"] == "informational_estimate"
    estimate = result["china_iit_estimate"][0]
    assert estimate["country"] == "US"
    assert estimate["category"] == "interest_dividends_bonus"
    assert estimate["income_rmb"] == 700
    assert estimate["china_tax_before_credit"] == 140
    assert estimate["foreign_tax_paid_rmb"] == 70
    assert estimate["creditable_tax"] == 70
    assert estimate["estimated_topup"] == 70
    assert estimate["excess_carryforward"] == 0
    assert result["fx_evidence"][0]["rate_rmb_per_unit"] == 7


def test_caps_credit_and_reports_excess_foreign_tax():
    data = _sample_data()
    data.cash_transactions[1].amount = -30
    analyzer = ChinaTaxAnalyzer(data, ChinaTaxConfig(tax_year=2025))

    estimate = analyzer.summary()["china_iit_estimate"][0]

    assert estimate["foreign_tax_paid_rmb"] == 210
    assert estimate["creditable_tax"] == 140
    assert estimate["estimated_topup"] == 0
    assert estimate["excess_carryforward"] == 70


def test_missing_ibkr_fx_evidence_raises_explicit_error():
    data = _sample_data()
    data.trades = []
    analyzer = ChinaTaxAnalyzer(data, ChinaTaxConfig(tax_year=2025))

    try:
        analyzer.summary()
    except MissingFxRateError as exc:
        assert "USD" in str(exc)
    else:
        raise AssertionError("Expected MissingFxRateError")


def test_non_us_dividends_are_marked_review_required_not_us_treaty_items():
    data = _sample_data()
    data.cash_transactions[0].currency = "HKD"
    data.cash_transactions[1].currency = "HKD"
    data.trades.append(
        Trade(
            asset_category="CASH",
            symbol="CNH.HKD",
            currency="HKD",
            date_time=datetime(2025, 12, 31, 10, 0),
            quantity=700,
            proceeds=-700,
        )
    )

    result = ChinaTaxAnalyzer(data, ChinaTaxConfig(tax_year=2025)).summary()

    assert result["evidence_summary"][0]["country"] == "review_required"
    assert result["treaty_sanity_check"] == []


def test_allocates_same_symbol_withholding_to_each_dividend_evidence_row():
    data = _sample_data()
    data.cash_transactions = [
        CashTransaction(datetime(2025, 3, 1), "Dividends", "AAPL", "USD", 100, "AAPL dividend March"),
        CashTransaction(datetime(2025, 3, 2), "Withholding Tax", "AAPL", "USD", -10, "US tax withheld March"),
        CashTransaction(datetime(2025, 6, 1), "Dividends", "AAPL", "USD", 200, "AAPL dividend June"),
        CashTransaction(datetime(2025, 6, 2), "Withholding Tax", "AAPL", "USD", -20, "US tax withheld June"),
    ]

    evidence = ChinaTaxAnalyzer(data, ChinaTaxConfig(tax_year=2025)).summary()["evidence_summary"]

    assert [row["gross_original"] for row in evidence] == [100, 200]
    assert [row["tax_withheld_original"] for row in evidence] == [10, 20]


def test_uses_weighted_ibkr_fx_evidence_from_tax_year_only():
    data = _sample_data()
    data.trades = [
        Trade(
            asset_category="CASH",
            symbol="USD.CNH",
            currency="CNH",
            date_time=datetime(2024, 12, 31, 10, 0),
            quantity=1000,
            proceeds=-8000,
        ),
        Trade(
            asset_category="CASH",
            symbol="USD.CNH",
            currency="CNH",
            date_time=datetime(2025, 1, 1, 10, 0),
            quantity=100,
            proceeds=-700,
        ),
        Trade(
            asset_category="CASH",
            symbol="USD.CNH",
            currency="CNH",
            date_time=datetime(2025, 12, 31, 10, 0),
            quantity=300,
            proceeds=-2108,
        ),
    ]

    result = ChinaTaxAnalyzer(data, ChinaTaxConfig(tax_year=2025)).summary()

    assert result["fx_evidence"][0]["rate_rmb_per_unit"] == 7.02
    assert result["china_iit_estimate"][0]["income_rmb"] == 702


def test_treaty_sanity_check_classifies_common_us_withholding_rates():
    result = ChinaTaxAnalyzer(_sample_data(), ChinaTaxConfig(tax_year=2025)).summary()
    treaty = result["treaty_sanity_check"][0]
    assert treaty["actual_rate"] == 0.10
    assert treaty["review_note"] == "appears_consistent_with_treaty_dividend_cap"

    data = _sample_data()
    data.cash_transactions[1].amount = -30
    treaty = ChinaTaxAnalyzer(data, ChinaTaxConfig(tax_year=2025)).summary()["treaty_sanity_check"][0]
    assert treaty["actual_rate"] == 0.30
    assert treaty["review_note"] == "review_w8ben_or_treaty_benefit_status"

    data.cash_transactions[1].amount = -17
    treaty = ChinaTaxAnalyzer(data, ChinaTaxConfig(tax_year=2025)).summary()["treaty_sanity_check"][0]
    assert treaty["actual_rate"] == 0.17
    assert treaty["review_note"] == "review_income_code_country_treaty_eligibility_and_withholding_records"


def test_builds_markdown_and_csv_evidence_outputs():
    result = ChinaTaxAnalyzer(_sample_data(), ChinaTaxConfig(tax_year=2025)).summary()

    assert "not tax filing advice" in result["markdown"].lower()
    assert "| Country | Category | Income RMB |" in result["markdown"]
    assert result["csv_rows"]["evidence_summary"][0]["source"] == "IBKR Flex"
    assert result["csv_rows"]["china_iit_estimate"][0]["estimated_topup"] == 70

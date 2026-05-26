from __future__ import annotations

from datetime import datetime

from ibkr_analyzer_lib.analyzers.china_tax import ChinaTaxAnalyzer, ChinaTaxConfig, MissingFxRateError
from ibkr_analyzer_lib.analyzers.diluted_cost import DilutedCostAnalyzer
from ibkr_analyzer_lib.models import AccountData, CashTransaction, Trade


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


def _sample_realized_gain_data(realized_pnl: float = 100.0, asset_category: str = "STK") -> AccountData:
    data = _sample_data()
    data.cash_transactions = []
    data.trades.extend([
        Trade(
            asset_category=asset_category,
            symbol="AAPL",
            currency="USD",
            date_time=datetime(2025, 2, 1, 10, 0),
            quantity=10,
            trade_price=90,
            proceeds=-900,
            commission=-1,
            realized_pnl=0,
            buy_sell="BUY",
            multiplier=1,
        ),
        Trade(
            asset_category=asset_category,
            symbol="AAPL",
            currency="USD",
            date_time=datetime(2025, 3, 1, 10, 0),
            quantity=-10,
            trade_price=100,
            proceeds=1000,
            commission=-1,
            realized_pnl=realized_pnl,
            buy_sell="SELL",
            multiplier=1,
        ),
    ])
    return data


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


def test_realized_pnl_disabled_by_default_preserves_phase1_output_shape():
    result = ChinaTaxAnalyzer(_sample_data(), ChinaTaxConfig(tax_year=2025)).summary()

    assert "property_transfer_income_estimate" not in result
    assert "realized_pnl_comparison" not in result
    assert "review_required" not in result


def test_realized_pnl_config_defaults_to_stock_ibkr_primary_method():
    config = ChinaTaxConfig(tax_year=2025, include_realized_pnl=True)

    assert config.china_iit_property_transfer_rate == 0.20
    assert config.realized_pnl_asset_types == ("STK",)
    assert config.realized_pnl_primary_method == "ibkr"


def test_realized_stock_gain_uses_ibkr_pnl_as_property_transfer_candidate():
    data = _sample_realized_gain_data(realized_pnl=100)
    result = ChinaTaxAnalyzer(data, ChinaTaxConfig(tax_year=2025, include_realized_pnl=True)).summary()

    estimate = result["property_transfer_income_estimate"][0]
    assert estimate["country"] == "US"
    assert estimate["category"] == "property_transfer_income_candidate"
    assert estimate["currency"] == "USD"
    assert estimate["ibkr_realized_pnl_original"] == 100
    assert estimate["income_rmb"] == 700
    assert estimate["china_rate"] == 0.20
    assert estimate["china_tax_before_credit"] == 140
    assert estimate["foreign_tax_paid_rmb"] == 0
    assert estimate["estimated_tax_rmb"] == 140


def test_realized_stock_loss_has_zero_tax_and_review_item():
    data = _sample_realized_gain_data(realized_pnl=-50)
    result = ChinaTaxAnalyzer(data, ChinaTaxConfig(tax_year=2025, include_realized_pnl=True)).summary()

    estimate = result["property_transfer_income_estimate"][0]
    assert estimate["ibkr_realized_pnl_original"] == -50
    assert estimate["income_rmb"] == 0
    assert estimate["estimated_tax_rmb"] == 0
    assert any(item["reason"] == "realized_loss_treatment_requires_review" for item in result["review_required"])


def test_non_stock_realized_pnl_is_review_required_not_auto_taxed():
    data = _sample_realized_gain_data(realized_pnl=100, asset_category="OPT")
    result = ChinaTaxAnalyzer(data, ChinaTaxConfig(tax_year=2025, include_realized_pnl=True)).summary()

    assert result["property_transfer_income_estimate"] == []
    assert any(item["reason"] == "non_stock_realized_pnl" for item in result["review_required"])


def test_configured_non_stock_realized_pnl_still_requires_review_not_auto_taxed():
    data = _sample_realized_gain_data(realized_pnl=100, asset_category="OPT")
    result = ChinaTaxAnalyzer(
        data,
        ChinaTaxConfig(tax_year=2025, include_realized_pnl=True, realized_pnl_asset_types=("OPT",)),
    ).summary()

    assert result["property_transfer_income_estimate"] == []
    assert any(item["reason"] == "non_stock_realized_pnl" for item in result["review_required"])


def test_realized_pnl_comparison_includes_complete_fifo_result():
    data = _sample_realized_gain_data(realized_pnl=100)
    result = ChinaTaxAnalyzer(data, ChinaTaxConfig(tax_year=2025, include_realized_pnl=True)).summary()

    comparison = result["realized_pnl_comparison"][0]
    assert comparison["symbol"] == "AAPL"
    assert comparison["currency"] == "USD"
    assert comparison["ibkr_realized_pnl"] == 100
    assert comparison["fifo_realized_pnl"] == 98
    assert comparison["fifo_status"] == "complete"
    assert comparison["difference_ibkr_vs_fifo"] == 2


def test_realized_pnl_comparison_includes_diluted_result():
    data = _sample_realized_gain_data(realized_pnl=100)
    result = ChinaTaxAnalyzer(data, ChinaTaxConfig(tax_year=2025, include_realized_pnl=True)).summary()

    comparison = result["realized_pnl_comparison"][0]
    assert comparison["diluted_realized_pnl"] == 100
    assert comparison["difference_ibkr_vs_diluted"] == 0


def test_realized_pnl_comparison_includes_diluted_result_beyond_summary_top_20():
    data = _sample_data()
    data.cash_transactions = []
    for index in range(21):
        symbol = f"STK{index:02d}"
        buy_price = 100
        sell_price = 110 + index
        data.trades.extend([
            Trade(
                asset_category="STK",
                symbol=symbol,
                currency="USD",
                date_time=datetime(2025, 2, 1, 10, 0),
                quantity=1,
                trade_price=buy_price,
                proceeds=-buy_price,
                commission=0,
                realized_pnl=0,
                buy_sell="BUY",
                multiplier=1,
            ),
            Trade(
                asset_category="STK",
                symbol=symbol,
                currency="USD",
                date_time=datetime(2025, 3, 1, 10, 0),
                quantity=-1,
                trade_price=sell_price,
                proceeds=sell_price,
                commission=0,
                realized_pnl=sell_price - buy_price,
                buy_sell="SELL",
                multiplier=1,
            ),
        ])

    truncated_symbols = {
        item["symbol"]
        for item in DilutedCostAnalyzer([
            trade for trade in data.trades if trade.asset_category == "STK"
        ]).summary()["symbol_details"]
    }
    expected_symbol = "STK00"
    assert expected_symbol not in truncated_symbols

    result = ChinaTaxAnalyzer(data, ChinaTaxConfig(tax_year=2025, include_realized_pnl=True)).summary()
    comparison = {
        item["symbol"]: item
        for item in result["realized_pnl_comparison"]
    }

    assert comparison[expected_symbol]["diluted_realized_pnl"] == 10
    assert comparison[expected_symbol]["difference_ibkr_vs_diluted"] == 0


def test_missing_fifo_lot_marks_comparison_incomplete():
    data = _sample_data()
    data.cash_transactions = []
    data.trades.append(
        Trade(
            asset_category="STK",
            symbol="MSFT",
            currency="USD",
            date_time=datetime(2025, 3, 1, 10, 0),
            quantity=-5,
            trade_price=100,
            proceeds=500,
            commission=-1,
            realized_pnl=50,
            buy_sell="SELL",
            multiplier=1,
        )
    )

    result = ChinaTaxAnalyzer(data, ChinaTaxConfig(tax_year=2025, include_realized_pnl=True)).summary()

    comparison = result["realized_pnl_comparison"][0]
    assert comparison["symbol"] == "MSFT"
    assert comparison["fifo_status"] == "incomplete"
    assert any(item["reason"] == "fifo_lot_history_incomplete" for item in result["review_required"])


def test_phase2_markdown_and_csv_include_realized_gain_sections():
    data = _sample_realized_gain_data(realized_pnl=100)
    result = ChinaTaxAnalyzer(data, ChinaTaxConfig(tax_year=2025, include_realized_pnl=True)).summary()

    assert "## Property Transfer Income Estimate" in result["markdown"]
    assert "## Realized P&L Comparison" in result["markdown"]
    assert "property_transfer_income_estimate" in result["csv_rows"]
    assert "realized_pnl_comparison" in result["csv_rows"]
    assert "review_required" in result["csv_rows"]

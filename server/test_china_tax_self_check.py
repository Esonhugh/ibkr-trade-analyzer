from __future__ import annotations

import subprocess
import sys
import zipfile
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
CHINA_TAX_SCRIPTS = ROOT / "skills" / "china-tax" / "scripts"
sys.path.insert(0, str(CHINA_TAX_SCRIPTS))

import china_tax_self_check
from china_tax_self_check import (
    TaxEvidenceItem,
    build_markdown_report,
    calculate_iit_estimate,
    extract_flex_evidence,
    inspect_ibkr_tax_zip,
    load_1042s_csv,
    load_fx_rates_csv,
)


def test_dividend_with_10_percent_us_withholding_has_topup() -> None:
    items = [
        TaxEvidenceItem(
            source="1042-S",
            tax_year=2025,
            country="US",
            category="dividend",
            currency="USD",
            gross_income=100.0,
            foreign_tax_paid=10.0,
            description="US dividend",
        )
    ]

    result = calculate_iit_estimate(
        items,
        tax_year=2025,
        fx_rates={"USD": 7.0},
        dividend_rate=0.20,
    )

    assert result.groups[0].income_rmb == 700.0
    assert result.groups[0].china_tax_before_credit == 140.0
    assert result.groups[0].foreign_tax_paid_rmb == 70.0
    assert result.groups[0].creditable_foreign_tax == 70.0
    assert result.groups[0].estimated_topup_tax == 70.0
    assert result.groups[0].excess_foreign_tax == 0.0


def test_dividend_with_30_percent_us_withholding_has_excess_credit() -> None:
    items = [
        TaxEvidenceItem(
            source="1042-S",
            tax_year=2025,
            country="US",
            category="dividend",
            currency="USD",
            gross_income=100.0,
            foreign_tax_paid=30.0,
            description="US dividend with high withholding",
        )
    ]

    result = calculate_iit_estimate(
        items,
        tax_year=2025,
        fx_rates={"USD": 7.0},
        dividend_rate=0.20,
    )

    assert result.groups[0].income_rmb == 700.0
    assert result.groups[0].china_tax_before_credit == 140.0
    assert result.groups[0].foreign_tax_paid_rmb == 210.0
    assert result.groups[0].creditable_foreign_tax == 140.0
    assert result.groups[0].estimated_topup_tax == 0.0
    assert result.groups[0].excess_foreign_tax == 70.0


def test_dividend_items_are_aggregated_before_credit_calculation() -> None:
    items = [
        TaxEvidenceItem(
            source="1042-S",
            tax_year=2025,
            country="US",
            category="dividend",
            currency="USD",
            gross_income=100.0,
            foreign_tax_paid=30.0,
            description="US dividend with high withholding",
        ),
        TaxEvidenceItem(
            source="1042-S",
            tax_year=2025,
            country="US",
            category="dividend",
            currency="USD",
            gross_income=100.0,
            foreign_tax_paid=0.0,
            description="US dividend without withholding",
        ),
    ]

    result = calculate_iit_estimate(
        items,
        tax_year=2025,
        fx_rates={"USD": 7.0},
        dividend_rate=0.20,
    )

    assert len(result.groups) == 1
    assert result.groups[0].income_rmb == 1400.0
    assert result.groups[0].china_tax_before_credit == 280.0
    assert result.groups[0].foreign_tax_paid_rmb == 210.0
    assert result.groups[0].creditable_foreign_tax == 210.0
    assert result.groups[0].estimated_topup_tax == 70.0
    assert result.groups[0].excess_foreign_tax == 0.0


def test_dividend_missing_fx_rate_is_marked_review_required() -> None:
    items = [
        TaxEvidenceItem(
            source="1042-S",
            tax_year=2025,
            country="US",
            category="dividend",
            currency="USD",
            gross_income=100.0,
            foreign_tax_paid=10.0,
            description="US dividend",
        )
    ]

    result = calculate_iit_estimate(
        items,
        tax_year=2025,
        fx_rates={},
        dividend_rate=0.20,
    )

    assert len(result.groups) == 1
    assert result.groups[0].country == "US"
    assert result.groups[0].category == "dividend"
    assert result.groups[0].currency == "USD"
    assert result.groups[0].review_required is True
    assert result.groups[0].income_rmb is None
    assert result.groups[0].china_tax_before_credit is None
    assert result.groups[0].foreign_tax_paid_rmb is None
    assert result.groups[0].creditable_foreign_tax is None
    assert result.groups[0].estimated_topup_tax is None
    assert result.groups[0].excess_foreign_tax is None
    assert result.groups[0].review_note == "missing_fx_rate:USD"


def test_unsupported_category_is_marked_review_required() -> None:
    items = [
        TaxEvidenceItem(
            source="1042-S",
            tax_year=2025,
            country="US",
            category="interest",
            currency="USD",
            gross_income=100.0,
            foreign_tax_paid=10.0,
            description="US interest",
        )
    ]

    result = calculate_iit_estimate(
        items,
        tax_year=2025,
        fx_rates={"USD": 7.0},
        dividend_rate=0.20,
    )

    assert len(result.groups) == 1
    assert result.groups[0].country == "US"
    assert result.groups[0].category == "interest"
    assert result.groups[0].review_required is True
    assert result.groups[0].income_rmb is None
    assert result.groups[0].china_tax_before_credit is None
    assert result.groups[0].foreign_tax_paid_rmb is None
    assert result.groups[0].creditable_foreign_tax is None
    assert result.groups[0].estimated_topup_tax is None
    assert result.groups[0].excess_foreign_tax is None
    assert result.groups[0].review_note == "category_requires_review"


def test_load_1042s_csv_accepts_expected_columns(tmp_path: Path) -> None:
    csv_path = tmp_path / "1042s.csv"
    csv_path.write_text(
        "tax_year,income_code,country,currency,gross_income,federal_tax_withheld,tax_rate,description\n"
        "2025,06,US,USD,100.00,10.00,0.10,US dividends\n",
        encoding="utf-8",
    )

    items = load_1042s_csv(csv_path)

    assert len(items) == 1
    assert items[0].tax_year == 2025
    assert items[0].country == "US"
    assert items[0].category == "dividend"
    assert items[0].gross_income == 100.0
    assert items[0].foreign_tax_paid == 10.0


def test_load_fx_rates_csv_returns_currency_mapping(tmp_path: Path) -> None:
    csv_path = tmp_path / "fx.csv"
    csv_path.write_text(
        "currency,rate_to_cny\nUSD,7.1884\nHKD,0.9253\n",
        encoding="utf-8",
    )

    rates = load_fx_rates_csv(csv_path)

    assert rates == {"USD": 7.1884, "HKD": 0.9253}


def test_inspect_ibkr_tax_zip_detects_empty_dividend_report(tmp_path: Path) -> None:
    zip_path = tmp_path / "2025 tax report.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr(
            "U123.2025.dividends.html",
            "There is no Dividend Report available for the selected account and date.",
        )
        archive.writestr("U123.2025.fx.pdf", b"%PDF-1.4 fake pdf")

    result = inspect_ibkr_tax_zip(zip_path)

    assert result["files"] == ["U123.2025.dividends.html", "U123.2025.fx.pdf"]
    assert result["dividend_report_available"] is False
    assert "Dividend Report" in result["notes"][0]


def test_load_1042s_csv_maps_interest_codes_and_text(tmp_path: Path) -> None:
    csv_path = tmp_path / "1042s.csv"
    csv_path.write_text(
        "tax_year,income_code,country,currency,gross_income,federal_tax_withheld,tax_rate,description\n"
        "2025,01,US,USD,10.00,1.00,0.10,Other income\n"
        "2025,99,US,USD,20.00,2.00,0.10,Bank interest\n"
        "2025,99,US,USD,30.00,3.00,0.10,债券利息\n",
        encoding="utf-8",
    )

    items = load_1042s_csv(csv_path)

    assert [item.category for item in items] == ["interest", "interest", "interest"]


def test_load_1042s_csv_maps_chinese_dividend_labels(tmp_path: Path) -> None:
    csv_path = tmp_path / "1042s.csv"
    csv_path.write_text(
        "tax_year,income_code,country,currency,gross_income,federal_tax_withheld,tax_rate,description\n"
        "2025,99,US,USD,10.00,1.00,0.10,现金股息\n"
        "2025,99,US,USD,20.00,2.00,0.10,股票红利\n",
        encoding="utf-8",
    )

    items = load_1042s_csv(csv_path)

    assert [item.category for item in items] == ["dividend", "dividend"]


def test_load_1042s_csv_marks_unmapped_income_for_review(tmp_path: Path) -> None:
    csv_path = tmp_path / "1042s.csv"
    csv_path.write_text(
        "tax_year,income_code,country,currency,gross_income,federal_tax_withheld,tax_rate,description\n"
        "2025,99,US,USD,10.00,1.00,0.10,Royalty payment\n",
        encoding="utf-8",
    )

    items = load_1042s_csv(csv_path)

    assert items[0].category == "review_required"
    assert items[0].review_note


def test_load_1042s_csv_defaults_identity_and_withholding_fields(tmp_path: Path) -> None:
    csv_path = tmp_path / "1042s.csv"
    csv_path.write_text(
        "tax_year,income_code,country,currency,gross_income,federal_tax_withheld,tax_rate,description\n"
        "2025,06,,,100.00,15.00,0.15,US dividends\n",
        encoding="utf-8",
    )

    items = load_1042s_csv(csv_path)

    assert items[0].source == "1042-S"
    assert items[0].country == "US"
    assert items[0].currency == "USD"
    assert items[0].foreign_tax_paid == 15.0


def test_load_fx_rates_csv_uppercases_and_ignores_non_positive_rows(tmp_path: Path) -> None:
    csv_path = tmp_path / "fx.csv"
    csv_path.write_text(
        "currency,rate_to_cny\n"
        "usd,7.1884\n"
        "HKD,0.9253\n"
        ",6.5\n"
        "EUR,0\n"
        "GBP,-1\n"
        "JPY,not-a-number\n",
        encoding="utf-8",
    )

    rates = load_fx_rates_csv(csv_path)

    assert rates == {"USD": 7.1884, "HKD": 0.9253}


def test_inspect_ibkr_tax_zip_notes_fx_pdf_and_sorts_files(tmp_path: Path) -> None:
    zip_path = tmp_path / "2025 tax report.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr("z-last.txt", "last")
        archive.writestr("U123.2025.fx.pdf", b"%PDF-1.4 fake pdf")
        archive.writestr("a-first.txt", "first")
        archive.writestr("U123.2025.dividends.html", "Dividend Report content")

    result = inspect_ibkr_tax_zip(zip_path)

    assert result["files"] == [
        "U123.2025.dividends.html",
        "U123.2025.fx.pdf",
        "a-first.txt",
        "z-last.txt",
    ]
    assert any("FX PDF" in note for note in result["notes"])


def test_inspect_ibkr_tax_zip_detects_short_empty_dividend_report_phrase(tmp_path: Path) -> None:
    zip_path = tmp_path / "2025 tax report.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr(
            "U123.2025.dividends.html",
            "There is no Dividend Report available",
        )

    result = inspect_ibkr_tax_zip(zip_path)

    assert result["dividend_report_available"] is False
    assert "Dividend Report" in result["notes"][0]


def test_inspect_ibkr_tax_zip_marks_missing_dividend_report_for_review(tmp_path: Path) -> None:
    zip_path = tmp_path / "2025 tax report.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr("U123.2025.fx.pdf", b"%PDF-1.4 fake pdf")

    result = inspect_ibkr_tax_zip(zip_path)

    assert result["dividend_report_available"] is None
    assert any("No Dividend Report file found" in note for note in result["notes"])


def test_estimate_groups_expose_currency_for_distinct_currency_groups() -> None:
    items = [
        TaxEvidenceItem(
            source="1042-S",
            tax_year=2025,
            country="US",
            category="dividend",
            currency="USD",
            gross_income=100.0,
            foreign_tax_paid=10.0,
            description="US dividend",
        ),
        TaxEvidenceItem(
            source="1042-S",
            tax_year=2025,
            country="US",
            category="dividend",
            currency="HKD",
            gross_income=100.0,
            foreign_tax_paid=0.0,
            description="HK dividend",
        ),
    ]

    result = calculate_iit_estimate(
        items,
        tax_year=2025,
        fx_rates={"USD": 7.0, "HKD": 0.9},
        dividend_rate=0.20,
    )

    assert {(group.country, group.category, group.currency) for group in result.groups} == {
        ("US", "dividend", "USD"),
        ("US", "dividend", "HKD"),
    }


def test_extract_flex_evidence_returns_records_for_existing_fixture(tmp_path: Path) -> None:
    flex_xml = tmp_path / "flex-2026-05-16.xml"
    flex_xml.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<FlexQueryResponse>
  <FlexStatements>
    <FlexStatement>
      <AccountInformation accountId="U1234567" currency="USD" />
      <CashTransactions>
        <CashTransaction dateTime="20260510;120000" type="Dividends" symbol="AAPL" currency="USD" amount="100.00" description="AAPL cash dividend" />
        <CashTransaction dateTime="20260512;120000" type="Interest" symbol="USD" currency="USD" amount="2.50" description="Credit interest" />
      </CashTransactions>
      <Trades>
        <Trade tradeID="1" accountId="U1234567" symbol="AAPL" assetCategory="STK" currency="USD" description="AAPL" dateTime="20260511;130000" quantity="10" tradePrice="30.00" proceeds="300.00" ibCommission="-1.00" fifoPnlRealized="25.00" cost="275.00" buySell="SELL" openCloseIndicator="C" exchange="SMART" orderType="LMT" multiplier="1" />
      </Trades>
    </FlexStatement>
  </FlexStatements>
</FlexQueryResponse>
""",
        encoding="utf-8",
    )

    result = extract_flex_evidence(flex_xml, tax_year=2026)

    assert {
        "dividend_income",
        "withholding_tax",
        "realized_pnl",
        "sell_proceeds",
    }.issubset(result.keys())
    assert isinstance(result["review_notes"], list)


def test_extract_flex_evidence_classifies_cash_transactions_by_description(monkeypatch) -> None:
    account = SimpleNamespace(
        account_id="U123",
        base_currency="USD",
        trades=[],
        cash_transactions=[
            SimpleNamespace(
                date_time=datetime(2026, 1, 2),
                type="Other",
                description="AAPL Dividend",
                amount=100.0,
                currency="USD",
            ),
            SimpleNamespace(
                date_time=datetime(2026, 1, 3),
                type="Other",
                description="US Withholding Tax",
                amount=-10.0,
                currency="USD",
            ),
            SimpleNamespace(
                date_time=datetime(2026, 1, 4),
                type="Other",
                description="USD Interest Payment",
                amount=2.5,
                currency="USD",
            ),
            SimpleNamespace(
                date_time=datetime(2025, 1, 4),
                type="Other",
                description="USD Interest Payment",
                amount=99.0,
                currency="USD",
            ),
        ],
    )
    data_loader = SimpleNamespace(from_file=lambda path: account)
    monkeypatch.setattr(china_tax_self_check, "_load_data_loader", lambda: data_loader)

    result = extract_flex_evidence(Path("unused.xml"), tax_year=2026)

    assert result["dividend_income"] == 100.0
    assert result["withholding_tax"] == 10.0
    assert result["interest_net"] == 2.5


def test_extract_flex_evidence_exposes_cash_metrics_by_currency(monkeypatch) -> None:
    account = SimpleNamespace(
        account_id="U123",
        base_currency="USD",
        trades=[],
        cash_transactions=[
            SimpleNamespace(
                date_time=datetime(2026, 1, 2),
                type="Dividends",
                description="USD dividend",
                amount=100.0,
                currency="USD",
            ),
            SimpleNamespace(
                date_time=datetime(2026, 1, 3),
                type="Other",
                description="USD tax withheld",
                amount=-10.0,
                currency="USD",
            ),
            SimpleNamespace(
                date_time=datetime(2026, 1, 4),
                type="Interest",
                description="USD interest",
                amount=2.5,
                currency="USD",
            ),
            SimpleNamespace(
                date_time=datetime(2026, 1, 5),
                type="Dividends",
                description="HKD dividend",
                amount=200.0,
                currency="HKD",
            ),
            SimpleNamespace(
                date_time=datetime(2026, 1, 6),
                type="Other",
                description="HKD withholding tax",
                amount=-20.0,
                currency="HKD",
            ),
            SimpleNamespace(
                date_time=datetime(2026, 1, 7),
                type="Interest",
                description="HKD interest",
                amount=3.5,
                currency="HKD",
            ),
        ],
    )
    data_loader = SimpleNamespace(from_file=lambda path: account)
    monkeypatch.setattr(china_tax_self_check, "_load_data_loader", lambda: data_loader)

    result = extract_flex_evidence(Path("unused.xml"), tax_year=2026)

    assert result["cash_by_currency"] == {
        "HKD": {
            "dividend_income": 200.0,
            "withholding_tax": 20.0,
            "interest_net": 3.5,
        },
        "USD": {
            "dividend_income": 100.0,
            "withholding_tax": 10.0,
            "interest_net": 2.5,
        },
    }
    assert result["dividend_income"] == 300.0
    assert result["withholding_tax"] == 30.0
    assert result["interest_net"] == 6.0


def test_build_markdown_report_includes_per_currency_flex_cash_evidence(tmp_path: Path) -> None:
    estimate = calculate_iit_estimate(
        [],
        tax_year=2025,
        fx_rates={},
        dividend_rate=0.20,
    )
    output_path = tmp_path / "report.md"

    report = build_markdown_report(
        tax_year=2025,
        estimate=estimate,
        evidence_items=[],
        flex_evidence={
            "dividend_income": 300.0,
            "withholding_tax": 30.0,
            "interest_net": 6.0,
            "realized_pnl": 0.0,
            "sell_proceeds": 0.0,
            "review_notes": [],
            "cash_by_currency": {
                "HKD": {
                    "dividend_income": 200.0,
                    "withholding_tax": 20.0,
                    "interest_net": 3.5,
                },
                "USD": {
                    "dividend_income": 100.0,
                    "withholding_tax": 10.0,
                    "interest_net": 2.5,
                },
            },
        },
        tax_zip_summary={"files": [], "dividend_report_available": None, "notes": []},
        output_path=output_path,
        planning=False,
    )

    assert "| Currency | Dividend income | Withholding tax | Interest net |" in report
    assert "| HKD | 200.00 | 20.00 | 3.50 |" in report
    assert "| USD | 100.00 | 10.00 | 2.50 |" in report
    assert output_path.read_text(encoding="utf-8") == report


def test_build_markdown_report_is_deterministic_for_reordered_inputs() -> None:
    usd_item = TaxEvidenceItem(
        source="1042-S",
        tax_year=2025,
        country="US",
        category="dividend",
        currency="USD",
        gross_income=100.0,
        foreign_tax_paid=10.0,
        description="US dividend",
    )
    hkd_item = TaxEvidenceItem(
        source="Manual",
        tax_year=2025,
        country="HK",
        category="dividend",
        currency="HKD",
        gross_income=200.0,
        foreign_tax_paid=0.0,
        description="HK dividend",
    )
    usd_group = calculate_iit_estimate(
        [usd_item],
        tax_year=2025,
        fx_rates={"USD": 7.0},
        dividend_rate=0.20,
    ).groups[0]
    hkd_group = calculate_iit_estimate(
        [hkd_item],
        tax_year=2025,
        fx_rates={"HKD": 0.9},
        dividend_rate=0.20,
    ).groups[0]
    flex_evidence = {
        "dividend_income": 300.0,
        "withholding_tax": 10.0,
        "interest_net": 0.0,
        "realized_pnl": 0.0,
        "sell_proceeds": 0.0,
        "review_notes": [],
        "cash_by_currency": {
            "USD": {"dividend_income": 100.0, "withholding_tax": 10.0, "interest_net": 0.0},
            "HKD": {"dividend_income": 200.0, "withholding_tax": 0.0, "interest_net": 0.0},
        },
    }

    first_report = build_markdown_report(
        tax_year=2025,
        estimate=SimpleNamespace(groups=[usd_group, hkd_group]),
        evidence_items=[usd_item, hkd_item],
        flex_evidence=flex_evidence,
        tax_zip_summary={
            "files": ["z-last.txt", "a-first.txt"],
            "dividend_report_available": True,
            "notes": [],
        },
        planning=False,
    )
    second_report = build_markdown_report(
        tax_year=2025,
        estimate=SimpleNamespace(groups=[hkd_group, usd_group]),
        evidence_items=[hkd_item, usd_item],
        flex_evidence=flex_evidence,
        tax_zip_summary={
            "files": ["a-first.txt", "z-last.txt"],
            "dividend_report_available": True,
            "notes": [],
        },
        planning=False,
    )

    assert first_report == second_report


def test_build_markdown_report_contains_required_sections(tmp_path: Path) -> None:
    items = [
        TaxEvidenceItem(
            source="1042-S",
            tax_year=2025,
            country="US",
            category="dividend",
            currency="USD",
            gross_income=100.0,
            foreign_tax_paid=10.0,
            description="US dividend",
        )
    ]
    estimate = calculate_iit_estimate(
        items,
        tax_year=2025,
        fx_rates={"USD": 7.0},
        dividend_rate=0.20,
    )
    output_path = tmp_path / "report.md"

    report = build_markdown_report(
        tax_year=2025,
        estimate=estimate,
        evidence_items=items,
        flex_evidence={
            "dividend_income": 100.0,
            "withholding_tax": 10.0,
            "realized_pnl": 0.0,
            "sell_proceeds": 0.0,
            "review_notes": [],
        },
        tax_zip_summary={
            "files": ["U123.2025.dividends.html"],
            "dividend_report_available": True,
            "notes": ["Dividend report present"],
        },
        output_path=output_path,
        planning=False,
    )

    assert "# China Tax Self-Check Report" in report
    assert "## Scope & Assumptions" in report
    assert "## Evidence Summary" in report
    assert "## China IIT Estimate" in report
    assert "## 1042-S Reconciliation" in report
    assert "## Review Checklist" in report
    assert output_path.read_text(encoding="utf-8") == report


def test_cli_generates_report_with_tax_zip_path_containing_spaces(tmp_path: Path) -> None:
    zip_path = tmp_path / "2025 税务报告.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr(
            "U123.2025.dividends.html",
            "There is no Dividend Report available for the selected account and date.",
        )
        archive.writestr("U123.2025.fx.pdf", b"%PDF-1.4 fake pdf")

    fx_path = tmp_path / "fx.csv"
    fx_path.write_text(
        "currency,rate_to_cny\nUSD,7.1884\n",
        encoding="utf-8",
    )
    output_path = tmp_path / "self-check.md"

    result = subprocess.run(
        [
            sys.executable,
            str(CHINA_TAX_SCRIPTS / "china_tax_self_check.py"),
            "--tax-year",
            "2025",
            "--tax-report-zip",
            str(zip_path),
            "--fx-rates",
            str(fx_path),
            "--output",
            str(output_path),
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert output_path.exists()
    report = output_path.read_text(encoding="utf-8")
    assert "China Tax Self-Check Report" in report
    assert "Dividend Report unavailable" in report


def test_cli_generates_report_with_1042s_dividend_and_no_fx_rates(tmp_path: Path) -> None:
    form_1042s_path = tmp_path / "1042s.csv"
    form_1042s_path.write_text(
        "tax_year,income_code,country,currency,gross_income,federal_tax_withheld,tax_rate,description\n"
        "2025,06,US,USD,100.00,10.00,0.10,US dividends\n",
        encoding="utf-8",
    )
    output_path = tmp_path / "self-check.md"

    result = subprocess.run(
        [
            sys.executable,
            str(CHINA_TAX_SCRIPTS / "china_tax_self_check.py"),
            "--tax-year",
            "2025",
            "--form-1042s",
            str(form_1042s_path),
            "--output",
            str(output_path),
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert output_path.exists()
    report = output_path.read_text(encoding="utf-8")
    assert "China Tax Self-Check Report" in report
    assert "missing_fx_rate:USD" in report
    assert "review required" in report

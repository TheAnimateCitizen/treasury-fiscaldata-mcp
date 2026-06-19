"""Offline tests for the Treasury Fiscal Data MCP (no network required)."""
import asyncio
import fiscaldata_mcp as f


def test_norm_path():
    assert f._norm_path("debt_to_penny") == "/v2/accounting/od/debt_to_penny"
    assert f._norm_path("/v2/accounting/od/debt_to_penny") == "/v2/accounting/od/debt_to_penny"
    assert f._norm_path("v1/accounting/mts/mts_table_1") == "/v1/accounting/mts/mts_table_1"
    full = "https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v2/accounting/od/debt_to_penny"
    assert f._norm_path(full) == "/v2/accounting/od/debt_to_penny"
    print("  test_norm_path: OK")


def test_build_params():
    p = f._build_params(fields=["record_date", "tot_pub_debt_out_amt"],
                        filters=["security_desc:eq:Notes"], sort="-record_date",
                        page_size=50, page_number=2,
                        date_field="record_date", start_date="2025-01-01", end_date="2025-12-31")
    assert p["fields"] == "record_date,tot_pub_debt_out_amt"
    assert p["page[size]"] == 50 and p["page[number]"] == 2
    assert p["sort"] == "-record_date"
    # filters + date range combined, comma-joined
    parts = p["filter"].split(",")
    assert "security_desc:eq:Notes" in parts
    assert "record_date:gte:2025-01-01" in parts
    assert "record_date:lte:2025-12-31" in parts
    # no filter key when nothing supplied
    p2 = f._build_params(page_size=1)
    assert "filter" not in p2 and "fields" not in p2
    print("  test_build_params: OK")


def test_catalog():
    assert len(f.DATASETS) >= 10
    assert "debt_to_penny" in f._BY_KEY
    assert f._BY_KEY["mts_table_1"]["path"] == "/v1/accounting/mts/mts_table_1"
    print("  test_catalog: OK")


def test_tools_registered():
    names = {t.name for t in asyncio.run(f.mcp.list_tools())}
    expected = {
        "fiscaldata_status", "list_datasets", "query_dataset", "debt_to_penny",
        "current_debt", "avg_interest_rates", "interest_expense", "exchange_rates",
        "monthly_treasury_statement", "treasury_auctions",
    }
    missing = expected - names
    assert not missing, f"missing tools: {missing}"
    print(f"  test_tools_registered: OK ({len(names)} tools)")


if __name__ == "__main__":
    print("Running Treasury Fiscal Data MCP offline tests...")
    test_norm_path()
    test_build_params()
    test_catalog()
    test_tools_registered()
    print("ALL TESTS PASSED")

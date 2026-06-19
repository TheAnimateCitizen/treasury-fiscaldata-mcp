# Changelog

All notable changes to this project are documented in this file. The format is
based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-06-19

### Added
- Initial release of the U.S. Treasury Fiscal Data MCP server (Python / FastMCP).
  10 tools, no API key required.
- Debt: `current_debt`, `debt_to_penny`.
- Rates & interest: `avg_interest_rates`, `interest_expense`.
- Budget: `monthly_treasury_statement` (receipts, outlays, surplus/deficit).
- Markets: `treasury_auctions`, `exchange_rates` (Treasury reporting rates).
- Discovery & power tools: `list_datasets` (curated catalog of popular endpoints)
  and `query_dataset` (generic access to ANY Fiscal Data endpoint with
  fields / filter / sort / pagination), plus `fiscaldata_status`.
- 5-minute in-memory response cache.
- Offline test suite (`test_fiscaldata.py`) covering path normalization, query
  parameter building, the dataset catalog, and tool registration.

# Treasury Fiscal Data MCP

A free, key-less [Model Context Protocol](https://modelcontextprotocol.io) server for the
**[U.S. Treasury Fiscal Data API](https://fiscaldata.treasury.gov/)** — the federal government's
official record of debt, interest, receipts and outlays, exchange rates, and auctions. No API key,
no account.

Built with [FastMCP](https://github.com/jlowin/fastmcp).

## Tools

| Tool | What it does |
| --- | --- |
| `fiscaldata_status` | Check API reachability and catalog size. |
| `list_datasets` | List/search popular Fiscal Data datasets (key, path, date field, description). |
| `query_dataset` | Generic access to **any** Fiscal Data endpoint: fields, filters, sort, pagination. |
| `current_debt` | Latest U.S. total public debt outstanding (single most recent figure). |
| `debt_to_penny` | Daily total public debt over a date range (public + intragovernmental). |
| `avg_interest_rates` | Average interest rates on Treasury securities by type. |
| `interest_expense` | Interest expense on the public debt by security type (month + FYTD). |
| `monthly_treasury_statement` | Monthly receipts, outlays, and surplus/deficit (MTS Table 1). |
| `exchange_rates` | Treasury reporting rates of exchange (foreign currency). |
| `treasury_auctions` | Recent Treasury securities auction results (CUSIP, term, dates). |

## Install

```bash
git clone https://github.com/jsconiers/treasury-fiscaldata-mcp.git
cd treasury-fiscaldata-mcp
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python test_fiscaldata.py   # offline tests
```

## Use with Claude Desktop

Add to `claude_desktop_config.json` (macOS:
`~/Library/Application Support/Claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "treasury-fiscaldata": {
      "command": "/absolute/path/to/treasury-fiscaldata-mcp/.venv/bin/python",
      "args": ["/absolute/path/to/treasury-fiscaldata-mcp/fiscaldata_mcp.py"]
    }
  }
}
```

Restart Claude Desktop, then ask things like *"What's the national debt right now?"*, *"How much
is the U.S. paying in interest this fiscal year?"*, or *"Show the monthly budget deficit."*

## The generic `query_dataset` tool

The curated catalog (`list_datasets`) surfaces ten popular datasets, but `query_dataset` works for
**any** Fiscal Data endpoint. It accepts a catalog key, a path, or a full URL:

```
query_dataset(endpoint="debt_to_penny", sort="-record_date", page_size=5)
query_dataset(endpoint="/v2/accounting/od/gold_reserve", sort="-record_date")
query_dataset(
  endpoint="avg_interest_rates",
  fields="record_date,security_desc,avg_interest_rate_amt",
  filters=["security_desc:eq:Treasury Notes"],
  start_date="2024-01-01", sort="-record_date",
)
```

Filter operators: `eq`, `gte`, `lte`, `gt`, `lt`, `in`. Sort by any column; prefix `-` for
descending. Responses include a `columns` map of field → human-readable label.

## Examples

```
current_debt()                                  -> latest total public debt (~$39.3T)
debt_to_penny(start_date="2025-01-01")          -> daily debt series
avg_interest_rates(security="Total Marketable") -> blended Treasury rate over time
interest_expense()                              -> interest cost by security type (month + FYTD)
monthly_treasury_statement(classification="Year-to-Date") -> FYTD surplus/deficit
exchange_rates(country_or_currency="Euro")      -> latest Treasury reporting rate
treasury_auctions(security_type="Note")         -> recent note auctions
```

## Data source

All data comes from the public U.S. Treasury Fiscal Data REST API
(`https://api.fiscaldata.treasury.gov/`). Datasets are updated on Treasury's published schedules
(daily, monthly, or quarterly depending on the dataset).

## License

MIT — see [LICENSE](LICENSE). Not affiliated with or endorsed by the U.S. Department of the
Treasury. For informational purposes only.

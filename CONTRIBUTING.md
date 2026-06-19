# Contributing

Issues and pull requests welcome.

## Development

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python test_fiscaldata.py   # offline tests (no network)
```

Keep the server's stdout clean — a stdio MCP server must log only to stderr.

## Scope

This server wraps the public U.S. Treasury Fiscal Data REST API
(`https://api.fiscaldata.treasury.gov/`). No API key is required.
The generic `query_dataset` tool works for any Fiscal Data endpoint; the curated
`DATASETS` catalog just surfaces the most popular ones.

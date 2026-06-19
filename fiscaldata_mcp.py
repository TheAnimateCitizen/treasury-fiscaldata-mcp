#!/usr/bin/env python3
"""U.S. Treasury Fiscal Data MCP server (Python / FastMCP).

Free, key-less access to the U.S. Treasury's Fiscal Data API — the federal government's
record of debt, interest, receipts and outlays, exchange rates, auctions, and more.
No API key or account required.

API docs: https://fiscaldata.treasury.gov/api-documentation/
"""
from __future__ import annotations

import datetime as _dt
import logging
import os
import sys
import time
from typing import Annotated, Any, Optional

import httpx
from fastmcp import FastMCP
from pydantic import Field

BASE = "https://api.fiscaldata.treasury.gov/services/api/fiscal_service"
REQUEST_TIMEOUT = 60.0
CACHE_TTL = 300.0

logging.basicConfig(
    stream=sys.stderr,
    level=logging.DEBUG if os.environ.get("DEBUG") == "true" else logging.INFO,
    format="%(asctime)s [fiscaldata] %(levelname)s %(message)s",
)
log = logging.getLogger("fiscaldata")

# Curated catalog of popular Fiscal Data endpoints. The generic query_dataset tool
# works for ANY Fiscal Data endpoint path, not just these.
DATASETS = [
    {"key": "debt_to_penny", "path": "/v2/accounting/od/debt_to_penny",
     "title": "Debt to the Penny", "date_field": "record_date",
     "desc": "Daily total public debt outstanding (public + intragovernmental)."},
    {"key": "interest_expense", "path": "/v2/accounting/od/interest_expense",
     "title": "Interest Expense on the Public Debt", "date_field": "record_date",
     "desc": "Monthly and fiscal-year-to-date interest expense by security type."},
    {"key": "avg_interest_rates", "path": "/v2/accounting/od/avg_interest_rates",
     "title": "Average Interest Rates on U.S. Treasury Securities", "date_field": "record_date",
     "desc": "Monthly average interest rate by security type/description."},
    {"key": "rates_of_exchange", "path": "/v1/accounting/od/rates_of_exchange",
     "title": "Treasury Reporting Rates of Exchange", "date_field": "record_date",
     "desc": "Quarterly foreign-currency exchange rates used for U.S. government reporting."},
    {"key": "mts_table_1", "path": "/v1/accounting/mts/mts_table_1",
     "title": "Monthly Treasury Statement - Summary (Table 1)", "date_field": "record_date",
     "desc": "Monthly federal receipts, outlays, and surplus/deficit."},
    {"key": "mspd_table_1", "path": "/v1/debt/mspd/mspd_table_1",
     "title": "Monthly Statement of the Public Debt - Summary", "date_field": "record_date",
     "desc": "Monthly summary of marketable/non-marketable debt outstanding (in millions)."},
    {"key": "auctions_query", "path": "/v1/accounting/od/auctions_query",
     "title": "Treasury Securities Auctions", "date_field": "auction_date",
     "desc": "Auction results for bills, notes, bonds, FRNs, and TIPS (CUSIP, terms, dates)."},
    {"key": "operating_cash_balance", "path": "/v1/accounting/dts/operating_cash_balance",
     "title": "Daily Treasury Statement - Operating Cash Balance", "date_field": "record_date",
     "desc": "Treasury's daily operating cash balance by account."},
    {"key": "deposits_withdrawals_operating_cash",
     "path": "/v1/accounting/dts/deposits_withdrawals_operating_cash",
     "title": "Daily Treasury Statement - Deposits & Withdrawals", "date_field": "record_date",
     "desc": "Daily, MTD and FYTD operating-cash deposits and withdrawals by category."},
    {"key": "gold_reserve", "path": "/v2/accounting/od/gold_reserve",
     "title": "U.S. Government Gold Reserve", "date_field": "record_date",
     "desc": "Monthly gold holdings by facility (fine troy ounces and book value)."},
]
_BY_KEY = {d["key"]: d for d in DATASETS}

_client: Optional[httpx.AsyncClient] = None


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(
            timeout=REQUEST_TIMEOUT, follow_redirects=True,
            headers={"User-Agent": "treasury-fiscaldata-mcp/0.1 (+https://github.com/jsconiers/treasury-fiscaldata-mcp)"},
        )
    return _client


class FiscalError(Exception):
    pass


_cache: dict = {}


def _norm_path(endpoint: str) -> str:
    """Accept a catalog key, a full path, or a full URL; return a normalized path."""
    e = endpoint.strip()
    if e in _BY_KEY:
        return _BY_KEY[e]["path"]
    if e.startswith("http"):
        e = e.split("/services/api/fiscal_service", 1)[-1]
    if not e.startswith("/"):
        e = "/" + e
    return e


async def _request(path: str, params: dict) -> Any:
    key = (path, tuple(sorted((k, str(v)) for k, v in params.items())))
    hit = _cache.get(key)
    if hit and (time.monotonic() - hit[1]) < CACHE_TTL:
        return hit[0]
    try:
        r = await _get_client().get(BASE + path, params=params)
    except Exception as exc:  # noqa: BLE001
        raise FiscalError(f"Request to Fiscal Data failed: {exc}") from exc
    if r.status_code == 404:
        raise FiscalError(f"Endpoint not found (404): {path}. Check the path or use list_datasets.")
    ctype = r.headers.get("content-type", "")
    if "application/json" not in ctype:
        raise FiscalError(f"Non-JSON response (HTTP {r.status_code}) from {path}; the endpoint path is likely wrong.")
    try:
        r.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        raise FiscalError(f"HTTP {r.status_code} from Fiscal Data: {r.text[:200]}") from exc
    try:
        data = r.json()
    except Exception as exc:  # noqa: BLE001
        raise FiscalError(f"Invalid JSON from {path}") from exc
    _cache[key] = (data, time.monotonic())
    return data


def _build_params(
    fields: Optional[Any] = None,
    filters: Optional[Any] = None,
    sort: Optional[str] = None,
    page_size: int = 100,
    page_number: int = 1,
    date_field: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> dict:
    params: dict = {"page[size]": page_size, "page[number]": page_number}
    if fields:
        params["fields"] = ",".join(fields) if isinstance(fields, (list, tuple)) else str(fields)
    flist = []
    if filters:
        if isinstance(filters, (list, tuple)):
            flist.extend([str(f) for f in filters])
        else:
            flist.append(str(filters))
    if date_field and start_date:
        flist.append(f"{date_field}:gte:{start_date}")
    if date_field and end_date:
        flist.append(f"{date_field}:lte:{end_date}")
    if flist:
        params["filter"] = ",".join(flist)
    if sort:
        params["sort"] = sort
    return params


async def _query(path: str, date_field: Optional[str] = None, *, fields=None, filters=None,
                 sort=None, page_size=100, page_number=1, start_date=None, end_date=None) -> dict:
    params = _build_params(fields, filters, sort, page_size, page_number,
                           date_field, start_date, end_date)
    data = await _request(path, params)
    meta = data.get("meta", {})
    return {
        "endpoint": path,
        "count": len(data.get("data", [])),
        "totalCount": meta.get("total-count"),
        "totalPages": meta.get("total-pages"),
        "data": data.get("data", []),
        "_labels": meta.get("labels", {}),
    }


mcp = FastMCP("mcp-treasury-fiscaldata-server")


@mcp.tool()
async def fiscaldata_status() -> dict:
    """Check that the U.S. Treasury Fiscal Data API is reachable and show server info."""
    reachable = None
    note = ""
    try:
        await _request("/v2/accounting/od/debt_to_penny", {"page[size]": 1, "sort": "-record_date"})
        reachable = True
    except FiscalError as exc:
        reachable = False
        note = str(exc)
    return {
        "api": BASE,
        "reachable": reachable,
        "catalogSize": len(DATASETS),
        "note": note or "No API key required. Public U.S. Treasury fiscal data.",
    }


@mcp.tool()
async def list_datasets(search: Optional[str] = None) -> dict:
    """List popular Treasury Fiscal Data datasets (key, path, description, primary date field).

    Pass a `key` or `path` from here to query_dataset. Note: query_dataset accepts ANY Fiscal Data
    endpoint path, not only the ones listed here.
    """
    rows = DATASETS
    if search:
        s = search.lower()
        rows = [d for d in rows if s in d["key"] or s in d["title"].lower() or s in d["desc"].lower()]
    return {"count": len(rows), "datasets": [
        {"key": d["key"], "path": d["path"], "title": d["title"],
         "dateField": d["date_field"], "description": d["desc"]} for d in rows]}


@mcp.tool()
async def query_dataset(
    endpoint: str,
    fields: Optional[str] = None,
    filters: Optional[list] = None,
    sort: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    date_field: str = "record_date",
    page_size: Annotated[int, Field(ge=1, le=1000)] = 100,
    page_number: Annotated[int, Field(ge=1)] = 1,
) -> dict:
    """Generic query against ANY Treasury Fiscal Data endpoint.

    `endpoint` is a catalog key (see list_datasets), a path like '/v2/accounting/od/debt_to_penny', or a
    full URL. `fields` is a comma-separated string of columns. `filters` is a list of 'field:op:value'
    strings (ops: eq, gte, lte, gt, lt, in). `sort` is a column, prefix '-' for descending (e.g.
    '-record_date'). `start_date`/`end_date` (YYYY-MM-DD) apply a range on `date_field`. Returns rows plus
    a `columns` map of field -> human label.
    """
    try:
        path = _norm_path(endpoint)
        res = await _query(path, date_field, fields=fields, filters=filters, sort=sort,
                           page_size=page_size, page_number=page_number,
                           start_date=start_date, end_date=end_date)
    except FiscalError as exc:
        return {"error": str(exc)}
    labels = res.pop("_labels", {})
    if res.get("data"):
        present = set(res["data"][0].keys())
        res["columns"] = {k: v for k, v in labels.items() if k in present}
    return res


@mcp.tool()
async def debt_to_penny(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: Annotated[int, Field(ge=1, le=1000)] = 30,
) -> dict:
    """Daily total U.S. public debt outstanding ("Debt to the Penny"), newest first.

    Optional `start_date`/`end_date` (YYYY-MM-DD) bound the range. Each row has total public debt, debt
    held by the public, and intragovernmental holdings.
    """
    try:
        res = await _query("/v2/accounting/od/debt_to_penny", "record_date",
                           fields="record_date,tot_pub_debt_out_amt,debt_held_public_amt,intragov_hold_amt",
                           sort="-record_date", page_size=limit, start_date=start_date, end_date=end_date)
    except FiscalError as exc:
        return {"error": str(exc)}
    res.pop("_labels", None)
    res["rows"] = [{
        "date": r.get("record_date"),
        "totalPublicDebt": r.get("tot_pub_debt_out_amt"),
        "debtHeldByPublic": r.get("debt_held_public_amt"),
        "intragovHoldings": r.get("intragov_hold_amt"),
    } for r in res.pop("data", [])]
    return res


@mcp.tool()
async def current_debt() -> dict:
    """Latest U.S. total public debt outstanding (single most recent daily figure)."""
    try:
        res = await _query("/v2/accounting/od/debt_to_penny", "record_date",
                           fields="record_date,tot_pub_debt_out_amt,debt_held_public_amt,intragov_hold_amt",
                           sort="-record_date", page_size=1)
    except FiscalError as exc:
        return {"error": str(exc)}
    rows = res.get("data", [])
    if not rows:
        return {"error": "no data returned"}
    r = rows[0]
    def _f(x):
        try:
            return float(x)
        except (TypeError, ValueError):
            return None
    return {
        "asOf": r.get("record_date"),
        "totalPublicDebt": r.get("tot_pub_debt_out_amt"),
        "totalPublicDebtTrillions": round(_f(r.get("tot_pub_debt_out_amt")) / 1e12, 3) if _f(r.get("tot_pub_debt_out_amt")) else None,
        "debtHeldByPublic": r.get("debt_held_public_amt"),
        "intragovHoldings": r.get("intragov_hold_amt"),
    }


@mcp.tool()
async def avg_interest_rates(
    security: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: Annotated[int, Field(ge=1, le=1000)] = 30,
) -> dict:
    """Average interest rates on U.S. Treasury securities, by security type, newest first.

    Optional `security` substring filters the security description (e.g. 'Notes', 'Bonds',
    'Total Marketable'). Dates are YYYY-MM-DD.
    """
    try:
        res = await _query("/v2/accounting/od/avg_interest_rates", "record_date",
                           fields="record_date,security_type_desc,security_desc,avg_interest_rate_amt",
                           sort="-record_date", page_size=max(limit, 200) if security else limit,
                           start_date=start_date, end_date=end_date)
    except FiscalError as exc:
        return {"error": str(exc)}
    res.pop("_labels", None)
    rows = res.pop("data", [])
    if security:
        s = security.lower()
        rows = [r for r in rows if s in (r.get("security_desc", "") or "").lower()
                or s in (r.get("security_type_desc", "") or "").lower()][:limit]
    res["security"] = security
    res["count"] = len(rows)
    res["rows"] = [{
        "date": r.get("record_date"),
        "securityType": r.get("security_type_desc"),
        "security": r.get("security_desc"),
        "avgInterestRatePct": r.get("avg_interest_rate_amt"),
    } for r in rows]
    return res


@mcp.tool()
async def interest_expense(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: Annotated[int, Field(ge=1, le=1000)] = 30,
) -> dict:
    """Interest expense on the U.S. public debt by security type, newest first.

    Each row has the month's expense and the fiscal-year-to-date total. Dates are YYYY-MM-DD.
    """
    try:
        res = await _query("/v2/accounting/od/interest_expense", "record_date",
                           fields="record_date,expense_catg_desc,expense_type_desc,month_expense_amt,fytd_expense_amt",
                           sort="-record_date", page_size=limit, start_date=start_date, end_date=end_date)
    except FiscalError as exc:
        return {"error": str(exc)}
    res.pop("_labels", None)
    res["rows"] = [{
        "date": r.get("record_date"),
        "category": r.get("expense_catg_desc"),
        "type": r.get("expense_type_desc"),
        "monthExpense": r.get("month_expense_amt"),
        "fiscalYtdExpense": r.get("fytd_expense_amt"),
    } for r in res.pop("data", [])]
    return res


@mcp.tool()
async def exchange_rates(
    country_or_currency: Optional[str] = None,
    limit: Annotated[int, Field(ge=1, le=500)] = 30,
) -> dict:
    """Treasury Reporting Rates of Exchange (foreign-currency rates for U.S. government reporting).

    Optional `country_or_currency` is a case-insensitive substring (e.g. 'Euro', 'Japan', 'Canada'); the
    most recent rate per matching currency is returned. With no filter, returns the latest reported rates.
    Note: these are quarterly Treasury reporting rates, not live market FX.
    """
    try:
        res = await _query("/v1/accounting/od/rates_of_exchange", "record_date",
                           fields="record_date,effective_date,country,currency,country_currency_desc,exchange_rate",
                           sort="-effective_date", page_size=500)
    except FiscalError as exc:
        return {"error": str(exc)}
    res.pop("_labels", None)
    rows = res.pop("data", [])
    if country_or_currency:
        s = country_or_currency.lower()
        rows = [r for r in rows if s in (r.get("country_currency_desc", "") or "").lower()]
    # keep the most recent effective_date per currency (rows already sorted desc)
    seen = set()
    dedup = []
    for r in rows:
        key = r.get("country_currency_desc")
        if key in seen:
            continue
        seen.add(key)
        dedup.append(r)
        if len(dedup) >= limit:
            break
    return {
        "filter": country_or_currency, "count": len(dedup),
        "rates": [{
            "country": r.get("country"), "currency": r.get("currency"),
            "label": r.get("country_currency_desc"),
            "exchangeRate": r.get("exchange_rate"),
            "effectiveDate": r.get("effective_date"),
            "recordDate": r.get("record_date"),
        } for r in dedup],
    }


@mcp.tool()
async def monthly_treasury_statement(
    classification: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: Annotated[int, Field(ge=1, le=1000)] = 30,
) -> dict:
    """Monthly Treasury Statement summary (Table 1): federal receipts, outlays, and surplus/deficit.

    Optional `classification` substring filters the line description; values are month names (e.g.
    'October'), 'Year-to-Date', or a fiscal year such as 'FY 2026'. Each row gives that period's gross
    receipts, gross outlays, and deficit/surplus. Dates (YYYY-MM-DD) bound the statement record date.
    """
    try:
        res = await _query("/v1/accounting/mts/mts_table_1", "record_date",
                           fields="record_date,classification_desc,current_month_gross_rcpt_amt,current_month_gross_outly_amt,current_month_dfct_sur_amt",
                           sort="-record_date", page_size=max(limit, 200) if classification else limit,
                           start_date=start_date, end_date=end_date)
    except FiscalError as exc:
        return {"error": str(exc)}
    res.pop("_labels", None)
    rows = res.pop("data", [])
    # drop parent/header rows (e.g. "FY 2026") that carry no amounts
    _amt_fields = ("current_month_gross_rcpt_amt", "current_month_gross_outly_amt",
                   "current_month_dfct_sur_amt")
    rows = [r for r in rows if any(r.get(k) not in (None, "null", "") for k in _amt_fields)]
    if classification:
        s = classification.lower()
        rows = [r for r in rows if s in (r.get("classification_desc", "") or "").lower()]
    rows = rows[:limit]
    res["classification"] = classification
    res["count"] = len(rows)
    res["rows"] = [{
        "date": r.get("record_date"),
        "classification": r.get("classification_desc"),
        "grossReceipts": r.get("current_month_gross_rcpt_amt"),
        "grossOutlays": r.get("current_month_gross_outly_amt"),
        "deficitOrSurplus": r.get("current_month_dfct_sur_amt"),
    } for r in rows]
    return res


@mcp.tool()
async def treasury_auctions(
    security_type: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: Annotated[int, Field(ge=1, le=1000)] = 30,
) -> dict:
    """Recent U.S. Treasury securities auction results, newest auction first.

    Optional `security_type` filters by type (e.g. 'Bill', 'Note', 'Bond', 'TIPS', 'FRN'). `start_date`/
    `end_date` (YYYY-MM-DD) bound the auction date. Returns CUSIP, term, and key auction dates.
    """
    try:
        filters = [f"security_type:eq:{security_type}"] if security_type else None
        res = await _query("/v1/accounting/od/auctions_query", "auction_date",
                           fields="auction_date,cusip,security_type,security_term,issue_date,maturity_date",
                           filters=filters, sort="-auction_date", page_size=limit,
                           start_date=start_date, end_date=end_date)
    except FiscalError as exc:
        return {"error": str(exc)}
    res.pop("_labels", None)
    res["securityType"] = security_type
    res["rows"] = [{
        "auctionDate": r.get("auction_date"),
        "cusip": r.get("cusip"),
        "securityType": r.get("security_type"),
        "term": r.get("security_term"),
        "issueDate": r.get("issue_date"),
        "maturityDate": r.get("maturity_date"),
    } for r in res.pop("data", [])]
    return res


def main() -> None:
    log.info("MCP Treasury Fiscal Data Server starting on stdio")
    mcp.run()


if __name__ == "__main__":
    main()

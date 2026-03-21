"""
fundamentals.py — EPS growth, revenue growth, and NSE corporate announcements.

Qullamaggie: "fundamentals are the fuel behind the move."
Used by screener.py to tag setups with fundamental context (non-blocking).

Data sources:
  - yfinance quarterly_earnings / quarterly_financials  →  EPS & revenue growth
  - NSE corporate announcements API                    →  recent results / concall
  - yfinance news (fallback)                           →  keyword-based announcement flag
"""
from __future__ import annotations

import time
import requests
from datetime import datetime, timedelta

import pandas as pd

# ── In-process cache (6 h TTL — fundamentals don't change intraday) ──────────
_cache: dict[str, tuple[float, object]] = {}
_CACHE_TTL = 3600 * 6

_NSE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/",
}
_nse_session: requests.Session | None = None


# ── NSE session ───────────────────────────────────────────────────────────────

def _get_nse_session() -> requests.Session:
    global _nse_session
    if _nse_session is None:
        _nse_session = requests.Session()
        _nse_session.headers.update(_NSE_HEADERS)
        try:
            _nse_session.get("https://www.nseindia.com/", timeout=8)
        except Exception:
            pass
    return _nse_session


# ── EPS & Revenue growth ──────────────────────────────────────────────────────

def get_eps_growth(ticker: str) -> dict:
    """
    Returns EPS and revenue growth (QoQ and YoY) from yfinance quarterly data.
    All values in percent. Returns zeros on failure / missing data.
    """
    cache_key = f"eps_{ticker}"
    if cache_key in _cache:
        cached_at, val = _cache[cache_key]
        if time.time() - cached_at < _CACHE_TTL:
            return val  # type: ignore[return-value]

    result = {"eps_qoq": 0.0, "eps_yoy": 0.0, "revenue_qoq": 0.0, "revenue_yoy": 0.0}

    try:
        import yfinance as yf
        t = yf.Ticker(ticker)

        # ── EPS (quarterly earnings) ──────────────────────────────
        qe = t.quarterly_earnings
        if qe is not None and not qe.empty and len(qe) >= 2:
            qe = qe.sort_index(ascending=False)
            eps_cols = [c for c in qe.columns if "earnings" in c.lower() or "eps" in c.lower()]
            if eps_cols:
                col = eps_cols[0]
                eps_now    = float(qe[col].iloc[0])
                eps_prev_q = float(qe[col].iloc[1])
                eps_prev_y = float(qe[col].iloc[4]) if len(qe) >= 5 else None

                if eps_prev_q and eps_prev_q != 0:
                    result["eps_qoq"] = round((eps_now - eps_prev_q) / abs(eps_prev_q) * 100, 1)
                if eps_prev_y is not None and eps_prev_y != 0:
                    result["eps_yoy"] = round((eps_now - eps_prev_y) / abs(eps_prev_y) * 100, 1)

        # ── Revenue (quarterly financials) ────────────────────────
        qf = t.quarterly_financials
        if qf is not None and not qf.empty:
            rev_row = None
            for label in ["Total Revenue", "Revenue", "Net Revenue", "Revenues"]:
                if label in qf.index:
                    rev_row = qf.loc[label]
                    break
            if rev_row is not None and len(rev_row) >= 2:
                rev_now    = float(rev_row.iloc[0])
                rev_prev_q = float(rev_row.iloc[1])
                rev_prev_y = float(rev_row.iloc[3]) if len(rev_row) >= 4 else None

                if rev_prev_q and rev_prev_q != 0:
                    result["revenue_qoq"] = round((rev_now - rev_prev_q) / abs(rev_prev_q) * 100, 1)
                if rev_prev_y is not None and rev_prev_y != 0:
                    result["revenue_yoy"] = round((rev_now - rev_prev_y) / abs(rev_prev_y) * 100, 1)

    except Exception as e:
        print(f"[Fundamentals] EPS/revenue fetch failed for {ticker}: {e}")

    _cache[cache_key] = (time.time(), result)
    return result


# ── NSE corporate announcements ───────────────────────────────────────────────

_CONCALL_KEYWORDS = [
    "financial result", "quarterly result", "unaudited result",
    "conference call", "concall", "investor meet", "analyst meet",
    "board meeting", "q1", "q2", "q3", "q4",
]


def _parse_nse_date(date_str: str) -> datetime | None:
    date_str = date_str.strip()
    for fmt in (
        "%d-%b-%Y %H:%M:%S",  # "21-Mar-2026 08:17:48"
        "%Y-%m-%d %H:%M:%S",  # "2026-03-21 08:17:48"
        "%d-%b-%Y",           # "21-Mar-2026"
        "%Y-%m-%d",           # "2026-03-21"
        "%d-%m-%Y",           # "21-03-2026"
    ):
        try:
            return datetime.strptime(date_str, fmt)
        except Exception:
            continue
    # Last resort: take first 11 chars and try date-only formats
    ds = date_str[:11].strip()
    for fmt in ("%d-%b-%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(ds, fmt)
        except Exception:
            continue
    return None


def get_nse_announcement(ticker: str, days: int = 10) -> bool:
    """
    Returns True if NSE has a results/concall announcement for this ticker
    in the last `days` days. Tries NSE API first, yfinance news as fallback.
    """
    symbol = ticker.replace(".NS", "").replace(".BO", "")
    cache_key = f"nse_ann_{symbol}"

    if cache_key in _cache:
        cached_at, val = _cache[cache_key]
        if time.time() - cached_at < _CACHE_TTL:
            return bool(val)

    cutoff = datetime.now() - timedelta(days=days)

    # ── NSE API ───────────────────────────────────────────────────
    try:
        session = _get_nse_session()
        url = (
            f"https://www.nseindia.com/api/corporate-announcements"
            f"?index=equities&symbol={symbol}"
        )
        resp = session.get(url, timeout=8)
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list):
                for item in data[:30]:
                    subject = (
                        item.get("subject", "") + " " + item.get("desc", "")
                    ).lower()
                    an_date = _parse_nse_date(
                        item.get("an_dt", "") or item.get("sort_date", "")
                    )
                    if an_date and an_date >= cutoff:
                        if any(k in subject for k in _CONCALL_KEYWORDS):
                            _cache[cache_key] = (time.time(), True)
                            return True
                _cache[cache_key] = (time.time(), False)
                return False
    except Exception:
        pass  # fall through to yfinance

    # ── yfinance news fallback ────────────────────────────────────
    result = _yfinance_news_fallback(ticker, days)
    _cache[cache_key] = (time.time(), result)
    return result


def _yfinance_news_fallback(ticker: str, days: int) -> bool:
    try:
        import yfinance as yf
        news = yf.Ticker(ticker).news
        if not news:
            return False
        cutoff_ts = time.time() - (days * 86400)
        keywords = ["result", "quarterly", "q1", "q2", "q3", "q4",
                    "earnings", "concall", "conference", "revenue", "profit"]
        for item in news[:15]:
            if item.get("providerPublishTime", 0) > cutoff_ts:
                title = item.get("title", "").lower()
                if any(k in title for k in keywords):
                    return True
        return False
    except Exception:
        return False


# ── All NSE announcements (for dashboard page) ────────────────────────────────

_CATEGORY_MAP = {
    # Results — NSE desc field values
    "financial result":      "Results",
    "quarterly result":      "Results",
    "unaudited result":      "Results",
    "audited result":        "Results",
    "half yearly result":    "Results",
    "annual result":         "Results",
    "outcome of board meet": "Results",   # often paired with results
    # Concall
    "conference call":       "Concall",
    "concall":               "Concall",
    "investor meet":         "Concall",
    "analyst":               "Concall",
    # Board Meeting
    "board meeting":         "Board Meeting",
    "outcome of board":      "Board Meeting",
    "board of directors":    "Board Meeting",
    # Dividend
    "dividend":              "Dividend",
    # Buyback
    "buyback":               "Buyback",
    "buy-back":              "Buyback",
    # Corporate Action
    "amalgamation":          "Corporate Action",
    "merger":                "Corporate Action",
    "acquisition":           "Corporate Action",
    "scheme":                "Corporate Action",
    "split":                 "Corporate Action",
    "bonus":                 "Corporate Action",
    "rights issue":          "Corporate Action",
}


def get_all_announcements(days: int = 7) -> list[dict]:
    """
    Fetch all NSE corporate announcements for the last `days` days.
    Returns top 50 sorted by date descending, filtered for relevant categories.
    Cached for 30 minutes.
    """
    cache_key = f"all_ann_{days}"
    if cache_key in _cache:
        cached_at, val = _cache[cache_key]
        if time.time() - cached_at < 1800:  # 30 min cache
            return val  # type: ignore[return-value]

    cutoff = datetime.now() - timedelta(days=days)
    results: list[dict] = []

    try:
        session = _get_nse_session()
        to_dt   = datetime.now()
        from_dt = to_dt - timedelta(days=days)
        url = (
            f"https://www.nseindia.com/api/corporate-announcements?index=equities"
            f"&from_date={from_dt.strftime('%d-%m-%Y')}&to_date={to_dt.strftime('%d-%m-%Y')}"
        )
        resp = session.get(url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list):
                for item in data:
                    # NSE API uses 'desc' as the announcement type/subject
                    desc = item.get("desc", "")
                    text = item.get("attchmntText", "")
                    subject_lower = (desc + " " + text).lower()

                    # Parse date — an_dt format: "21-Mar-2026 08:17:48"
                    raw_date = item.get("an_dt", "") or item.get("sort_date", "")
                    an_date = _parse_nse_date(raw_date[:11])  # take date part only
                    if not an_date or an_date < cutoff:
                        continue

                    # Determine category
                    category = None
                    for kw, cat in _CATEGORY_MAP.items():
                        if kw in subject_lower:
                            category = cat
                            break
                    if category is None:
                        continue  # skip press releases, misc

                    results.append({
                        "symbol":   item.get("symbol", ""),
                        "company":  item.get("sm_name", item.get("symbol", "")),
                        "subject":  desc,
                        "category": category,
                        "date":     an_date.strftime("%Y-%m-%d"),
                        "datetime": an_date.isoformat(),
                    })
    except Exception as e:
        print(f"[Fundamentals] All-announcements fetch failed: {e}")

    # Sort by date desc, deduplicate by symbol+date
    seen: set[str] = set()
    deduped: list[dict] = []
    for item in sorted(results, key=lambda x: x["datetime"], reverse=True):
        key = f"{item['symbol']}_{item['date']}_{item['category']}"
        if key not in seen:
            seen.add(key)
            deduped.append(item)

    _cache[cache_key] = (time.time(), deduped[:50])
    return deduped[:50]


# ── Combined entry point ──────────────────────────────────────────────────────

def get_fundamentals(ticker: str) -> dict:
    """
    Full fundamental context for a setup ticker.
    Called by screener.py for each ticker that has a detected setup.
    Cached 6 h — safe to call for every setup in a scan.

    Returns:
        eps_qoq          float   EPS growth quarter-over-quarter (%)
        eps_yoy          float   EPS growth year-over-year (%)
        revenue_qoq      float   Revenue growth QoQ (%)
        revenue_yoy      float   Revenue growth YoY (%)
        has_announcement bool    Recent results/concall in last 10 days
        strong_catalyst  bool    has_announcement AND (eps_yoy > 20% OR revenue_yoy > 15%)
    """
    cache_key = f"fund_{ticker}"
    if cache_key in _cache:
        cached_at, val = _cache[cache_key]
        if time.time() - cached_at < _CACHE_TTL:
            return val  # type: ignore[return-value]

    growth = get_eps_growth(ticker)
    has_ann = get_nse_announcement(ticker, days=10)

    result = {
        **growth,
        "has_announcement": has_ann,
        "strong_catalyst": (
            has_ann and (growth["eps_yoy"] > 20 or growth["revenue_yoy"] > 15)
        ),
    }

    _cache[cache_key] = (time.time(), result)
    return result

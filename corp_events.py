"""
corp_events.py — Bulk NSE corporate announcement feed.

Fetches recent results, concalls, board meetings, dividends from NSE.
Used by the Corp Events dashboard page.

Sources:
  1. NSE bulk corporate announcements API (last N days)
  2. NSE corporate actions API (dividends, splits, bonuses)
"""
from __future__ import annotations

import time
import requests
from datetime import datetime, timedelta
from typing import Literal

# ── 1-hour cache (refreshed automatically) ───────────────────
_cache: dict[str, tuple[float, object]] = {}
_CACHE_TTL = 3600  # 1 hour

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

_CATEGORY_KEYWORDS = {
    "result": [
        "financial result", "quarterly result", "half yearly result",
        "annual result", "unaudited result", "audited result",
        "standalone result", "consolidated result", "q1", "q2", "q3", "q4",
    ],
    "concall": [
        "conference call", "concall", "investor meet", "analyst meet",
        "earnings call", "investor call", "investor presentation",
    ],
    "board": [
        "board meeting", "board of directors", "meeting of board",
    ],
    "dividend": [
        "dividend", "interim dividend", "final dividend", "special dividend",
    ],
    "agm": [
        "annual general meeting", "agm", "extraordinary general meeting", "egm",
    ],
    "split": [
        "stock split", "face value", "sub-division",
    ],
    "buyback": [
        "buyback", "buy-back", "share repurchase",
    ],
}

AnnouncementCategory = Literal["result", "concall", "board", "dividend", "agm", "split", "buyback", "other"]


def _categorize(subject: str) -> AnnouncementCategory:
    text = subject.lower()
    for cat, keywords in _CATEGORY_KEYWORDS.items():
        if any(k in text for k in keywords):
            return cat  # type: ignore[return-value]
    return "other"


def _parse_nse_date(date_str: str) -> datetime | None:
    if not date_str:
        return None
    for fmt in ("%d-%b-%Y %H:%M:%S", "%d-%b-%Y", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(date_str[:19].strip(), fmt)
        except Exception:
            continue
    return None


def _nse_session() -> requests.Session:
    s = requests.Session()
    s.headers.update(_NSE_HEADERS)
    try:
        s.get("https://www.nseindia.com/", timeout=8)
    except Exception:
        pass
    return s


def _fetch_nse_announcements(days_back: int = 7) -> list[dict]:
    """Fetch bulk corporate announcements from NSE (last N days)."""
    cutoff = datetime.now() - timedelta(days=days_back)
    from_date = (datetime.now() - timedelta(days=days_back)).strftime("%d-%m-%Y")
    to_date = datetime.now().strftime("%d-%m-%Y")

    session = _nse_session()
    results = []

    # ── NSE corporate announcements bulk endpoint ─────────────
    try:
        url = (
            f"https://www.nseindia.com/api/corporate-announcements"
            f"?index=equities&from_date={from_date}&to_date={to_date}"
        )
        resp = session.get(url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list):
                for item in data:
                    subject = (item.get("subject") or item.get("desc") or "").strip()
                    symbol  = (item.get("symbol") or item.get("sm_isin") or "").strip()
                    company = (item.get("comp") or item.get("companyName") or symbol).strip()
                    an_date_str = item.get("an_dt") or item.get("sort_date") or ""
                    an_date = _parse_nse_date(an_date_str)

                    if not subject or not symbol:
                        continue
                    if an_date and an_date < cutoff:
                        continue

                    cat = _categorize(subject)
                    results.append({
                        "ticker":   symbol + ".NS",
                        "symbol":   symbol,
                        "company":  company,
                        "subject":  subject,
                        "category": cat,
                        "date":     an_date.strftime("%Y-%m-%d %H:%M") if an_date else "",
                        "date_ts":  an_date.timestamp() if an_date else 0,
                    })
    except Exception as e:
        print(f"[CorpEvents] NSE bulk announcements failed: {e}")

    # ── Fallback: NSE home corporate announcements ────────────
    if not results:
        try:
            resp = session.get(
                "https://www.nseindia.com/api/home-corporate-announcements",
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                items = data if isinstance(data, list) else data.get("data", [])
                for item in items:
                    subject = (item.get("subject") or item.get("headline") or "").strip()
                    symbol  = (item.get("symbol") or "").strip()
                    company = (item.get("comp") or symbol).strip()
                    an_date_str = item.get("an_dt") or item.get("timestamp") or ""
                    an_date = _parse_nse_date(an_date_str)

                    if not subject or not symbol:
                        continue

                    cat = _categorize(subject)
                    results.append({
                        "ticker":   symbol + ".NS",
                        "symbol":   symbol,
                        "company":  company,
                        "subject":  subject,
                        "category": cat,
                        "date":     an_date.strftime("%Y-%m-%d %H:%M") if an_date else "",
                        "date_ts":  an_date.timestamp() if an_date else 0,
                    })
        except Exception as e:
            print(f"[CorpEvents] NSE home announcements fallback failed: {e}")

    return results


def _fetch_nse_corporate_actions(days_back: int = 30) -> list[dict]:
    """Fetch corporate actions (dividends, splits, bonuses) from NSE."""
    from_date = (datetime.now() - timedelta(days=days_back)).strftime("%d-%m-%Y")
    to_date = (datetime.now() + timedelta(days=30)).strftime("%d-%m-%Y")  # include upcoming

    session = _nse_session()
    results = []

    for subject in ["Dividend", "Bonus", "Split"]:
        try:
            url = (
                f"https://www.nseindia.com/api/corporates-corporateActions"
                f"?index=equities&from_date={from_date}&to_date={to_date}&subject={subject}"
            )
            resp = session.get(url, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list):
                    for item in data:
                        symbol = (item.get("symbol") or "").strip()
                        company = (item.get("comp") or symbol).strip()
                        ex_date_str = item.get("exDate") or item.get("ex_date") or ""
                        rec_date_str = item.get("recDate") or ""
                        details = item.get("subject") or item.get("purpose") or subject

                        ex_date = _parse_nse_date(ex_date_str)
                        results.append({
                            "ticker":   symbol + ".NS",
                            "symbol":   symbol,
                            "company":  company,
                            "subject":  f"{subject}: {details}",
                            "category": subject.lower(),
                            "date":     ex_date.strftime("%Y-%m-%d") if ex_date else ex_date_str,
                            "date_ts":  ex_date.timestamp() if ex_date else 0,
                            "ex_date":  ex_date_str,
                            "rec_date": rec_date_str,
                        })
        except Exception as e:
            print(f"[CorpEvents] Corporate actions ({subject}) failed: {e}")

    return results


def get_corp_events(days_back: int = 7, include_actions: bool = True) -> dict:
    """
    Main entry point. Returns:
        announcements: list of recent NSE announcements (results, concalls, etc.)
        actions:       list of upcoming corporate actions (dividends, splits)
        fetched_at:    ISO timestamp of when data was fetched
        cached:        bool
    """
    cache_key = f"corp_events_{days_back}"
    if cache_key in _cache:
        cached_at, val = _cache[cache_key]
        if time.time() - cached_at < _CACHE_TTL:
            return {**val, "cached": True}  # type: ignore[return-value]

    announcements = _fetch_nse_announcements(days_back=days_back)
    actions = _fetch_nse_corporate_actions(days_back=30) if include_actions else []

    # Sort by date descending
    announcements.sort(key=lambda x: x.get("date_ts", 0), reverse=True)
    actions.sort(key=lambda x: x.get("date_ts", 0), reverse=True)

    result = {
        "announcements": announcements,
        "actions": actions,
        "total_announcements": len(announcements),
        "total_actions": len(actions),
        "fetched_at": datetime.now().isoformat(),
        "cached": False,
    }

    _cache[cache_key] = (time.time(), result)
    return result

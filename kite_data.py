"""
kite_data.py — Zerodha Kite Connect as a data source.

Provides:
  - Historical OHLCV (replaces yfinance in screener / backtest)
  - Live quotes (replaces 15-min delayed yfinance in price refresh)
  - Instrument token lookup (NSE ticker → Kite token)

Falls back to yfinance automatically if Kite is not configured / token expired.

Setup:
  1. pip install kiteconnect
  2. Add to .env:
       KITE_API_KEY=your_api_key
       KITE_ACCESS_TOKEN=your_access_token   ← refresh daily via login()
  3. Call kite_data.login_url() once per day, visit URL, paste request_token
     into kite_data.set_access_token(request_token) to generate access token.
"""
from __future__ import annotations

import os
import json
import time
from datetime import datetime, timedelta, date
from pathlib import Path
from typing import Optional

import pandas as pd

# ── Instrument cache ───────────────────────────────────────────
_INSTRUMENT_CACHE = Path("data/kite_instruments.json")
_TOKEN_MAP: dict[str, int] = {}   # "RELIANCE.NS" → 738561
_kite = None                       # KiteConnect instance (lazy init)


# ── Initialise ─────────────────────────────────────────────────

def _get_kite():
    """Return a configured KiteConnect instance, or None if not available."""
    global _kite
    if _kite is not None:
        return _kite
    try:
        from kiteconnect import KiteConnect
        api_key      = os.getenv("KITE_API_KEY", "")
        access_token = os.getenv("KITE_ACCESS_TOKEN", "")
        if not api_key or not access_token:
            return None
        k = KiteConnect(api_key=api_key)
        k.set_access_token(access_token)
        _kite = k
        return _kite
    except ImportError:
        return None
    except Exception as e:
        print(f"[KiteData] Init failed: {e}")
        return None


def is_available() -> bool:
    """True if Kite Connect is configured and the access token is valid."""
    k = _get_kite()
    if k is None:
        return False
    try:
        k.profile()   # lightweight API call to verify token
        return True
    except Exception:
        return False


# ── Daily login flow ────────────────────────────────────────────

def login_url() -> str:
    """
    Returns the Zerodha login URL for the day.
    Visit this URL, log in, and you'll be redirected to your redirect_url
    with a `request_token` query param. Pass that to set_access_token().
    """
    k = _get_kite()
    if k is None:
        return "Kite not configured — set KITE_API_KEY in .env"
    return k.login_url()


def set_access_token(request_token: str) -> str:
    """
    Exchange a one-time request_token for an access_token.
    Call this once per day after logging in via login_url().
    Saves the access_token to .env automatically.
    Requires KITE_API_SECRET in .env.
    """
    global _kite
    try:
        from kiteconnect import KiteConnect
        api_key    = os.getenv("KITE_API_KEY", "")
        api_secret = os.getenv("KITE_API_SECRET", "")
        k = KiteConnect(api_key=api_key)
        session = k.generate_session(request_token, api_secret=api_secret)
        access_token = session["access_token"]
        k.set_access_token(access_token)
        _kite = k

        # Persist to .env
        env_path = Path(".env")
        if env_path.exists():
            lines = env_path.read_text().splitlines()
            new_lines = []
            found = False
            for line in lines:
                if line.startswith("KITE_ACCESS_TOKEN="):
                    new_lines.append(f"KITE_ACCESS_TOKEN={access_token}")
                    found = True
                else:
                    new_lines.append(line)
            if not found:
                new_lines.append(f"KITE_ACCESS_TOKEN={access_token}")
            env_path.write_text("\n".join(new_lines))

        print(f"[KiteData] Access token set and saved.")
        return access_token
    except Exception as e:
        return f"Error: {e}"


# ── Instrument token lookup ─────────────────────────────────────

def _load_instrument_map() -> None:
    """Load NSE ticker → Kite instrument token map from cache."""
    global _TOKEN_MAP
    if _INSTRUMENT_CACHE.exists():
        age_hours = (time.time() - _INSTRUMENT_CACHE.stat().st_mtime) / 3600
        if age_hours < 23:
            _TOKEN_MAP = json.loads(_INSTRUMENT_CACHE.read_text())
            return
    _refresh_instrument_map()


def _refresh_instrument_map() -> None:
    """Fetch full NSE instrument list from Kite and build token map."""
    global _TOKEN_MAP
    k = _get_kite()
    if k is None:
        return
    try:
        instruments = k.instruments("NSE")
        token_map: dict[str, int] = {}
        for inst in instruments:
            sym = inst["tradingsymbol"]
            token_map[sym + ".NS"] = inst["instrument_token"]
            token_map[sym]         = inst["instrument_token"]
        _TOKEN_MAP = token_map
        _INSTRUMENT_CACHE.parent.mkdir(exist_ok=True)
        _INSTRUMENT_CACHE.write_text(json.dumps(token_map))
        print(f"[KiteData] Loaded {len(token_map)} NSE instruments.")
    except Exception as e:
        print(f"[KiteData] Instrument refresh failed: {e}")


def get_token(ticker: str) -> Optional[int]:
    """Return the Kite instrument token for a ticker like 'RELIANCE.NS'."""
    if not _TOKEN_MAP:
        _load_instrument_map()
    token = _TOKEN_MAP.get(ticker) or _TOKEN_MAP.get(ticker.replace(".NS", ""))
    return token


# ── Historical data (replaces yfinance for screener) ───────────

def get_historical_ohlcv(
    ticker: str,
    days: int = 365,
    interval: str = "day",
) -> Optional[pd.DataFrame]:
    """
    Fetch historical OHLCV from Kite Connect.
    Returns a DataFrame indexed by date with columns: Open High Low Close Volume.
    Falls back to yfinance on failure.
    """
    k = _get_kite()
    token = get_token(ticker) if k else None

    if k and token:
        try:
            to_date   = datetime.now()
            from_date = to_date - timedelta(days=days + 10)  # buffer
            candles   = k.historical_data(
                token,
                from_date.strftime("%Y-%m-%d"),
                to_date.strftime("%Y-%m-%d"),
                interval,
            )
            if not candles:
                return _yfinance_fallback(ticker, days)

            df = pd.DataFrame(candles)
            df = df.rename(columns={
                "date": "Date", "open": "Open", "high": "High",
                "low": "Low", "close": "Close", "volume": "Volume",
            })
            df["Date"] = pd.to_datetime(df["Date"])
            df = df.set_index("Date").sort_index()
            df = df.tail(days)
            print(f"[KiteData] {ticker}: {len(df)} bars from Kite")
            return df
        except Exception as e:
            print(f"[KiteData] Historical failed for {ticker}: {e} — using yfinance")

    return _yfinance_fallback(ticker, days)


def _yfinance_fallback(ticker: str, days: int) -> Optional[pd.DataFrame]:
    """Fall back to yfinance when Kite is unavailable."""
    try:
        import yfinance as yf
        period = f"{min(days + 30, 700)}d"
        df = yf.download(ticker, period=period, auto_adjust=True, progress=False)
        if df.empty:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return df.tail(days)
    except Exception as e:
        print(f"[KiteData] yfinance fallback failed for {ticker}: {e}")
        return None


# ── Live quotes (replaces yfinance 15-min delayed price) ────────

def get_live_quotes(tickers: list[str]) -> dict[str, float]:
    """
    Fetch real-time last traded prices from Kite.
    Returns {ticker: price} dict.
    Falls back to yfinance on failure.
    """
    k = _get_kite()
    if not k:
        return _yfinance_live_fallback(tickers)

    if not _TOKEN_MAP:
        _load_instrument_map()

    # Build NSE:SYMBOL list for Kite quote API
    kite_symbols = []
    symbol_map: dict[str, str] = {}   # "NSE:RELIANCE" → "RELIANCE.NS"
    for ticker in tickers:
        sym = ticker.replace(".NS", "")
        kite_sym = f"NSE:{sym}"
        kite_symbols.append(kite_sym)
        symbol_map[kite_sym] = ticker

    if not kite_symbols:
        return {}

    try:
        quotes = k.quote(kite_symbols)
        result: dict[str, float] = {}
        for kite_sym, data in quotes.items():
            original_ticker = symbol_map.get(kite_sym, kite_sym)
            ltp = data.get("last_price")
            if ltp:
                result[original_ticker] = float(ltp)
        print(f"[KiteData] Live quotes: {len(result)}/{len(tickers)} tickers")
        return result
    except Exception as e:
        print(f"[KiteData] Quote fetch failed: {e} — using yfinance")
        return _yfinance_live_fallback(tickers)


def _yfinance_live_fallback(tickers: list[str]) -> dict[str, float]:
    """Fall back to yfinance 1d prices when Kite quotes are unavailable."""
    try:
        import yfinance as yf
        data = yf.download(tickers, period="1d", auto_adjust=True, progress=False)
        if data.empty:
            return {}
        close = data["Close"]
        if hasattr(close, "columns"):
            return {str(c): float(close[c].dropna().iloc[-1])
                    for c in close.columns if not close[c].dropna().empty}
        return {tickers[0]: float(close.dropna().iloc[-1])} if tickers else {}
    except Exception:
        return {}


# ── Chart data (for /chart/{ticker} endpoint) ──────────────────

def get_chart_data(ticker: str, days: int = 120) -> list[dict]:
    """
    Return OHLCV + indicators for the chart modal.
    Tries Kite first, falls back to yfinance.
    """
    df = get_historical_ohlcv(ticker, days=days + 60)
    if df is None or df.empty:
        return []

    df = df.tail(days).copy()
    df["ema10"]  = df["Close"].ewm(span=10, adjust=False).mean()
    df["sma50"]  = df["Close"].rolling(50).mean()
    df["sma200"] = df["Close"].rolling(200).mean()

    import numpy as np
    records = []
    for ts, row in df.iterrows():
        def safe(v):
            return round(float(v), 2) if not (isinstance(v, float) and np.isnan(v)) else None
        records.append({
            "date":   ts.strftime("%Y-%m-%d"),
            "open":   safe(row["Open"]),
            "high":   safe(row["High"]),
            "low":    safe(row["Low"]),
            "close":  safe(row["Close"]),
            "volume": int(row["Volume"]) if not np.isnan(row["Volume"]) else 0,
            "ema10":  safe(row["ema10"]),
            "sma50":  safe(row["sma50"]),
            "sma200": safe(row["sma200"]),
            "source": "kite" if is_available() else "yfinance",
        })
    return records


# ── Opening Range High (ORH) for EP gap-up alerts ──────────────

def get_intraday_orh(ticker: str, minutes: int = 5) -> dict | None:
    """
    Fetch today's intraday 1-minute candles and return the Opening Range High/Low
    from the first `minutes` minutes of the session (default: 5-min ORH).

    Returns {"orh": float, "orl": float, "current_price": float, "candles_used": int}
    or None if Kite is not available or data is missing.

    Used by run_ep_gap_scan() to give a precise entry trigger at 9:15 AM.
    """
    k = _get_kite()
    token = get_token(ticker) if k else None

    if not k or not token:
        return None

    try:
        today = datetime.now().strftime("%Y-%m-%d")
        candles = k.historical_data(token, today, today, "minute")
        if not candles or len(candles) < 1:
            return None

        # Opening range = first `minutes` candles (9:15–9:20 AM for 5-min ORH)
        n = min(minutes, len(candles))
        orh = max(c["high"] for c in candles[:n])
        orl = min(c["low"]  for c in candles[:n])
        current = candles[-1]["close"]

        return {
            "orh":          float(orh),
            "orl":          float(orl),
            "current_price": float(current),
            "candles_used": n,
        }
    except Exception as e:
        print(f"[KiteData] ORH fetch failed for {ticker}: {e}")
        return None


# ── Status summary ──────────────────────────────────────────────

def status() -> dict:
    """Return current Kite data source status."""
    k = _get_kite()
    if k is None:
        return {"connected": False, "reason": "KITE_API_KEY or KITE_ACCESS_TOKEN not set in .env"}
    try:
        profile = k.profile()
        return {
            "connected": True,
            "user":      profile.get("user_name", ""),
            "broker":    profile.get("broker", "Zerodha"),
            "mode":      "live",
        }
    except Exception as e:
        return {"connected": False, "reason": str(e), "fix": "Call /kite/login to get new access token"}

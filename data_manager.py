# ============================================================
# DATA MANAGER — Download, cache, and serve OHLCV price data
# ============================================================
import os
import time
import pandas as pd
import yfinance as yf
import config


def _cache_path(ticker: str, start: str, end: str) -> str:
    """Return the local CSV cache path for a given ticker + date range."""
    os.makedirs(config.CACHE_DIR, exist_ok=True)
    return os.path.join(config.CACHE_DIR, f"{ticker}_{start}_{end}.csv")


def get_price_data(ticker: str, start: str, end: str, force_download: bool = False) -> pd.DataFrame | None:
    """
    Return OHLCV DataFrame for ticker between start and end (inclusive).
    Uses a local CSV cache to avoid redundant downloads.
    Returns None if data is insufficient or download fails.
    """
    cache_file = _cache_path(ticker, start, end)

    if not force_download and os.path.exists(cache_file):
        df = pd.read_csv(cache_file, index_col=0, parse_dates=True)
    else:
        try:
            raw = yf.download(ticker, start=start, end=end, auto_adjust=True, progress=False)
            if raw.empty:
                print(f"  [SKIP] {ticker}: no data returned")
                return None
            # Flatten multi-level columns if present
            if isinstance(raw.columns, pd.MultiIndex):
                raw.columns = raw.columns.get_level_values(0)
            df = raw[["Open", "High", "Low", "Close", "Volume"]].copy()
            df.index = pd.to_datetime(df.index)
            df.sort_index(inplace=True)
            df.to_csv(cache_file)
        except Exception as e:
            print(f"  [ERROR] {ticker}: {e}")
            return None

    # Clean: drop rows with zero volume or NaN closes
    df = df[df["Volume"] > 0].dropna(subset=["Close", "Open", "High", "Low"])
    df.index = pd.to_datetime(df.index)

    if len(df) < 150:
        print(f"  [SKIP] {ticker}: insufficient history ({len(df)} rows)")
        return None

    return df


def get_multiple_tickers(
    tickers: list[str],
    start: str = config.DEFAULT_START,
    end: str = config.DEFAULT_END,
    delay: float = 0.3,
    force_download: bool = False,
) -> dict[str, pd.DataFrame]:
    """
    Download and return a dict of {ticker: DataFrame} for all tickers.
    Skips tickers with insufficient history.
    `delay` throttles requests to avoid yfinance rate limits.
    """
    result = {}
    total = len(tickers)
    for i, ticker in enumerate(tickers, 1):
        print(f"  [{i}/{total}] {ticker}...", end=" ")
        df = get_price_data(ticker, start, end, force_download=force_download)
        if df is not None:
            result[ticker] = df
            print(f"OK ({len(df)} rows)")
        time.sleep(delay)
    return result


def invalidate_cache(ticker: str, start: str, end: str) -> None:
    """Delete a cached file so it re-downloads on next request."""
    path = _cache_path(ticker, start, end)
    if os.path.exists(path):
        os.remove(path)
        print(f"Cache cleared: {path}")


def get_recent_data(ticker: str, lookback_days: int = 350) -> pd.DataFrame | None:
    """
    Convenience wrapper for the screener: fetch the last N calendar days.
    Uses Kite Connect if available (real NSE data), otherwise yfinance.
    """
    try:
        from kite_data import get_historical_ohlcv, is_available
        if is_available():
            df = get_historical_ohlcv(ticker, days=lookback_days)
            if df is not None and len(df) >= 150:
                df = df[df["Volume"] > 0].dropna(subset=["Close", "Open", "High", "Low"])
                return df
    except ImportError:
        pass

    # yfinance fallback
    end   = pd.Timestamp.today().strftime("%Y-%m-%d")
    start = (pd.Timestamp.today() - pd.Timedelta(days=lookback_days)).strftime("%Y-%m-%d")
    return get_price_data(ticker, start, end, force_download=True)

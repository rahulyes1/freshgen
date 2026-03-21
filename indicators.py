# ============================================================
# INDICATORS — Pure functions on OHLCV DataFrames
# ============================================================
# All functions take a DataFrame and return a Series.
# No side effects. No look-ahead bias (all rolling windows use min_periods=1
# only where appropriate; signals are generated on complete windows).

import numpy as np
import pandas as pd


# ── Trend Indicators ─────────────────────────────────────────

def sma(df: pd.DataFrame, period: int, col: str = "Close") -> pd.Series:
    """Simple Moving Average."""
    return df[col].rolling(period, min_periods=period).mean()


def ema(df: pd.DataFrame, period: int, col: str = "Close") -> pd.Series:
    """Exponential Moving Average."""
    return df[col].ewm(span=period, adjust=False).mean()


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Average True Range (Wilder's method)."""
    high = df["High"]
    low = df["Low"]
    prev_close = df["Close"].shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.rolling(period, min_periods=period).mean()


def volume_sma(df: pd.DataFrame, period: int = 50) -> pd.Series:
    """Simple moving average of volume (excludes current bar in rolling)."""
    # Shift by 1 so current bar is excluded from its own average
    return df["Volume"].shift(1).rolling(period, min_periods=20).mean()


def rolling_high(df: pd.DataFrame, period: int, col: str = "High") -> pd.Series:
    """Rolling maximum of High over last `period` bars."""
    return df[col].rolling(period, min_periods=period).max()


def rolling_low(df: pd.DataFrame, period: int, col: str = "Low") -> pd.Series:
    """Rolling minimum of Low over last `period` bars."""
    return df[col].rolling(period, min_periods=period).min()


def rsi(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Relative Strength Index."""
    delta = df["Close"].diff()
    gain = delta.clip(lower=0).rolling(period, min_periods=period).mean()
    loss = (-delta.clip(upper=0)).rolling(period, min_periods=period).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


# ── Composite Filters ─────────────────────────────────────────

def in_uptrend(df: pd.DataFrame, sma_short: int = 50, sma_long: int = 150) -> pd.Series:
    """
    Returns True where Close > SMA(short) and Close > SMA(long).
    Classic Qullamaggie trend filter.
    """
    close = df["Close"]
    s_short = sma(df, sma_short)
    s_long = sma(df, sma_long)
    return (close > s_short) & (close > s_long)


def near_52w_high(df: pd.DataFrame, max_distance: float = 0.25) -> pd.Series:
    """
    Returns True where Close is within max_distance of 52-week high.
    E.g., max_distance=0.25 means within 25% of the high.
    """
    high_52w = rolling_high(df, 252)
    return df["Close"] >= high_52w * (1 - max_distance)


def volume_ratio(df: pd.DataFrame, avg_period: int = 50) -> pd.Series:
    """Current day's volume divided by N-day average volume (prior bars only)."""
    avg_vol = volume_sma(df, avg_period)
    return df["Volume"] / avg_vol


def gap_up_pct(df: pd.DataFrame) -> pd.Series:
    """
    Percentage gap-up: (today's Open - yesterday's Close) / yesterday's Close.
    Positive = gap up, negative = gap down.
    """
    return (df["Open"] - df["Close"].shift(1)) / df["Close"].shift(1)


def close_position_in_range(df: pd.DataFrame) -> pd.Series:
    """
    Where the close sits within the day's high-low range.
    1.0 = closed at high, 0.0 = closed at low, 0.5 = midpoint.
    """
    day_range = df["High"] - df["Low"]
    # Avoid division by zero on doji candles
    day_range = day_range.replace(0, np.nan)
    return (df["Close"] - df["Low"]) / day_range


def compute_rs_raw(df: pd.DataFrame) -> float:
    """
    IBD-style Relative Strength raw score.
    Weighted return: 40% 1M + 20% 3M + 15% 6M + 15% 12M + 10% 18M.
    Matches Qullamaggie's 1M/3M/6M/12M/18M scan timeframes.
    Call for each stock, then percentile-rank across the universe.
    """
    def pret(days: int) -> float:
        if len(df) < days + 1:
            return 0.0
        s = float(df["Close"].iloc[-days])
        e = float(df["Close"].iloc[-1])
        return (e - s) / s if s > 0 else 0.0

    r1m  = pret(21)
    r3m  = pret(63)
    r6m  = pret(126)
    r12m = pret(252)
    r18m = pret(378)
    return r1m * 0.40 + r3m * 0.20 + r6m * 0.15 + r12m * 0.15 + r18m * 0.10


def add_all_indicators(df: pd.DataFrame, cfg) -> pd.DataFrame:
    """
    Compute and attach all indicators needed by the pattern detectors.
    Returns a copy of df with new columns added.
    This is called once per ticker before pattern scanning.
    """
    df = df.copy()
    df["SMA50"]       = sma(df, cfg.SMA_SHORT)
    df["SMA150"]      = sma(df, cfg.SMA_LONG)
    df["EMA10"]       = ema(df, cfg.EMA_TRAIL)
    df["ATR14"]       = atr(df, cfg.ATR_PERIOD)
    df["VolSMA50"]    = volume_sma(df, cfg.VOLUME_AVG_PERIOD)
    df["VolRatio"]    = volume_ratio(df, cfg.VOLUME_AVG_PERIOD)
    df["High52W"]     = rolling_high(df, 252)
    df["Low52W"]      = rolling_low(df, 252)
    df["GapPct"]      = gap_up_pct(df)
    df["ClosePos"]    = close_position_in_range(df)
    df["InUptrend"]   = in_uptrend(df, cfg.SMA_SHORT, cfg.SMA_LONG)
    df["Near52WHigh"] = near_52w_high(df, cfg.PRICE_FROM_52W_HIGH_MAX)
    return df

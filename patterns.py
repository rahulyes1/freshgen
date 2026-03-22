# ============================================================
# PATTERNS — Breakout and Episodic Pivot detection
# ============================================================
# Based on Kristjan Kullamägi's trading methodology:
#   • Breakout: stock consolidates 3-12 weeks, then breaks out on high volume
#   • Episodic Pivot: gap-up on huge volume from a fundamental catalyst
#
# IMPORTANT: No look-ahead bias. All signals are generated using only
# data available up to and including the signal bar (day i).

import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from typing import Literal
import config as cfg


@dataclass
class Setup:
    """A trading setup signal."""
    ticker: str
    date: pd.Timestamp
    pattern: Literal["BREAKOUT", "EP", "VCP", "SA"]
    signal_price: float          # Close of the signal bar
    entry_price: float           # Intended entry (next open or signal close)
    initial_stop: float          # Initial stop-loss level
    hard_stop: float             # Hard-cap stop (entry * (1 - STOP_MAX_PCT))
    stop_price: float            # Effective stop = max(initial_stop, hard_stop)
    risk_pct: float              # (entry - stop) / entry
    volume_ratio: float          # Signal bar volume vs 50-day avg
    base_high: float = 0.0       # Highest high of consolidation base (Breakout only)
    base_low: float = 0.0        # Lowest low of consolidation base (Breakout only)
    base_days: int = 0           # Length of base in trading days
    gap_pct: float = 0.0         # Gap-up % (EP only)
    notes: str = ""


def _find_consolidation_base(df: pd.DataFrame, i: int) -> tuple[float, float, int] | None:
    """
    Look backward from row i to find a valid tight consolidation base.
    Returns (base_high, base_low, base_length) or None if no valid base found.

    A valid base:
    - Length between CONSOLIDATION_DAYS_MIN and CONSOLIDATION_DAYS_MAX
    - High-to-low range <= CONSOLIDATION_RANGE_MAX
    - ATR during base is contracted vs prior equivalent period
    """
    min_days = cfg.CONSOLIDATION_DAYS_MIN
    max_days = cfg.CONSOLIDATION_DAYS_MAX

    # We need enough prior data for ATR comparison
    if i < max_days + min_days:
        return None

    close_series = df["Close"]
    high_series = df["High"]
    low_series = df["Low"]
    atr_series = df["ATR14"]

    best = None  # (range_pct, base_high, base_low, base_length)

    for base_len in range(min_days, min(max_days + 1, i - min_days)):
        # Base window: rows [i - base_len, i-1] (exclude today)
        start_idx = i - base_len
        end_idx = i  # exclusive → slice [start_idx:i]

        base_high = high_series.iloc[start_idx:end_idx].max()
        base_low = low_series.iloc[start_idx:end_idx].min()

        if base_low <= 0:
            continue

        range_pct = (base_high - base_low) / base_low

        if range_pct > cfg.CONSOLIDATION_RANGE_MAX:
            continue

        # ATR contraction check: compare base ATR vs prior-period ATR
        prior_start = max(0, start_idx - base_len)
        atr_base = atr_series.iloc[start_idx:end_idx].mean()
        atr_prior = atr_series.iloc[prior_start:start_idx].mean()

        if pd.isna(atr_base) or pd.isna(atr_prior) or atr_prior == 0:
            continue

        if atr_base > cfg.ATR_CONTRACTION_RATIO * atr_prior:
            # ATR is NOT contracted enough
            continue

        # ── Linearity: filter out choppy/distributive bases ──────
        # 1. No more than 1 gap-down > 3% in the base (distribution signal)
        if "GapPct" in df.columns:
            base_gaps = df["GapPct"].iloc[start_idx:end_idx]
            if (base_gaps < -0.03).sum() > 1:
                continue

        # 2. No violent spike days — range > 2.5x average base range
        base_daily_ranges = high_series.iloc[start_idx:end_idx] - low_series.iloc[start_idx:end_idx]
        avg_daily_range = base_daily_ranges.mean()
        if avg_daily_range > 0 and (base_daily_ranges > 2.5 * avg_daily_range).sum() > 2:
            continue

        # Valid base found — prefer the tightest range
        if best is None or range_pct < best[0]:
            best = (range_pct, base_high, base_low, base_len)

    if best is None:
        return None
    return best[1], best[2], best[3]  # base_high, base_low, base_length


def find_breakout_setups(df: pd.DataFrame, ticker: str) -> list[Setup]:
    """
    Scan df for Breakout setups and return a list of Setup objects.

    Entry conditions (all must be true on signal bar):
    1. Stock is in uptrend: Close > SMA50 > SMA150
    2. Stock near 52-week high: within PRICE_FROM_52W_HIGH_MAX
    3. Valid tight consolidation base found in the lookback window
    4. Today's close breaks above the base high
    5. Today's volume >= BREAKOUT_VOLUME_MULTIPLIER x 50-day avg volume
    """
    setups = []
    n = len(df)

    for i in range(cfg.CONSOLIDATION_DAYS_MIN + 60, n):
        row = df.iloc[i]

        # ── Filter 1: Uptrend ──────────────────────────────────
        if not row.get("InUptrend", False):
            continue

        # ── Filter 2: Near 52-week high ────────────────────────
        if not row.get("Near52WHigh", False):
            continue

        # ── Filter 3: Volume surge ─────────────────────────────
        vol_ratio = row.get("VolRatio", 0)
        if vol_ratio < cfg.BREAKOUT_VOLUME_MULTIPLIER:
            continue

        # ── Filter 4: Breakout above prior high ────────────────
        # Today's close must be higher than recent bars
        recent_high = df["High"].iloc[i - cfg.CONSOLIDATION_DAYS_MIN:i].max()
        if row["Close"] <= recent_high * 0.995:  # small tolerance
            continue

        # ── Filter 5: Valid consolidation base ────────────────
        base_result = _find_consolidation_base(df, i)
        if base_result is None:
            continue

        base_high, base_low, base_days = base_result

        # Signal bar close must be breaking above base high
        if row["Close"] < base_high:
            continue

        # ── Compute stops and risk ─────────────────────────────
        # Entry: next bar's open (approximated as today's close for backtesting)
        entry = row["Close"]
        initial_stop = base_low
        hard_stop = entry * (1 - cfg.STOP_MAX_PCT)
        stop = max(initial_stop, hard_stop)
        risk_pct = (entry - stop) / entry

        # Skip if the stop is effectively the hard cap (base too wide)
        if risk_pct > cfg.STOP_MAX_PCT * 1.01:
            continue

        # Skip if risk is trivially small (over-tight base)
        if risk_pct < 0.01:
            continue

        setups.append(Setup(
            ticker=ticker,
            date=df.index[i],
            pattern="BREAKOUT",
            signal_price=row["Close"],
            entry_price=entry,
            initial_stop=initial_stop,
            hard_stop=hard_stop,
            stop_price=stop,
            risk_pct=risk_pct,
            volume_ratio=vol_ratio,
            base_high=base_high,
            base_low=base_low,
            base_days=base_days,
        ))

    return setups


def find_ep_setups(df: pd.DataFrame, ticker: str) -> list[Setup]:
    """
    Scan df for Episodic Pivot (gap-up) setups.

    Entry conditions (all must be true on signal bar):
    1. Gap-up: today's open >= yesterday's close * (1 + EP_GAP_MIN)
    2. Volume surge: volume >= EP_VOLUME_MULTIPLIER x 50-day avg
    3. Strong close: close in top 50% of the day's range
    4. Minimum trend: close > SMA50 (relaxed — EPs can start new trends)
    5. No recent gap-up in last 15 days (avoid chasing extended moves)
    """
    setups = []
    n = len(df)

    for i in range(60, n):
        row = df.iloc[i]

        # ── Filter 1: Gap-up ──────────────────────────────────
        gap_pct = row.get("GapPct", 0)
        if gap_pct < cfg.EP_GAP_MIN:
            continue

        # ── Filter 2: Volume surge ────────────────────────────
        vol_ratio = row.get("VolRatio", 0)
        if vol_ratio < cfg.EP_VOLUME_MULTIPLIER:
            continue

        # ── Filter 3: Strong close ────────────────────────────
        close_pos = row.get("ClosePos", 0)
        if cfg.EP_CLOSE_IN_TOP_HALF and close_pos < 0.5:
            continue

        # ── Filter 4: Minimum trend (above SMA50) ────────────
        sma50 = row.get("SMA50")
        if sma50 is None or pd.isna(sma50):
            continue
        if row["Close"] < sma50 * 0.95:  # allow 5% tolerance for EPs starting trends
            continue

        # ── Filter 5: No recent gap-up in last 15 bars ───────
        recent_gaps = df["GapPct"].iloc[max(0, i - 15):i]
        if (recent_gaps >= cfg.EP_GAP_MIN).any():
            continue

        # ── Compute stops and risk ────────────────────────────
        # For EP: stop is below the EP candle's low
        entry = row["Close"]
        initial_stop = row["Low"]
        hard_stop = entry * (1 - cfg.STOP_MAX_PCT)
        stop = max(initial_stop, hard_stop)
        risk_pct = (entry - stop) / entry

        if risk_pct < 0.005:
            continue

        setups.append(Setup(
            ticker=ticker,
            date=df.index[i],
            pattern="EP",
            signal_price=row["Close"],
            entry_price=entry,
            initial_stop=initial_stop,
            hard_stop=hard_stop,
            stop_price=stop,
            risk_pct=risk_pct,
            volume_ratio=vol_ratio,
            gap_pct=gap_pct,
        ))

    return setups


def _find_vcp_contractions(highs: pd.Series, lows: pd.Series, n_segments: int = 4) -> list[dict] | None:
    """
    Divide the price window into n_segments equal segments.
    Return a list of dicts with high/low/range_pct for each segment,
    or None if data is insufficient.
    """
    total = len(highs)
    if total < n_segments * 5:
        return None

    seg_size = total // n_segments
    contractions = []
    for k in range(n_segments):
        start = k * seg_size
        end = start + seg_size
        seg_high = float(highs.iloc[start:end].max())
        seg_low  = float(lows.iloc[start:end].min())
        if seg_low <= 0:
            return None
        range_pct = (seg_high - seg_low) / seg_low
        contractions.append({"high": seg_high, "low": seg_low, "range_pct": range_pct})
    return contractions


def find_vcp_setups(df: pd.DataFrame, ticker: str) -> list[Setup]:
    """
    Volatility Contraction Pattern (VCP) — Mark Minervini style.

    Conditions (all must be true on signal bar i):
    1. Stock in uptrend (InUptrend flag)
    2. Near 52-week high (within 25%)
    3. Lookback window shows 4 price segments with progressively tighter ranges
    4. Each segment's range is at most 70% of the prior segment's range
    5. Volume declining across segments (VCP volume signature)
    6. Final (tightest) contraction range <= 10%
    7. Today's close breaks above the last segment's high
    8. Volume surge: >= BREAKOUT_VOLUME_MULTIPLIER x 50-day avg
    """
    setups = []
    n = len(df)
    LOOKBACK = 80  # bars (~16 weeks) for VCP structure

    for i in range(200, n):
        row = df.iloc[i]

        # ── Filter 1: Uptrend ────────────────────────────────
        if not row.get("InUptrend", False):
            continue

        # ── Filter 2: Near 52-week high ──────────────────────
        if not row.get("Near52WHigh", False):
            continue

        # ── Filter 3: Volume surge on breakout bar ───────────
        vol_ratio = row.get("VolRatio", 0)
        if vol_ratio < cfg.BREAKOUT_VOLUME_MULTIPLIER:
            continue

        # ── Filter 4: VCP structure in the lookback window ───
        start = max(0, i - LOOKBACK)
        window_highs = df["High"].iloc[start:i]
        window_lows  = df["Low"].iloc[start:i]
        window_vol   = df["Volume"].iloc[start:i]

        contractions = _find_vcp_contractions(window_highs, window_lows, n_segments=4)
        if contractions is None:
            continue

        # Each segment range must be <= 70% of the previous segment's range
        valid = True
        for k in range(1, len(contractions)):
            prev_range = contractions[k - 1]["range_pct"]
            this_range = contractions[k]["range_pct"]
            if prev_range <= 0 or this_range > prev_range * 0.70:
                valid = False
                break
        if not valid:
            continue

        # ── Filter 5: Volume declining across segments ────────
        seg_size = len(window_vol) // 4
        seg_vols = [float(window_vol.iloc[k * seg_size:(k + 1) * seg_size].mean()) for k in range(4)]
        # Volume should be lower in later segments (allow one exception)
        vol_drops = sum(seg_vols[k] < seg_vols[k - 1] for k in range(1, 4))
        if vol_drops < 2:
            continue

        # ── Filter 6: Final contraction tight (<= 10%) ───────
        last_range_pct = contractions[-1]["range_pct"]
        if last_range_pct > 0.10:
            continue

        # ── Filter 7: Breakout above last contraction high ───
        last_high = contractions[-1]["high"]
        if row["Close"] < last_high:
            continue

        # ── Compute stops and risk ────────────────────────────
        entry = row["Close"]
        initial_stop = contractions[-1]["low"]
        hard_stop    = entry * (1 - cfg.STOP_MAX_PCT)
        stop         = max(initial_stop, hard_stop)
        risk_pct     = (entry - stop) / entry

        if risk_pct < 0.01 or risk_pct > cfg.STOP_MAX_PCT * 1.01:
            continue

        setups.append(Setup(
            ticker=ticker,
            date=df.index[i],
            pattern="VCP",
            signal_price=row["Close"],
            entry_price=entry,
            initial_stop=initial_stop,
            hard_stop=hard_stop,
            stop_price=stop,
            risk_pct=risk_pct,
            volume_ratio=vol_ratio,
            base_high=last_high,
            base_low=initial_stop,
            base_days=LOOKBACK,
            notes=f"VCP {len(contractions)}-C | final {last_range_pct*100:.1f}%",
        ))

    return setups


def find_supply_absorption_setups(df: pd.DataFrame, ticker: str) -> list[Setup]:
    """
    Supply Absorption (SA) — Demand thrust followed by orderly pullback on drying volume.

    Concept (from Nitin's framework):
    "Supply absorption preceded by recent high-volume demand expansion
     in an orderly stage-2 structure"

    Detection logic:
    1. Stage-2: Close > rising SMA50 > SMA150 (orderly uptrend)
    2. Demand thrust: a recent window with ≥4% gain on ≥2× volume (institutional buying)
    3. Pullback absorption: price pulls back 1-5 weeks on DECLINING volume
       → sellers drying up, supply being absorbed
    4. Tight range at end of pullback (≤6%) — coiling before next move
    5. Close reclaims above 10-EMA (buyers stepping back in)
    """
    setups = []
    n = len(df)

    for i in range(200, n):
        row = df.iloc[i]

        # ── Filter 1: Stage-2 uptrend (strict) ───────────────
        if not row.get("InUptrend", False):
            continue

        # Rising SMA50 (slope positive over last 10 bars)
        sma50_now = row.get("SMA50")
        if sma50_now is None or pd.isna(sma50_now):
            continue
        sma50_10ago = df["SMA50"].iloc[i - 10] if i >= 10 else sma50_now
        if pd.isna(sma50_10ago) or sma50_now <= sma50_10ago:
            continue  # SMA50 must be rising

        # ── Filter 2: Near 52-week high ──────────────────────
        if not row.get("Near52WHigh", False):
            continue

        # ── Filter 3: Recent demand thrust in lookback window ─
        thrust_lookback = cfg.SA_THRUST_LOOKBACK
        thrust_found = False
        thrust_end = 0
        thrust_high = 0.0
        thrust_vol_avg = 0.0

        # Search for a high-volume thrust move ending 5-25 bars ago
        for pb_len in range(cfg.SA_PULLBACK_DAYS_MIN, min(cfg.SA_PULLBACK_DAYS_MAX + 1, i - thrust_lookback)):
            thrust_end_idx = i - pb_len
            thrust_start_idx = max(0, thrust_end_idx - thrust_lookback)

            if thrust_start_idx < 60:
                continue

            thrust_close_start = df["Close"].iloc[thrust_start_idx]
            thrust_close_end = df["Close"].iloc[thrust_end_idx]

            if thrust_close_start <= 0:
                continue

            thrust_gain = (thrust_close_end - thrust_close_start) / thrust_close_start
            if thrust_gain < cfg.SA_THRUST_MOVE_MIN:
                continue

            # Check for at least 2 high-volume bars in the thrust window
            thrust_vol = df["VolRatio"].iloc[thrust_start_idx:thrust_end_idx + 1]
            hv_bars = (thrust_vol >= cfg.SA_THRUST_VOL_MULT).sum()
            if hv_bars < 2:
                continue

            thrust_found = True
            thrust_end = thrust_end_idx
            thrust_high = df["High"].iloc[thrust_start_idx:thrust_end_idx + 1].max()
            thrust_vol_avg = df["Volume"].iloc[thrust_start_idx:thrust_end_idx + 1].mean()
            break

        if not thrust_found:
            continue

        # ── Filter 4: Pullback on declining volume ────────────
        pb_start = thrust_end + 1
        pb_end = i  # today
        pb_len_actual = pb_end - pb_start

        if pb_len_actual < cfg.SA_PULLBACK_DAYS_MIN:
            continue

        pb_low = df["Low"].iloc[pb_start:pb_end].min()
        pb_depth = (thrust_high - pb_low) / thrust_high if thrust_high > 0 else 1.0

        if pb_depth > cfg.SA_PULLBACK_DEPTH_MAX:
            continue  # Pulled back too deep — not orderly

        # Volume decline: pullback volume should be ≤70% of thrust volume
        pb_vol_avg = df["Volume"].iloc[pb_start:pb_end].mean()
        if thrust_vol_avg > 0 and pb_vol_avg > cfg.SA_PULLBACK_VOL_DECLINE * thrust_vol_avg:
            continue  # Volume NOT declining enough — supply not absorbed

        # ── Filter 5: Tight range at end of pullback ──────────
        last_5 = df.iloc[max(pb_start, i - 5):i]
        if len(last_5) < 3:
            continue
        tight_high = last_5["High"].max()
        tight_low = last_5["Low"].min()
        tight_range = (tight_high - tight_low) / tight_low if tight_low > 0 else 1.0

        if tight_range > cfg.SA_ABSORPTION_RANGE_MAX:
            continue  # Not tight enough — supply still present

        # ── Filter 6: Close reclaims 10-EMA (buyers stepping in) ──
        ema10 = row.get("EMA10")
        if ema10 is None or pd.isna(ema10):
            continue
        if row["Close"] < ema10:
            continue  # Still below short-term trend — not ready

        # ── Compute stops and risk ────────────────────────────
        entry = row["Close"]
        initial_stop = pb_low  # Below the pullback low
        hard_stop = entry * (1 - cfg.STOP_MAX_PCT)
        stop = max(initial_stop, hard_stop)
        risk_pct = (entry - stop) / entry

        if risk_pct < 0.01 or risk_pct > cfg.STOP_MAX_PCT * 1.01:
            continue

        vol_ratio = row.get("VolRatio", 0)

        setups.append(Setup(
            ticker=ticker,
            date=df.index[i],
            pattern="SA",
            signal_price=row["Close"],
            entry_price=entry,
            initial_stop=initial_stop,
            hard_stop=hard_stop,
            stop_price=stop,
            risk_pct=risk_pct,
            volume_ratio=vol_ratio,
            base_high=thrust_high,
            base_low=pb_low,
            base_days=pb_len_actual,
            notes=f"SA thrust +{thrust_gain*100:.0f}% → pullback {pb_depth*100:.0f}% depth, vol decline {pb_vol_avg/thrust_vol_avg*100:.0f}%",
        ))

    return setups


def find_all_setups(df: pd.DataFrame, ticker: str) -> list[Setup]:
    """Find Breakout, EP, VCP, and Supply Absorption setups, sorted by date."""
    breakouts = find_breakout_setups(df, ticker)
    eps = find_ep_setups(df, ticker)
    vcps = find_vcp_setups(df, ticker)
    sas = find_supply_absorption_setups(df, ticker)
    all_setups = breakouts + eps + vcps + sas
    all_setups.sort(key=lambda s: s.date)
    return all_setups


def deduplicate_setups(setups: list[Setup], cooldown_days: int = 20) -> list[Setup]:
    """
    For each ticker, enforce a minimum cooldown_days between setups.
    If two setups are within cooldown_days of each other, keep the first one.
    EP takes priority over BREAKOUT if both appear on the same day.
    """
    by_ticker: dict[str, list[Setup]] = {}
    for s in setups:
        by_ticker.setdefault(s.ticker, []).append(s)

    result = []
    for ticker, ticker_setups in by_ticker.items():
        ticker_setups.sort(key=lambda s: (s.date, 0 if s.pattern == "EP" else 1))
        last_date = None
        for s in ticker_setups:
            if last_date is None or (s.date - last_date).days >= cooldown_days:
                result.append(s)
                last_date = s.date

    result.sort(key=lambda s: s.date)
    return result

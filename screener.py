# ============================================================
# SCREENER — Daily live screening for Breakout, EP, and VCP setups
# ============================================================
# Run this each morning before market open to find today's candidates.
# Uses the last 350 days of data to have all indicators available.

import pandas as pd
from indicators import add_all_indicators, compute_rs_raw
from patterns import find_all_setups
import config as cfg


def _earnings_guard(ticker: str, days: int = 7) -> bool:
    """
    Returns True if the ticker has earnings within the next `days` days.
    Signals should be flagged (not blocked) if earnings are nearby.
    """
    try:
        import yfinance as yf
        from datetime import date, timedelta
        cal = yf.Ticker(ticker).calendar
        if cal is None:
            return False
        today = date.today()
        cutoff = today + timedelta(days=days)
        # calendar is a dict with 'Earnings Date' key (list of dates)
        if isinstance(cal, dict):
            dates = cal.get("Earnings Date", [])
            if not hasattr(dates, "__iter__"):
                dates = [dates]
            for d in dates:
                try:
                    d_date = d.date() if hasattr(d, "date") else d
                    if today <= d_date <= cutoff:
                        return True
                except Exception:
                    pass
        return False
    except Exception:
        return False


def screen_ticker(df: pd.DataFrame, ticker: str, lookback_bars: int = 5,
                  indicators_added: bool = False) -> list[dict]:
    """
    Screen a single ticker for fresh setups in the last `lookback_bars` bars.
    Pass indicators_added=True if add_all_indicators has already been applied.
    Returns a list of setup dicts, or empty list if no fresh setups found.
    """
    if len(df) < 100:
        return []

    if not indicators_added:
        df = add_all_indicators(df, cfg)
    setups = find_all_setups(df, ticker)

    if not setups:
        return []

    # Keep only fresh setups (last N bars)
    cutoff = df.index[-lookback_bars]
    fresh_setups = [s for s in setups if s.date >= cutoff]

    rows = []
    for s in fresh_setups:
        # Distance from 52-week high
        idx = df.index.get_loc(s.date)
        bar = df.iloc[idx]
        high_52w = bar.get("High52W", bar["Close"])
        distance_52w = (high_52w - bar["Close"]) / high_52w * 100

        # ATR14 at signal bar (for position sizing floor)
        atr14 = float(bar.get("ATR14", 0) or 0)

        rows.append({
            "ticker":            ticker,
            "date":              s.date.strftime("%Y-%m-%d"),
            "pattern":           s.pattern,
            "entry_price":       round(s.entry_price, 2),
            "stop_price":        round(s.stop_price, 2),
            "risk_pct":          round(s.risk_pct * 100, 2),
            "volume_ratio":      round(s.volume_ratio, 1),
            "distance_52w_pct":  round(distance_52w, 1),
            "base_weeks":        round(s.base_days / 5, 1) if s.base_days > 0 else "-",
            "gap_pct":           round(s.gap_pct * 100, 2) if s.gap_pct else 0.0,
            "atr14":             round(atr14, 2),
            "rs_rank":           0,    # filled in by run_screener after universe ranking
            "near_earnings":     False, # filled in by run_screener
            # Fundamentals — filled in by run_screener after setup detection
            "eps_qoq":           0.0,
            "eps_yoy":           0.0,
            "revenue_qoq":       0.0,
            "revenue_yoy":       0.0,
            "has_announcement":  False,
            "strong_catalyst":   False,
        })

    return rows


def run_screener(
    tickers: list[str],
    lookback_days: int = 350,
    fresh_bars: int = 5,
    check_earnings: bool = True,
) -> pd.DataFrame:
    """
    Screen a list of tickers for live setups.
    Downloads the most recent `lookback_days` of data for each ticker.
    Returns a DataFrame of found setups sorted by rs_rank descending.
    """
    from data_manager import get_recent_data
    import time

    all_rows = []
    rs_raw_scores: dict[str, float] = {}
    total = len(tickers)

    for i, ticker in enumerate(tickers, 1):
        print(f"  Screening [{i}/{total}] {ticker}...", end=" ", flush=True)
        df = get_recent_data(ticker, lookback_days=lookback_days)
        if df is None:
            print("no data")
            continue

        df_ind = add_all_indicators(df, cfg)

        # RS raw score for ALL tickers (not just setups) for accurate percentile ranking
        rs_raw_scores[ticker] = compute_rs_raw(df_ind)

        rows = screen_ticker(df_ind, ticker, lookback_bars=fresh_bars, indicators_added=True)
        if rows:
            all_rows.extend(rows)
            print(f"SETUP FOUND — {rows[0]['pattern']}")
        else:
            print("clear")
        time.sleep(0.3)

    if not all_rows:
        return pd.DataFrame()

    # ── RS Percentile Ranking across the full universe ────────
    all_scores = sorted(rs_raw_scores.values())
    n = len(all_scores)

    def _percentile(score: float) -> int:
        if n == 0:
            return 50
        rank = sum(s <= score for s in all_scores) / n * 99
        return max(1, min(99, round(rank)))

    result = pd.DataFrame(all_rows)
    result["rs_rank"] = result["ticker"].apply(
        lambda t: _percentile(rs_raw_scores.get(t, 0))
    )

    # ── Earnings Calendar Guard ───────────────────────────────
    if check_earnings:
        print("  Checking earnings calendars…")
        result["near_earnings"] = result["ticker"].apply(
            lambda t: _earnings_guard(t, days=7)
        )

    # ── Fundamental enrichment (setups only, not full universe) ──
    print("  Fetching fundamentals for setup tickers…")
    try:
        from fundamentals import get_fundamentals
        setup_tickers = result["ticker"].unique().tolist()
        for tkr in setup_tickers:
            fund = get_fundamentals(tkr)
            mask = result["ticker"] == tkr
            for field in ("eps_qoq", "eps_yoy", "revenue_qoq", "revenue_yoy",
                          "has_announcement", "strong_catalyst"):
                result.loc[mask, field] = fund.get(field, False if "has" in field or "strong" in field else 0.0)
    except Exception as fe:
        print(f"  Fundamentals enrichment failed (non-fatal): {fe}")

    # Sort by RS rank descending (best outperformers first)
    result = result.sort_values("rs_rank", ascending=False).reset_index(drop=True)
    return result


def print_screener_results(df: pd.DataFrame) -> None:
    """Pretty-print screener results to the console."""
    if df.empty:
        print("\n  No setups found today.")
        return

    print(f"\n{'='*80}")
    print(f"  QULLAMAGGIE SCREENER — {pd.Timestamp.today().strftime('%Y-%m-%d %H:%M')}")
    print(f"  {len(df)} setup(s) found")
    print(f"{'='*80}")

    for _, row in df.iterrows():
        risk_shares = row["entry_price"] - row["stop_price"]
        position_risk = cfg.ACCOUNT_SIZE * cfg.RISK_PER_TRADE
        shares = int(position_risk / risk_shares) if risk_shares > 0 else 0
        position_value = shares * row["entry_price"]
        earnings_flag = " ⚠️ EARNINGS SOON" if row.get("near_earnings") else ""

        print(f"\n  [{row['pattern']}] {row['ticker']}  —  {row['date']}  RS:{row.get('rs_rank',0)}{earnings_flag}")
        print(f"  Entry:      ₹{row['entry_price']:.2f}   Stop: ₹{row['stop_price']:.2f}   Risk: {row['risk_pct']:.1f}%")
        print(f"  Volume:     {row['volume_ratio']:.1f}x avg", end="")
        if row['gap_pct']:
            print(f"   Gap: +{row['gap_pct']:.1f}%", end="")
        if row['base_weeks'] != "-":
            print(f"   Base: {row['base_weeks']}w", end="")
        print(f"   Dist from 52wH: {row['distance_52w_pct']:.1f}%")
        print(f"  Sizing:     {shares} shares = ₹{position_value:,.0f} position  (1% risk = ₹{position_risk:,.0f})")

    print(f"\n{'='*80}\n")

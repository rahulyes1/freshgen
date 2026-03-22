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
            "patterns":          s.pattern,  # single pattern; merged by _dedup_and_merge later
            "rs_rank":           0,    # filled in by run_screener after universe ranking
            "near_earnings":     False, # filled in by run_screener
            # Fundamentals — filled in by run_screener after setup detection
            "eps_qoq":           0.0,
            "eps_yoy":           0.0,
            "revenue_qoq":       0.0,
            "revenue_yoy":       0.0,
            "has_announcement":  False,
            "strong_catalyst":   False,
            "grade":             "",     # filled by run_screener after grading
            "regime_size_pct":   1.0,    # filled by run_screener (regime-aware sizing multiplier)
        })

    return rows


def _dedup_and_merge(df: pd.DataFrame) -> pd.DataFrame:
    """
    Dedup & merge: produce one row per ticker with all detected patterns.

    Step 1: Per ticker+pattern, keep only the row with the most recent date.
    Step 2: Per ticker, merge multiple pattern rows into a single row.
      - patterns: list of all unique patterns (e.g. ["BREAKOUT", "S2HIGH"])
      - pattern:  primary pattern (the one with the best grade / highest score)
      - grade:    best grade among merged rows (A > B > C)
      - entry/stop/risk: from the primary pattern row
      - volume_ratio: max across all patterns
      - Other fields: from the primary row (same ticker = same RS, earnings, etc.)
    """
    if df.empty:
        return df

    grade_rank = {"A": 0, "B": 1, "C": 2}

    # Step 1: Per ticker+pattern, keep only the most recent date
    df = df.copy()
    df["_date_sort"] = pd.to_datetime(df["date"])
    df = df.sort_values("_date_sort", ascending=False)
    df = df.drop_duplicates(subset=["ticker", "pattern"], keep="first")
    df = df.drop(columns=["_date_sort"])

    # Step 2: Per ticker, merge all rows into one
    merged_rows = []
    for ticker, group in df.groupby("ticker", sort=False):
        group = group.sort_values("grade", key=lambda s: s.map(grade_rank))
        primary = group.iloc[0]  # Best grade row = primary
        all_patterns = group["pattern"].unique().tolist()

        row = primary.to_dict()
        row["patterns"] = ", ".join(all_patterns)   # "BREAKOUT, S2HIGH"
        row["volume_ratio"] = group["volume_ratio"].max()
        row["gap_pct"] = group["gap_pct"].max()
        # Use most recent date across all patterns
        row["date"] = group["date"].max()
        merged_rows.append(row)

    result = pd.DataFrame(merged_rows)
    return result


def _compute_momentum_leaders(rs_raw_scores, all_ticker_data, n_percentile):
    """Compute top momentum stocks from scan data."""
    leaders = []
    for ticker, data in all_ticker_data.items():
        rs_raw = rs_raw_scores.get(ticker, 0)
        rs_rank = n_percentile(rs_raw)
        close = data.get("close", 0)
        sma50 = data.get("sma50")
        sma150 = data.get("sma150")
        above_50 = close > sma50 if sma50 else False
        above_150 = close > sma150 if sma150 else False

        if rs_rank < 75 or not above_50:
            continue

        leaders.append({
            "ticker": ticker,
            "rs_rank": rs_rank,
            "close": round(close, 2),
            "sma50": round(sma50, 2) if sma50 else None,
            "sma150": round(sma150, 2) if sma150 else None,
            "above_50": above_50,
            "above_150": above_150,
            "return_1m": round(data.get("ret_1m", 0) * 100, 1),
            "return_3m": round(data.get("ret_3m", 0) * 100, 1),
            "volume_ratio": round(data.get("vol_ratio", 1), 1),
            "dist_52w_pct": round(data.get("dist_52w", 0) * 100, 1),
        })

    leaders.sort(key=lambda x: x["rs_rank"], reverse=True)
    return leaders[:50]


def run_screener(
    tickers: list[str],
    lookback_days: int = 450,
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
    all_ticker_data: dict[str, dict] = {}
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

        # Collect ticker data for momentum leaders
        all_ticker_data[ticker] = {
            "close": float(df_ind["Close"].iloc[-1]),
            "sma50": float(df_ind["SMA50"].iloc[-1]) if pd.notna(df_ind["SMA50"].iloc[-1]) else None,
            "sma150": float(df_ind["SMA150"].iloc[-1]) if pd.notna(df_ind["SMA150"].iloc[-1]) else None,
            "ret_1m": (float(df_ind["Close"].iloc[-1]) - float(df_ind["Close"].iloc[-21])) / float(df_ind["Close"].iloc[-21]) if len(df_ind) > 21 else 0,
            "ret_3m": (float(df_ind["Close"].iloc[-1]) - float(df_ind["Close"].iloc[-63])) / float(df_ind["Close"].iloc[-63]) if len(df_ind) > 63 else 0,
            "vol_ratio": float(df_ind["VolRatio"].iloc[-1]) if pd.notna(df_ind["VolRatio"].iloc[-1]) else 1.0,
            "dist_52w": (float(df_ind["High52W"].iloc[-1]) - float(df_ind["Close"].iloc[-1])) / float(df_ind["High52W"].iloc[-1]) if pd.notna(df_ind["High52W"].iloc[-1]) else 0,
        }

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

    # ── A/B/C Grading ─────────────────────────────────────────
    # Grade every setup based on quality factors. Never blocks — just ranks.
    #   A = High conviction: RS>80, volume>2x, tight base, near 52wH
    #   B = Solid: RS 50-80, volume>1.5x, decent structure
    #   C = Watchlist: weaker RS or loose structure, still valid pattern
    print("  Grading setups…")

    def _grade_row(row):
        score = 0
        rs = row.get("rs_rank", 0)
        vol = row.get("volume_ratio", 0)
        dist = row.get("distance_52w_pct", 100)
        risk = row.get("risk_pct", 10)
        pattern = row.get("pattern", "")

        # RS strength (max 30 pts)
        if rs >= 90:    score += 30
        elif rs >= 80:  score += 25
        elif rs >= 70:  score += 20
        elif rs >= 50:  score += 10

        # Volume conviction (max 20 pts)
        if vol >= 3.0:    score += 20
        elif vol >= 2.0:  score += 15
        elif vol >= 1.5:  score += 10

        # Proximity to 52-week high (max 15 pts)
        if dist <= 5:     score += 15
        elif dist <= 10:  score += 10
        elif dist <= 15:  score += 5

        # Tight risk (max 15 pts)
        if risk <= 3:     score += 15
        elif risk <= 5:   score += 10
        elif risk <= 7:   score += 5

        # Pattern bonus (max 10 pts)
        if pattern == "EP" and vol >= 2.5:    score += 10  # Strong EP
        elif pattern == "S2HIGH":              score += 9   # Stage-2 + 52wH = leadership
        elif pattern == "SA":                  score += 8   # Supply absorption = smart money
        elif pattern == "VCP":                 score += 7   # Minervini quality
        elif pattern == "BREAKOUT":            score += 5

        # Catalyst bonus (max 10 pts)
        if row.get("strong_catalyst"):   score += 10
        elif row.get("has_announcement"): score += 5

        # Earnings penalty
        if row.get("near_earnings"):     score -= 10

        # EMERGING is always C (watchlist)
        if pattern == "EMERGING":
            return "C"

        if score >= 65:   return "A"
        elif score >= 40: return "B"
        else:             return "C"

    result["grade"] = result.apply(_grade_row, axis=1)

    # ── Regime-Aware Position Sizing ──────────────────────────
    # Doesn't block setups — adjusts recommended size.
    # regime_size_pct: 1.0 = full size, 0.5 = half, 0.25 = quarter
    print("  Applying regime-aware sizing…")
    try:
        from api.database import get_market_cache, get_connection
        import asyncio

        async def _get_quadrant():
            conn = await get_connection()
            try:
                cached = await get_market_cache(conn, "quadrant")
                return cached.get("data", {}) if cached else {}
            finally:
                await conn.close()

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                quadrant = {}  # Can't await in running loop, skip
            else:
                quadrant = loop.run_until_complete(_get_quadrant())
        except RuntimeError:
            quadrant = {}

        overall = quadrant.get("overall", "SELECTIVE")
        swing_conf = quadrant.get("swing_confidence", 50)

        if overall == "INVEST" and swing_conf >= 60:
            base_mult = 1.0   # Full size — easy money market
        elif overall == "INVEST":
            base_mult = 0.75  # Good market but not perfect momentum
        elif overall == "SELECTIVE":
            base_mult = 0.50  # Selective — half size, pick only A grades
        else:  # CASH
            base_mult = 0.25  # Hard market — quarter size, only the best

        # Adjust per grade
        def _regime_size(row):
            grade = row.get("grade", "C")
            if grade == "A":
                return min(base_mult * 1.25, 1.0)  # A-grade gets a boost, capped at 1.0
            elif grade == "B":
                return base_mult
            else:  # C or EMERGING
                return base_mult * 0.5

        result["regime_size_pct"] = result.apply(_regime_size, axis=1)
        print(f"  Regime: {overall} | Swing confidence: {swing_conf} | Base size: {base_mult*100:.0f}%")

    except Exception as re:
        print(f"  Regime sizing skipped (non-fatal): {re}")
        result["regime_size_pct"] = 1.0

    # ── Dedup & Merge: One row per ticker ──────────────────────
    # 1. Per ticker+pattern, keep only the most recent signal date
    # 2. Per ticker, merge all patterns into one row with combined labels
    print("  Deduplicating & merging setups…")
    result = _dedup_and_merge(result)

    # Sort by grade (A first), then RS rank descending
    grade_order = {"A": 0, "B": 1, "C": 2}
    result["_grade_sort"] = result["grade"].map(grade_order)
    result = result.sort_values(["_grade_sort", "rs_rank"], ascending=[True, False]).reset_index(drop=True)
    result = result.drop(columns=["_grade_sort"])

    # Cache momentum leaders
    print("  Computing momentum leaders…")
    momentum = _compute_momentum_leaders(rs_raw_scores, all_ticker_data, _percentile)
    try:
        import asyncio as _aio
        from api.database import get_connection, set_market_cache
        async def _save_momentum():
            conn = await get_connection()
            try:
                await set_market_cache(conn, "momentum_leaders", {"leaders": momentum, "count": len(momentum)})
            finally:
                await conn.close()
        try:
            loop = _aio.get_event_loop()
            if loop.is_running():
                pass  # Skip in running loop
            else:
                loop.run_until_complete(_save_momentum())
        except RuntimeError:
            pass
        print(f"  Cached {len(momentum)} momentum leaders")
    except Exception as me:
        print(f"  Momentum cache failed (non-fatal): {me}")

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

        patterns_label = row.get('patterns', row['pattern'])
        print(f"\n  [{patterns_label}] {row['ticker']}  —  {row['date']}  RS:{row.get('rs_rank',0)}{earnings_flag}")
        print(f"  Entry:      ₹{row['entry_price']:.2f}   Stop: ₹{row['stop_price']:.2f}   Risk: {row['risk_pct']:.1f}%")
        print(f"  Volume:     {row['volume_ratio']:.1f}x avg", end="")
        if row['gap_pct']:
            print(f"   Gap: +{row['gap_pct']:.1f}%", end="")
        if row['base_weeks'] != "-":
            print(f"   Base: {row['base_weeks']}w", end="")
        print(f"   Dist from 52wH: {row['distance_52w_pct']:.1f}%")
        print(f"  Sizing:     {shares} shares = ₹{position_value:,.0f} position  (1% risk = ₹{position_risk:,.0f})")

    print(f"\n{'='*80}\n")

"""
APScheduler jobs — Qullamaggie-style EOD swing trading on Nifty 500.

Schedule (Mon–Fri IST):
  08:00  Kite auto-login (Playwright + TOTP)
  08:30  Token health check — reports funds, confirms data source
  09:00  Morning scan on yesterday's confirmed daily closes → entry alerts for today
  09:15  EP gap-up check — only Episodic Pivots (gap visible at open, act immediately)
  15:45  After-close PRIMARY scan — today's confirmed candles → setups for tomorrow's open
  */30   Position price refresh during market hours (9:15–15:30)

No intraday scans at 12:00 / 14:30 — strategy is EOD swing, patterns need confirmed closes.
"""
from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import time
from datetime import datetime

import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

IST = pytz.timezone("Asia/Kolkata")

# Quality thresholds for instant Telegram alerts
HQ_EP_GAP_MIN = 6.0   # EP gap > 6% → fire immediately
HQ_VOL_MIN    = 3.0   # Volume > 3× average → high conviction

# Track which position IDs have already received a partial-profit alert
# (in-memory — resets on server restart, that's fine)
_alerted_profit: set[int] = set()


# ── Shared helpers ────────────────────────────────────────────────────────────

async def _log_paper_trades(conn, setups: list, scan_date: str, note: str) -> None:
    """Auto-log new setups to paper_trades table (skip duplicates for the day)."""
    try:
        from api.database import create_paper_trade, get_paper_trades_by_date
        existing = {pt["ticker"] for pt in await get_paper_trades_by_date(conn, scan_date)}
        for s in setups:
            if s["ticker"] not in existing:
                await create_paper_trade(conn, {
                    "ticker":      s["ticker"],
                    "pattern":     s.get("pattern", ""),
                    "entry_price": s.get("entry_price", 0),
                    "stop_price":  s.get("stop_price", 0),
                    "shares":      s.get("position_size_shares", 1),
                    "entry_date":  scan_date,
                    "signal_date": scan_date,
                    "notes":       note,
                })
    except Exception as e:
        print(f"[Scheduler] Paper trade logging failed: {e}")


def _hq_telegram(setups: list, header: str) -> None:
    """Send Telegram alert for high-quality setups (EP gap > 6% or vol > 3×)."""
    hq = [
        s for s in setups
        if (s.get("pattern") == "EP" and float(s.get("gap_pct", 0)) >= HQ_EP_GAP_MIN)
        or float(s.get("volume_ratio", 0)) >= HQ_VOL_MIN
    ]
    if not hq:
        return
    from telegram_alerts import send_message
    lines = [f"{header} — *{len(hq)} HQ Setup{'s' if len(hq)>1 else ''}*\n"]
    for s in hq[:5]:
        t     = s["ticker"].replace(".NS", "")
        pat   = s.get("pattern", "")
        rs    = s.get("rs_rank", 0)
        entry = s.get("entry_price", 0)
        stop  = s.get("stop_price", 0)
        extra = (f"Gap `+{s.get('gap_pct', 0):.1f}%`"
                 if pat == "EP"
                 else f"Vol `{s.get('volume_ratio', 0):.1f}×`")
        lines.append(f"• *{t}* `{pat}` RS:{rs} ₹{entry:.2f} SL:₹{stop:.2f} — {extra}")
    send_message("\n".join(lines))


# ── Kite auth ─────────────────────────────────────────────────────────────────

async def _run_kite_login() -> None:
    """8:00 AM IST Mon-Fri — automated Kite token refresh via Playwright + TOTP."""
    try:
        from kite_auth import refresh_kite_token
        await refresh_kite_token()
    except Exception as e:
        print(f"[Scheduler] Kite login job error: {e}")


async def _run_kite_health() -> None:
    """8:30 AM IST Mon-Fri — verify token is valid, report available funds."""
    try:
        from kite_auth import check_token_health
        await check_token_health()
    except Exception as e:
        print(f"[Scheduler] Kite health check job error: {e}")


# ── Morning scan (9:00 AM) ────────────────────────────────────────────────────

async def run_daily_scan() -> None:
    """
    9:00 AM IST — scan on yesterday's confirmed daily closes.
    Gives you the entry candidates for today's open.
    Sends Telegram digest + email, auto-logs paper trades.
    """
    from nifty500_universe import get_full_universe
    from screener import run_screener
    from api.database import get_connection, init_db, save_scan_results
    from telegram_alerts import send_daily_digest
    from email_alerts import send_daily_email

    scan_date = datetime.now(IST).strftime("%Y-%m-%d")
    print(f"[Scheduler] Morning scan — {scan_date}")
    t0 = time.time()

    try:
        tickers  = get_full_universe()
        df       = run_screener(tickers, lookback_days=350, fresh_bars=5)
        setups   = df.to_dict(orient="records") if not df.empty else []
        duration = round(time.time() - t0, 1)
        print(f"[Scheduler] Morning scan: {len(setups)} setups in {duration}s")

        conn = await get_connection()
        await init_db(conn)
        await save_scan_results(conn, scan_date, setups, duration, len(tickers))
        await _log_paper_trades(conn, setups, scan_date, "Auto: morning scan")
        await conn.close()

        import config as cfg
        await send_daily_digest(setups, cfg.ACCOUNT_SIZE)

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: _hq_telegram(setups, "🔥 *Morning HQ Alert*"))

        try:
            from api.main import _market_regime
            regime = _market_regime()
        except Exception:
            regime = {"bullish": True, "note": ""}
        send_daily_email(setups, regime, scan_date, len(tickers))

        # Watchlist hits
        try:
            conn2 = await get_connection()
            from api.database import get_watchlist_tickers
            watch = await get_watchlist_tickers(conn2)
            await conn2.close()
            hits = [t for t in watch if t in {s["ticker"] for s in setups}]
            if hits:
                from telegram_alerts import send_message
                names = ", ".join(t.replace(".NS", "") for t in hits)
                send_message(f"👀 *Watchlist Hit*\n{names} in today's morning scan")
        except Exception as we:
            print(f"[Scheduler] Watchlist alert failed: {we}")

    except Exception as e:
        print(f"[Scheduler] Morning scan ERROR: {e}")
        import traceback; traceback.print_exc()


# ── EP gap-up check (9:15 AM) ────────────────────────────────────────────────

async def run_ep_gap_scan() -> None:
    """
    9:15 AM IST — EP gap-up check with precise ORH entry triggers via Kite.

    EP is the only setup actionable intraday — a stock gapping above a base
    on a catalyst is a same-day signal. After detecting EPs from the scanner,
    we fetch each stock's 5-min Opening Range High from Kite so the Telegram
    alert gives an exact entry price to watch, not just yesterday's close level.
    """
    from nifty500_universe import get_full_universe
    from screener import run_screener
    from api.database import get_connection

    now_ist = datetime.now(IST)
    if now_ist.weekday() >= 5:
        return

    scan_date = now_ist.strftime("%Y-%m-%d")
    print("[Scheduler] EP gap-up + ORH check — 9:15 AM")

    try:
        tickers  = get_full_universe()
        df       = run_screener(tickers, lookback_days=100, fresh_bars=1)
        setups   = df.to_dict(orient="records") if not df.empty else []
        ep_setups = [
            s for s in setups
            if s.get("pattern") == "EP" and float(s.get("gap_pct", 0)) >= 4.0
        ]

        if not ep_setups:
            print("[Scheduler] EP gap check: no qualifying gaps at 9:15 AM")
            return

        print(f"[Scheduler] EP gap check: {len(ep_setups)} EP(s) gapping")

        conn = await get_connection()
        await _log_paper_trades(conn, ep_setups, scan_date, "Auto: EP gap-up 9:15 AM")
        await conn.close()

        # Fetch ORH from Kite for precise entry levels
        try:
            import kite_data
            kite_available = kite_data.is_available()
        except Exception:
            kite_available = False

        from telegram_alerts import send_message
        lines = [f"⚡ *EP Gap-Up — {len(ep_setups)} stock{'s' if len(ep_setups)>1 else ''} above base at open*\n"]

        for s in ep_setups[:6]:
            t     = s["ticker"].replace(".NS", "")
            rs    = s.get("rs_rank", 0)
            gap   = s.get("gap_pct", 0)
            stop  = s.get("stop_price", 0)
            ann   = " 📢" if s.get("has_announcement") else ""
            cat   = " ⭐" if s.get("strong_catalyst") else ""
            eps   = f" EPS:{s.get('eps_yoy', 0):+.0f}%YoY" if s.get("eps_yoy") else ""

            # Try to get live ORH from Kite intraday data
            orh_line = ""
            if kite_available:
                try:
                    orh_data = kite_data.get_intraday_orh(s["ticker"], minutes=5)
                    if orh_data:
                        orh  = orh_data["orh"]
                        orl  = orh_data["orl"]
                        curr = orh_data["current_price"]
                        above = "✅ above ORH" if curr >= orh else "⏳ watch for break"
                        orh_line = f"\n  ORH:₹{orh:.2f} ORL:₹{orl:.2f} Now:₹{curr:.2f} {above}"
                except Exception:
                    pass

            lines.append(
                f"• *{t}* RS:{rs} Gap:`+{gap:.1f}%` SL:₹{stop:.2f}{ann}{cat}{eps}{orh_line}"
            )

        send_message("\n".join(lines))

    except Exception as e:
        print(f"[Scheduler] EP gap scan ERROR: {e}")
        import traceback; traceback.print_exc()


# ── After-close PRIMARY scan (3:45 PM) ───────────────────────────────────────

async def run_afterclose_scan() -> None:
    """
    3:45 PM IST — THE primary scan. Runs on today's confirmed daily candles
    (NSE closes at 3:30 PM, data available within ~10 min).
    These are your setups for TOMORROW's open — set your alerts tonight.
    Sends a dedicated Telegram digest with RS rank + stop levels.
    Auto-logs to paper trades for tracking.
    """
    from nifty500_universe import get_full_universe
    from screener import run_screener
    from api.database import get_connection, init_db, save_scan_results

    now_ist = datetime.now(IST)
    if now_ist.weekday() >= 5:
        return

    scan_date = now_ist.strftime("%Y-%m-%d")
    print(f"[Scheduler] After-close scan — {scan_date}")
    t0 = time.time()

    try:
        tickers  = get_full_universe()
        df       = run_screener(tickers, lookback_days=350, fresh_bars=1)
        setups   = df.to_dict(orient="records") if not df.empty else []
        duration = round(time.time() - t0, 1)
        print(f"[Scheduler] After-close scan: {len(setups)} setups in {duration}s")

        # Save under a distinct key so it doesn't overwrite morning scan
        conn = await get_connection()
        await init_db(conn)
        await save_scan_results(conn, f"{scan_date}_afterclose", setups, duration, len(tickers))
        await _log_paper_trades(conn, setups, scan_date, "Auto: after-close scan")
        await conn.close()

        if not setups:
            from telegram_alerts import send_message
            send_message("📋 *After-Close Scan* — No setups today. Wait for better conditions.")
            return

        # Telegram digest — top setups by RS rank for tomorrow's watchlist
        from telegram_alerts import send_message
        import config as cfg

        top = sorted(setups, key=lambda x: x.get("rs_rank", 0), reverse=True)[:8]
        bull_count = sum(1 for s in setups if s.get("pattern") == "BREAKOUT")
        ep_count   = sum(1 for s in setups if s.get("pattern") == "EP")
        vcp_count  = sum(1 for s in setups if s.get("pattern") == "VCP")

        # ── 30-position market-top heuristic ─────────────────────
        # Qullamaggie: every time he hit 30 positions, a pullback followed.
        try:
            from api.database import get_positions
            conn_pos = await get_connection()
            open_count = len(await get_positions(conn_pos, "open"))
            await conn_pos.close()
            if open_count >= 28:
                send_message(
                    f"⚠️ *Position Count Warning*\n"
                    f"You have *{open_count} open positions* — approaching Qullamaggie's "
                    f"30-position market-top indicator.\n"
                    f"_Consider tightening stops and sizing down new entries._"
                )
        except Exception:
            open_count = 0

        header = (
            f"📊 *Tonight's Setups — {scan_date}*\n"
            f"Total: *{len(setups)}* | BO:{bull_count} EP:{ep_count} VCP:{vcp_count}\n"
            f"_Set alerts for tomorrow's open_\n"
        )
        lines = [header]
        for s in top:
            t     = s["ticker"].replace(".NS", "")
            pat   = s.get("pattern", "")
            rs    = s.get("rs_rank", 0)
            entry = s.get("entry_price", 0)
            stop  = s.get("stop_price", 0)
            risk  = s.get("risk_pct", 0)
            warn  = " ⚠️ earnings" if s.get("near_earnings") else ""
            lines.append(f"• *{t}* `{pat}` RS:{rs} ₹{entry:.2f} SL:₹{stop:.2f} R:{risk:.1f}%{warn}")
        send_message("\n".join(lines))

        # Watchlist hits in after-close scan
        try:
            conn2 = await get_connection()
            from api.database import get_watchlist_tickers
            watch = await get_watchlist_tickers(conn2)
            await conn2.close()
            hits = [t for t in watch if t in {s["ticker"] for s in setups}]
            if hits:
                names = ", ".join(t.replace(".NS", "") for t in hits)
                send_message(f"👀 *Watchlist Hit (after-close)*\n{names} — set your alerts!")
        except Exception as we:
            print(f"[Scheduler] Watchlist alert failed: {we}")

    except Exception as e:
        print(f"[Scheduler] After-close scan ERROR: {e}")
        import traceback; traceback.print_exc()


# ── Position price refresh (every 30 min during market hours) ────────────────

async def refresh_open_positions() -> None:
    """
    Every 30 min during market hours — refresh prices, fire stop-breach alerts,
    and send partial-profit alerts (once per position) when up 15%+.
    Uses Kite live quotes if available, falls back to yfinance.
    """
    now_ist = datetime.now(IST)
    if not (9 * 60 + 15 <= now_ist.hour * 60 + now_ist.minute <= 15 * 60 + 30):
        return

    try:
        from api.database import get_connection, get_positions, update_position_price

        conn = await get_connection()
        open_positions = await get_positions(conn, "open")

        if not open_positions:
            await conn.close()
            return

        tickers = list({p["ticker"] for p in open_positions})
        loop    = asyncio.get_event_loop()

        # Try Kite live quotes first, fall back to yfinance
        prices: dict = {}
        try:
            import kite_data
            if kite_data.is_available():
                prices = kite_data.get_live_quotes(tickers)
        except Exception:
            pass

        if not prices:
            import yfinance as yf
            def _fetch():
                data = yf.download(tickers, period="1d", auto_adjust=True, progress=False)
                if data.empty:
                    return {}
                close = data["Close"]
                if hasattr(close, "columns"):
                    return {str(c): float(close[c].dropna().iloc[-1])
                            for c in close.columns if not close[c].dropna().empty}
                return {tickers[0]: float(close.dropna().iloc[-1])}
            prices = await loop.run_in_executor(None, _fetch)

        stop_alerts   = []
        profit_alerts = []

        for pos in open_positions:
            price = prices.get(pos["ticker"])
            if not price:
                continue

            await update_position_price(conn, pos["id"], price)

            # ── Hard stop breach (intraday) ───────────────────────
            if price <= pos["stop_price"]:
                stop_alerts.append((pos, price))

            # ── Partial profit alert — fire once when up 15%+ ─────
            entry = pos.get("entry_price", 0)
            pos_id = pos["id"]
            if entry and price >= entry * 1.15 and pos_id not in _alerted_profit:
                _alerted_profit.add(pos_id)
                gain_pct = (price / entry - 1) * 100
                profit_alerts.append((pos, price, gain_pct))

        await conn.close()

        from telegram_alerts import send_message

        for pos, price in stop_alerts:
            t = pos["ticker"].replace(".NS", "")
            send_message(
                f"🚨 *Stop Breach (intraday)*\n"
                f"*{t}* at ₹{price:.2f} (stop: ₹{pos['stop_price']:.2f})\n"
                f"_Wait for EOD close before exiting — check MA trailing stop at 3:40 PM_"
            )

        for pos, price, gain_pct in profit_alerts:
            t = pos["ticker"].replace(".NS", "")
            r = gain_pct / (pos.get("risk_pct", 1) or 1) if pos.get("risk_pct") else "—"
            send_message(
                f"💰 *Partial Profit Alert*\n"
                f"*{t}* up *{gain_pct:.1f}%* from entry ₹{pos['entry_price']:.2f}\n"
                f"Consider trimming *20–25%* into this strength\n"
                f"_Let the rest run with trailing MA stop_"
            )

    except Exception as e:
        print(f"[Scheduler] Price refresh error: {e}")


async def check_ma_trailing_stops() -> None:
    """
    3:40 PM IST — After NSE closes (3:30 PM). Check all open positions and
    paper trades against their 10-day and 20-day MAs on CONFIRMED closes.

    Qullamaggie: trail with 10MA (fast stocks) or 20MA (slow stocks).
    Wait for EOD close — intraday dips below MA are noise, not signals.
    """
    now_ist = datetime.now(IST)
    if now_ist.weekday() >= 5:
        return

    print("[Scheduler] EOD trailing stop check — 3:40 PM")

    try:
        from api.database import get_connection, get_positions, get_paper_trades

        conn = await get_connection()
        open_positions = await get_positions(conn, "open")
        open_papers    = [p for p in await get_paper_trades(conn) if p.get("status") == "open"]
        await conn.close()

        all_open = open_positions + open_papers
        if not all_open:
            return

        tickers = list({p["ticker"] for p in all_open})
        loop    = asyncio.get_event_loop()

        # Fetch 25 days to compute 10MA and 20MA
        def _fetch_ma():
            try:
                import yfinance as yf
                data = yf.download(tickers, period="25d", auto_adjust=True, progress=False)
                if data.empty:
                    return {}
                close = data["Close"]
                result: dict = {}
                for tkr in tickers:
                    try:
                        s = close[tkr].dropna() if hasattr(close, "columns") else close.dropna()
                        if len(s) >= 20:
                            result[tkr] = {
                                "close": float(s.iloc[-1]),
                                "ma10":  float(s.rolling(10).mean().iloc[-1]),
                                "ma20":  float(s.rolling(20).mean().iloc[-1]),
                            }
                    except Exception:
                        continue
                return result
            except Exception:
                return {}

        # Try Kite live quotes for today's confirmed close (more accurate)
        ma_data = await loop.run_in_executor(None, _fetch_ma)

        from telegram_alerts import send_message
        alerts = []

        for pos in all_open:
            tkr  = pos["ticker"]
            data = ma_data.get(tkr)
            if not data:
                continue

            close = data["close"]
            ma10  = data["ma10"]
            ma20  = data["ma20"]
            t     = tkr.replace(".NS", "")
            entry = pos.get("entry_price", 0)
            gain  = f" ({(close/entry-1)*100:+.1f}%)" if entry else ""

            if close < ma10:
                alerts.append(
                    f"🔴 *{t}*{gain} closed ₹{close:.2f} — BELOW 10MA ₹{ma10:.2f}"
                    f"\n  _Fast-stock trail stop triggered. Consider exiting._"
                )
            elif close < ma20:
                alerts.append(
                    f"🟡 *{t}*{gain} closed ₹{close:.2f} — below 20MA ₹{ma20:.2f}"
                    f"\n  _Slow-stock trail stop. Watch tomorrow's close._"
                )

        if alerts:
            header = f"📉 *EOD Trailing Stop Check — {now_ist.strftime('%Y-%m-%d')}*\n"
            send_message(header + "\n".join(alerts))
        else:
            print("[Scheduler] Trailing stop check: all positions above MAs")

    except Exception as e:
        print(f"[Scheduler] Trailing stop check error: {e}")


# ── Scheduler factory ─────────────────────────────────────────────────────────

def create_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=IST)

    # 8:00 AM — Kite auto-login
    scheduler.add_job(
        _run_kite_login,
        CronTrigger(day_of_week="mon-fri", hour=8, minute=0, timezone=IST),
        id="kite_login", name="Kite Auto Login 8:00 AM",
        replace_existing=True, misfire_grace_time=300,
    )

    # 8:30 AM — Token health check
    scheduler.add_job(
        _run_kite_health,
        CronTrigger(day_of_week="mon-fri", hour=8, minute=30, timezone=IST),
        id="kite_health", name="Kite Health Check 8:30 AM",
        replace_existing=True, misfire_grace_time=300,
    )

    # 9:00 AM — Morning scan (yesterday's confirmed closes → today's entries)
    scheduler.add_job(
        run_daily_scan,
        CronTrigger(day_of_week="mon-fri", hour=9, minute=0, timezone=IST),
        id="daily_scan", name="Morning Scan 9:00 AM",
        replace_existing=True, misfire_grace_time=300,
    )

    # 9:15 AM — EP gap-up check (only actionable intraday signal)
    scheduler.add_job(
        run_ep_gap_scan,
        CronTrigger(day_of_week="mon-fri", hour=9, minute=15, timezone=IST),
        id="ep_gap_scan", name="EP Gap-Up Check 9:15 AM",
        replace_existing=True, misfire_grace_time=120,
    )

    # 3:40 PM — EOD trailing MA stop check (before after-close scan)
    scheduler.add_job(
        check_ma_trailing_stops,
        CronTrigger(day_of_week="mon-fri", hour=15, minute=40, timezone=IST),
        id="ma_trailing_stop", name="EOD Trailing Stop Check 3:40 PM",
        replace_existing=True, misfire_grace_time=120,
    )

    # 3:45 PM — After-close PRIMARY scan (today's confirmed candles → tomorrow's setups)
    scheduler.add_job(
        run_afterclose_scan,
        CronTrigger(day_of_week="mon-fri", hour=15, minute=45, timezone=IST),
        id="afterclose_scan", name="After-Close Scan 3:45 PM",
        replace_existing=True, misfire_grace_time=300,
    )

    # Every 30 min Mon-Fri — position price refresh + stop alerts
    scheduler.add_job(
        refresh_open_positions,
        CronTrigger(day_of_week="mon-fri", minute="*/30", timezone=IST),
        id="price_refresh", name="Position Price Refresh (30 min)",
        replace_existing=True,
    )

    return scheduler

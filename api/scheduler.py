"""
APScheduler jobs — Qullamaggie-style EOD swing trading on Nifty 500.

Schedule (Mon–Fri IST):
  08:00  Kite auto-login (Playwright + TOTP)
  08:30  Token health check — reports funds, confirms data source
  09:00  Morning scan on yesterday's confirmed daily closes → entry alerts for today
  09:15  EP gap-up check — only Episodic Pivots (gap visible at open, act immediately)
  15:45  After-close PRIMARY scan — today's confirmed candles → setups for tomorrow's open
         + saves sectors + quadrant to DB
  */30   Position price refresh during market hours (9:15–15:30)
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

HQ_EP_GAP_MIN = 6.0
HQ_VOL_MIN = 3.0

_alerted_profit: set[int] = set()


# ── Shared helpers ────────────────────────────────────────────

async def _log_paper_trades(conn, setups: list, scan_date: str, note: str) -> None:
    try:
        from api.database import create_paper_trade, get_paper_trades_by_date
        existing = {pt["ticker"] for pt in await get_paper_trades_by_date(conn, scan_date)}
        for s in setups:
            if s["ticker"] not in existing:
                await create_paper_trade(conn, {
                    "ticker": s["ticker"], "pattern": s.get("pattern", ""),
                    "entry_price": s.get("entry_price", 0), "stop_price": s.get("stop_price", 0),
                    "shares": s.get("position_size_shares", 1), "entry_date": scan_date,
                    "signal_date": scan_date, "notes": note,
                })
    except Exception as e:
        print(f"[Scheduler] Paper trade logging failed: {e}")


def _hq_telegram(setups: list, header: str) -> None:
    hq = [
        s for s in setups
        if (s.get("pattern") == "EP" and float(s.get("gap_pct", 0)) >= HQ_EP_GAP_MIN)
        or float(s.get("volume_ratio", 0)) >= HQ_VOL_MIN
    ]
    if not hq:
        return
    from telegram_alerts import send_message
    lines = [f"{header} — *{len(hq)} HQ Setup{'s' if len(hq) > 1 else ''}*\n"]
    for s in hq[:5]:
        t = s["ticker"].replace(".NS", "")
        pat = s.get("pattern", "")
        rs = s.get("rs_rank", 0)
        entry = s.get("entry_price", 0)
        stop = s.get("stop_price", 0)
        extra = (f"Gap `+{s.get('gap_pct', 0):.1f}%`" if pat == "EP"
                 else f"Vol `{s.get('volume_ratio', 0):.1f}×`")
        lines.append(f"• *{t}* `{pat}` RS:{rs} ₹{entry:.2f} SL:₹{stop:.2f} — {extra}")
    send_message("\n".join(lines))


# ── Kite auth ─────────────────────────────────────────────────

async def _run_kite_login() -> None:
    try:
        from kite_auth import refresh_kite_token
        await refresh_kite_token()
    except Exception as e:
        print(f"[Scheduler] Kite login job error: {e}")


async def _run_kite_health() -> None:
    try:
        from kite_auth import check_token_health
        await check_token_health()
    except Exception as e:
        print(f"[Scheduler] Kite health check job error: {e}")


# ── Morning scan (9:00 AM) ────────────────────────────────────

async def run_daily_scan() -> None:
    from nifty500_universe import get_full_universe
    from screener import run_screener
    from api.database import db, save_scan_results
    from telegram_alerts import send_daily_digest
    from email_alerts import send_daily_email

    scan_date = datetime.now(IST).strftime("%Y-%m-%d")
    print(f"[Scheduler] Morning scan — {scan_date}")
    t0 = time.time()

    try:
        tickers = get_full_universe()
        df = run_screener(tickers, lookback_days=350, fresh_bars=5)
        setups = df.to_dict(orient="records") if not df.empty else []
        duration = round(time.time() - t0, 1)
        print(f"[Scheduler] Morning scan: {len(setups)} setups from {len(tickers)} tickers in {duration}s")

        async with db() as conn:
            await save_scan_results(conn, scan_date, setups, duration, len(tickers))
            await _log_paper_trades(conn, setups, scan_date, "Auto: morning scan")

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
            async with db() as conn:
                from api.database import get_watchlist_tickers
                watch = await get_watchlist_tickers(conn)
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


# ── EP gap-up check (9:15 AM) ────────────────────────────────

async def run_ep_gap_scan() -> None:
    from nifty500_universe import get_full_universe
    from screener import run_screener
    from api.database import db

    now_ist = datetime.now(IST)
    if now_ist.weekday() >= 5:
        return

    scan_date = now_ist.strftime("%Y-%m-%d")
    print("[Scheduler] EP gap-up + ORH check — 9:15 AM")

    try:
        tickers = get_full_universe()
        df = run_screener(tickers, lookback_days=100, fresh_bars=1)
        setups = df.to_dict(orient="records") if not df.empty else []
        ep_setups = [
            s for s in setups
            if s.get("pattern") == "EP" and float(s.get("gap_pct", 0)) >= 4.0
        ]

        if not ep_setups:
            print("[Scheduler] EP gap check: no qualifying gaps at 9:15 AM")
            return

        print(f"[Scheduler] EP gap check: {len(ep_setups)} EP(s) gapping")

        async with db() as conn:
            await _log_paper_trades(conn, ep_setups, scan_date, "Auto: EP gap-up 9:15 AM")

        # Fetch ORH from Kite for precise entry levels
        try:
            import kite_data
            kite_available = kite_data.is_available()
        except Exception:
            kite_available = False

        from telegram_alerts import send_message
        lines = [f"⚡ *EP Gap-Up — {len(ep_setups)} stock{'s' if len(ep_setups) > 1 else ''} above base at open*\n"]

        for s in ep_setups[:6]:
            t = s["ticker"].replace(".NS", "")
            rs = s.get("rs_rank", 0)
            gap = s.get("gap_pct", 0)
            stop = s.get("stop_price", 0)
            ann = " 📢" if s.get("has_announcement") else ""
            cat = " ⭐" if s.get("strong_catalyst") else ""
            eps = f" EPS:{s.get('eps_yoy', 0):+.0f}%YoY" if s.get("eps_yoy") else ""

            orh_line = ""
            if kite_available:
                try:
                    orh_data = kite_data.get_intraday_orh(s["ticker"], minutes=5)
                    if orh_data:
                        orh = orh_data["orh"]
                        orl = orh_data["orl"]
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


# ── After-close PRIMARY scan (3:45 PM) ───────────────────────

async def run_afterclose_scan() -> None:
    """
    3:45 PM IST — THE primary scan + saves sectors & quadrant to DB.
    Everything persists so dashboard loads instantly next morning.
    """
    from nifty500_universe import get_full_universe
    from screener import run_screener
    from api.database import db, save_scan_results, set_market_cache

    now_ist = datetime.now(IST)
    if now_ist.weekday() >= 5:
        return

    scan_date = now_ist.strftime("%Y-%m-%d")
    print(f"[Scheduler] After-close scan — {scan_date}")
    t0 = time.time()

    try:
        tickers = get_full_universe()
        df = run_screener(tickers, lookback_days=350, fresh_bars=1)
        setups = df.to_dict(orient="records") if not df.empty else []
        duration = round(time.time() - t0, 1)
        print(f"[Scheduler] After-close scan: {len(setups)} setups from {len(tickers)} tickers in {duration}s")

        async with db() as conn:
            await save_scan_results(conn, f"{scan_date}_afterclose", setups, duration, len(tickers))
            await _log_paper_trades(conn, setups, scan_date, "Auto: after-close scan")

        # ── Save sectors + quadrant to DB (persist for dashboard) ──
        try:
            from api.main import compute_sector_performance, compute_market_quadrant
            print("[Scheduler] Computing sector performance for DB cache...")
            sector_data = compute_sector_performance()
            if sector_data:
                async with db() as conn:
                    await set_market_cache(conn, "sectors", sector_data)
                print(f"[Scheduler] Sectors cached: {len(sector_data)} sectors")

            print("[Scheduler] Computing market quadrant for DB cache...")
            quadrant_data = compute_market_quadrant()
            if quadrant_data:
                async with db() as conn:
                    await set_market_cache(conn, "quadrant", quadrant_data)
                print("[Scheduler] Quadrant cached to DB")
        except Exception as ce:
            print(f"[Scheduler] Cache save error: {ce}")

        if not setups:
            from telegram_alerts import send_message
            send_message("📋 *After-Close Scan* — No setups today. Wait for better conditions.")
            return

        from telegram_alerts import send_message
        import config as cfg

        top = sorted(setups, key=lambda x: x.get("rs_rank", 0), reverse=True)[:8]
        bull_count = sum(1 for s in setups if s.get("pattern") == "BREAKOUT")
        ep_count = sum(1 for s in setups if s.get("pattern") == "EP")
        vcp_count = sum(1 for s in setups if s.get("pattern") == "VCP")

        # 30-position market-top heuristic
        try:
            from api.database import get_positions
            async with db() as conn:
                open_count = len(await get_positions(conn, "open"))
            if open_count >= 28:
                send_message(
                    f"⚠️ *Position Count Warning*\n"
                    f"You have *{open_count} open positions* — approaching Qullamaggie's "
                    f"30-position market-top indicator.\n"
                    f"_Consider tightening stops and sizing down new entries._"
                )
        except Exception:
            pass

        header = (
            f"📊 *Tonight's Setups — {scan_date}*\n"
            f"Total: *{len(setups)}* | BO:{bull_count} EP:{ep_count} VCP:{vcp_count}\n"
            f"_Set alerts for tomorrow's open_\n"
        )
        lines = [header]
        for s in top:
            t = s["ticker"].replace(".NS", "")
            pat = s.get("pattern", "")
            rs = s.get("rs_rank", 0)
            entry = s.get("entry_price", 0)
            stop = s.get("stop_price", 0)
            risk = s.get("risk_pct", 0)
            warn = " ⚠️ earnings" if s.get("near_earnings") else ""
            lines.append(f"• *{t}* `{pat}` RS:{rs} ₹{entry:.2f} SL:₹{stop:.2f} R:{risk:.1f}%{warn}")
        send_message("\n".join(lines))

        # Watchlist hits
        try:
            from api.database import get_watchlist_tickers
            async with db() as conn:
                watch = await get_watchlist_tickers(conn)
            hits = [t for t in watch if t in {s["ticker"] for s in setups}]
            if hits:
                names = ", ".join(t.replace(".NS", "") for t in hits)
                send_message(f"👀 *Watchlist Hit (after-close)*\n{names} — set your alerts!")
        except Exception as we:
            print(f"[Scheduler] Watchlist alert failed: {we}")

    except Exception as e:
        print(f"[Scheduler] After-close scan ERROR: {e}")
        import traceback; traceback.print_exc()


# ── Position price refresh ────────────────────────────────────

async def refresh_open_positions() -> None:
    now_ist = datetime.now(IST)
    if not (9 * 60 + 15 <= now_ist.hour * 60 + now_ist.minute <= 15 * 60 + 30):
        return

    try:
        from api.database import db, get_positions, update_position_price, fetch_live_prices

        async with db() as conn:
            open_positions = await get_positions(conn, "open")
            if not open_positions:
                return

            tickers = list({p["ticker"] for p in open_positions})
            prices = await fetch_live_prices(tickers)

            stop_alerts = []
            profit_alerts = []

            for pos in open_positions:
                price = prices.get(pos["ticker"])
                if not price:
                    continue

                await update_position_price(conn, pos["id"], price)

                if price <= pos["stop_price"]:
                    stop_alerts.append((pos, price))

                entry = pos.get("entry_price", 0)
                pos_id = pos["id"]
                if entry and price >= entry * 1.15 and pos_id not in _alerted_profit:
                    _alerted_profit.add(pos_id)
                    gain_pct = (price / entry - 1) * 100
                    profit_alerts.append((pos, price, gain_pct))

        from telegram_alerts import send_message

        for pos, price in stop_alerts:
            t = pos["ticker"].replace(".NS", "")
            send_message(
                f"🚨 *Stop Breach (intraday)*\n*{t}* at ₹{price:.2f} (stop: ₹{pos['stop_price']:.2f})\n"
                f"_Wait for EOD close before exiting — check MA trailing stop at 3:40 PM_"
            )

        for pos, price, gain_pct in profit_alerts:
            t = pos["ticker"].replace(".NS", "")
            send_message(
                f"💰 *Partial Profit Alert*\n*{t}* up *{gain_pct:.1f}%* from entry ₹{pos['entry_price']:.2f}\n"
                f"Consider trimming *20–25%* into this strength\n_Let the rest run with trailing MA stop_"
            )

    except Exception as e:
        print(f"[Scheduler] Price refresh error: {e}")


# ── EOD trailing MA stop check (3:40 PM) ─────────────────────

async def check_ma_trailing_stops() -> None:
    now_ist = datetime.now(IST)
    if now_ist.weekday() >= 5:
        return

    print("[Scheduler] EOD trailing stop check — 3:40 PM")

    try:
        from api.database import db, get_positions, get_paper_trades

        async with db() as conn:
            open_positions = await get_positions(conn, "open")
            open_papers = [p for p in await get_paper_trades(conn) if p.get("status") == "open"]

        all_open = open_positions + open_papers
        if not all_open:
            return

        tickers = list({p["ticker"] for p in all_open})
        loop = asyncio.get_event_loop()

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
                                "ma10": float(s.rolling(10).mean().iloc[-1]),
                                "ma20": float(s.rolling(20).mean().iloc[-1]),
                            }
                    except Exception:
                        continue
                return result
            except Exception:
                return {}

        ma_data = await loop.run_in_executor(None, _fetch_ma)

        from telegram_alerts import send_message
        alerts = []

        for pos in all_open:
            tkr = pos["ticker"]
            data = ma_data.get(tkr)
            if not data:
                continue

            close = data["close"]
            ma10 = data["ma10"]
            ma20 = data["ma20"]
            t = tkr.replace(".NS", "")
            entry = pos.get("entry_price", 0)
            gain = f" ({(close / entry - 1) * 100:+.1f}%)" if entry else ""

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


# ── Scheduler factory ─────────────────────────────────────────

def create_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=IST)

    scheduler.add_job(
        _run_kite_login,
        CronTrigger(day_of_week="mon-fri", hour=8, minute=0, timezone=IST),
        id="kite_login", name="Kite Auto Login 8:00 AM",
        replace_existing=True, misfire_grace_time=300,
    )

    scheduler.add_job(
        _run_kite_health,
        CronTrigger(day_of_week="mon-fri", hour=8, minute=30, timezone=IST),
        id="kite_health", name="Kite Health Check 8:30 AM",
        replace_existing=True, misfire_grace_time=300,
    )

    scheduler.add_job(
        run_daily_scan,
        CronTrigger(day_of_week="mon-fri", hour=9, minute=0, timezone=IST),
        id="daily_scan", name="Morning Scan 9:00 AM",
        replace_existing=True, misfire_grace_time=300,
    )

    scheduler.add_job(
        run_ep_gap_scan,
        CronTrigger(day_of_week="mon-fri", hour=9, minute=15, timezone=IST),
        id="ep_gap_scan", name="EP Gap-Up Check 9:15 AM",
        replace_existing=True, misfire_grace_time=120,
    )

    scheduler.add_job(
        check_ma_trailing_stops,
        CronTrigger(day_of_week="mon-fri", hour=15, minute=40, timezone=IST),
        id="ma_trailing_stop", name="EOD Trailing Stop Check 3:40 PM",
        replace_existing=True, misfire_grace_time=120,
    )

    scheduler.add_job(
        run_afterclose_scan,
        CronTrigger(day_of_week="mon-fri", hour=15, minute=45, timezone=IST),
        id="afterclose_scan", name="After-Close Scan 3:45 PM",
        replace_existing=True, misfire_grace_time=300,
    )

    scheduler.add_job(
        refresh_open_positions,
        CronTrigger(day_of_week="mon-fri", minute="*/30", timezone=IST),
        id="price_refresh", name="Position Price Refresh (30 min)",
        replace_existing=True,
    )

    return scheduler

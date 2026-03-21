"""
FastAPI backend for the Qullamaggie Nifty 500 Trading Scanner.

Start from the repo root:
    uvicorn api.main:app --reload --port 8000

Routes:
    GET  /health
    GET  /scan
    GET  /positions
    POST /positions
    PUT  /positions/{id}
    DEL  /positions/{id}
    POST /backtest
    GET  /scan/history
"""
from __future__ import annotations

import sys, os
# Must insert parent dir FIRST so all existing modules are importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
import math
import asyncio
import pandas as pd
from datetime import datetime
from contextlib import asynccontextmanager
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

# Project imports (after sys.path setup)
import config as cfg
from api.models import (
    SetupSchema, ScanResponse,
    PositionCreate, PositionUpdate, PositionSchema,
    BacktestRequest, BacktestResponse, BacktestStats,
    EquityPoint, TradeRecord, HealthResponse,
    JournalCreate, JournalUpdate, JournalSchema,
    WatchlistCreate, WatchlistSchema,
    PaperTradeCreate, PaperTradeUpdate, PaperTradeSchema,
)
from api.database import (
    get_connection, init_db,
    get_positions, get_position, create_position, update_position, delete_position,
    save_scan_results, get_scan_history, get_cached_scan, get_most_recent_cached_scan, update_position_price,
    get_journal, get_journal_entry, create_journal_entry, update_journal_entry, delete_journal_entry,
    get_watchlist, add_to_watchlist, remove_from_watchlist, get_watchlist_tickers,
    get_paper_trades, get_paper_trade, create_paper_trade, update_paper_trade,
    delete_paper_trade, update_paper_trade_price,
)
from api.scheduler import create_scheduler


# ── App Lifecycle ─────────────────────────────────────────────

executor = ThreadPoolExecutor(max_workers=2)
_scheduler = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _scheduler

    # Init DB
    conn = await get_connection()
    await init_db(conn)
    await conn.close()

    # Start scheduler
    _scheduler = create_scheduler()
    _scheduler.start()
    print("[API] Scheduler started — daily scan at 9:00 AM IST (Mon-Fri)")

    yield

    _scheduler.shutdown(wait=False)
    executor.shutdown(wait=False)


app = FastAPI(
    title="Qullamaggie Nifty 500 Scanner",
    description="Live breakout + episodic pivot scanner for NSE India",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Helpers ───────────────────────────────────────────────────

_regime_cache: dict = {}
_regime_cache_ts: float = 0.0
_REGIME_TTL = 300  # 5 minutes

def _market_regime() -> dict:
    """
    Check if Nifty 50 is in a bull regime (above 200-day SMA).
    Uses ^NSEI (Nifty 50 index) — most reliable yfinance ticker for NSE regime.
    Cached 5 minutes to avoid flapping on each health check.
    """
    global _regime_cache, _regime_cache_ts
    if _regime_cache and (time.time() - _regime_cache_ts) < _REGIME_TTL:
        return _regime_cache

    try:
        import yfinance as yf
        df = yf.download("^NSEI", period="300d", auto_adjust=True, progress=False)
        if df.empty or len(df) < 50:
            return {"bullish": True, "index_price": None, "sma200": None, "note": "No data"}
        close = df["Close"].squeeze()
        price  = float(close.iloc[-1])
        sma200 = float(close.rolling(200).mean().iloc[-1]) if len(close) >= 200 else float(close.rolling(50).mean().iloc[-1])
        bullish = price > sma200
        result = {
            "bullish": bullish,
            "index_price": round(price, 1),
            "sma200": round(sma200, 1),
            "note": "Above 200-SMA — Bull market" if bullish else "Below 200-SMA — Bear market, trade small",
        }
        _regime_cache = result
        _regime_cache_ts = time.time()
        return result
    except Exception as e:
        return {"bullish": True, "index_price": None, "sma200": None, "note": f"Regime check failed: {e}"}


def _compute_sizing(setup_row: dict, account_size: float) -> dict:
    """
    Attach position sizing fields to a setup dict.
    ATR floor: if stop is tighter than 2×ATR14, use 2×ATR as minimum risk distance
    to prevent over-sizing from artificially tight stops.
    """
    entry  = float(setup_row.get("entry_price", 0))
    stop   = float(setup_row.get("stop_price", 0))
    atr14  = float(setup_row.get("atr14", 0) or 0)

    risk_per_share = entry - stop
    if risk_per_share <= 0:
        return {"position_size_shares": 0, "position_value": 0.0, "risk_amount": 0.0}

    # ATR floor: use 2×ATR as minimum risk distance
    if atr14 > 0:
        risk_per_share = max(risk_per_share, 2.0 * atr14)

    risk_dollars = account_size * cfg.RISK_PER_TRADE
    shares = math.floor(risk_dollars / risk_per_share)
    max_shares = math.floor((account_size * cfg.MAX_POSITION_PCT) / entry) if entry > 0 else 0
    shares = min(shares, max_shares)
    return {
        "position_size_shares": shares,
        "position_value": round(shares * entry, 2),
        "risk_amount": round(risk_dollars, 2),
    }


def _enrich_position(pos: dict) -> dict:
    """Add unrealized_pnl fields to a position dict."""
    current = pos.get("current_price")
    if current and pos.get("status") == "open":
        entry  = pos["entry_price"]
        shares = pos["shares"]
        pnl    = (float(current) - entry) * shares
        pnl_pct = (float(current) - entry) / entry
        pos["unrealized_pnl"]     = round(pnl, 2)
        pos["unrealized_pnl_pct"] = round(pnl_pct * 100, 3)
    else:
        pos["unrealized_pnl"]     = None
        pos["unrealized_pnl_pct"] = None

    risk = (pos["entry_price"] - pos["stop_price"]) * pos["shares"]
    pos["risk_amount"] = round(max(risk, 0), 2)
    return pos


# ── Routes ────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse)
async def health():
    db_ok = True
    try:
        conn = await get_connection()
        await conn.execute("SELECT 1")
        await conn.close()
    except Exception:
        db_ok = False

    loop = asyncio.get_event_loop()
    regime = await loop.run_in_executor(executor, _market_regime)

    # Kite status (non-blocking)
    kite_info = {"connected": False, "user": ""}
    try:
        from kite_data import status as kite_status
        kite_info = kite_status()
    except ImportError:
        pass

    return HealthResponse(
        status="ok",
        timestamp=datetime.now().isoformat(),
        scheduler_running=_scheduler is not None and _scheduler.running,
        db_ok=db_ok,
        market_bullish=regime.get("bullish", True),
        regime_note=regime.get("note", ""),
        nifty500_price=regime.get("index_price"),
        nifty500_sma200=regime.get("sma200"),
        kite_connected=kite_info.get("connected", False),
        kite_user=kite_info.get("user", ""),
        data_source="kite" if kite_info.get("connected") else "yfinance",
    )


def _build_setups_from_rows(rows: list[dict]) -> list[SetupSchema]:
    setups = []
    for row in rows:
        row.update(_compute_sizing(row, cfg.ACCOUNT_SIZE))
        row.setdefault("gap_pct", 0.0)
        row.setdefault("base_weeks", "-")
        row.setdefault("distance_52w_pct", 0.0)
        row.setdefault("atr14", 0.0)
        row.setdefault("rs_rank", 0)
        row.setdefault("near_earnings", False)
        try:
            setups.append(SetupSchema(**{k: row[k] for k in SetupSchema.model_fields if k in row}))
        except Exception:
            pass
    return setups


def _run_scan_background(universe: str, fresh_bars: int) -> None:
    """Blocking scan that saves results to DB — runs in thread executor."""
    from screener import run_screener
    from nifty500_universe import get_full_universe, get_momentum_universe
    import asyncio as _aio

    today = datetime.now().strftime("%Y-%m-%d")
    if universe == "nifty50":
        from nifty500_universe import NIFTY_50
        tickers = NIFTY_50
    elif universe == "momentum":
        tickers = get_momentum_universe()
    else:
        tickers = get_full_universe()

    print(f"[BG Scan] Starting {universe} scan for {today}…")
    t0 = time.time()
    try:
        df = run_screener(tickers, lookback_days=350, fresh_bars=fresh_bars)
        setups_raw = df.to_dict(orient="records") if not df.empty else []
        duration = round(time.time() - t0, 1)

        loop = _aio.new_event_loop()
        async def _save():
            conn = await get_connection()
            await save_scan_results(conn, today, setups_raw, duration, len(tickers))
            await conn.close()
        loop.run_until_complete(_save())
        loop.close()
        print(f"[BG Scan] Done — {len(setups_raw)} setups in {duration}s")
    except Exception as e:
        print(f"[BG Scan] Error: {e}")


@app.get("/scan", response_model=ScanResponse)
async def scan(
    background_tasks: BackgroundTasks,
    universe: str = Query("nifty500", description="nifty500 | momentum | nifty50"),
    fresh_bars: int = Query(5, description="How many recent bars to consider fresh"),
    force: bool = Query(False, description="Force re-scan even if today's results exist"),
):
    """
    Return today's setups instantly from cache when available.
    If today's scan hasn't run yet, return the most recent cached scan (stale=True)
    and kick off today's scan in the background — frontend can poll or refresh later.
    Use force=true to always trigger a fresh scan synchronously.
    """
    from screener import run_screener
    from nifty500_universe import get_momentum_universe

    today = datetime.now().strftime("%Y-%m-%d")

    # ── 1. Serve today's cache instantly ──────────────────────
    if not force:
        conn = await get_connection()
        cached = await get_cached_scan(conn, today)

        if cached:
            await conn.close()
            return ScanResponse(
                scan_date=today,
                setups=_build_setups_from_rows(cached),
                total_found=len(cached),
                universe_size=len(cached),
                scan_duration_seconds=0.0,
                cached=True,
                stale=False,
            )

        # ── 2. No today's cache — return most recent scan instantly ──
        stale_date, stale_rows = await get_most_recent_cached_scan(conn)
        await conn.close()

        if stale_date:
            # Kick off background scan for today (non-blocking)
            background_tasks.add_task(
                lambda: executor.submit(_run_scan_background, universe, fresh_bars)
            )
            print(f"[Scan] Returning stale data from {stale_date}, background scan started for {today}")
            return ScanResponse(
                scan_date=stale_date,
                setups=_build_setups_from_rows(stale_rows),
                total_found=len(stale_rows),
                universe_size=len(stale_rows),
                scan_duration_seconds=0.0,
                cached=True,
                stale=True,
            )

    # ── 3. Force scan (synchronous, only when explicitly requested) ──
    if universe == "nifty50":
        from nifty500_universe import NIFTY_50
        tickers = NIFTY_50
    elif universe == "momentum":
        tickers = get_momentum_universe()
    else:
        from nifty500_universe import get_full_universe
        tickers = get_full_universe()

    t0 = time.time()
    loop = asyncio.get_event_loop()
    df = await loop.run_in_executor(
        executor,
        lambda: run_screener(tickers, lookback_days=350, fresh_bars=fresh_bars),
    )
    duration = round(time.time() - t0, 1)
    setups_raw = df.to_dict(orient="records") if not df.empty else []

    try:
        conn = await get_connection()
        await save_scan_results(conn, today, setups_raw, duration, len(tickers))
        await conn.close()
    except Exception as e:
        print(f"[DB] Failed to save scan: {e}")

    return ScanResponse(
        scan_date=today,
        setups=_build_setups_from_rows(setups_raw),
        total_found=len(setups_raw),
        universe_size=len(tickers),
        scan_duration_seconds=duration,
        cached=False,
        stale=False,
    )


# ── Positions ─────────────────────────────────────────────────

@app.get("/positions", response_model=list[PositionSchema])
async def list_positions(status: Optional[str] = Query(None, description="open | closed")):
    conn = await get_connection()
    rows = await get_positions(conn, status)
    await conn.close()
    return [PositionSchema(**_enrich_position(r)) for r in rows]


@app.post("/positions", response_model=PositionSchema, status_code=201)
async def add_position(body: PositionCreate):
    conn = await get_connection()
    data = body.model_dump()
    new_id = await create_position(conn, data)
    row = await get_position(conn, new_id)
    await conn.close()
    return PositionSchema(**_enrich_position(dict(row)))


@app.put("/positions/{position_id}", response_model=PositionSchema)
async def edit_position(position_id: int, body: PositionUpdate):
    conn = await get_connection()
    exists = await get_position(conn, position_id)
    if not exists:
        await conn.close()
        raise HTTPException(status_code=404, detail="Position not found")
    await update_position(conn, position_id, body.model_dump(exclude_none=True))
    row = await get_position(conn, position_id)
    await conn.close()
    return PositionSchema(**_enrich_position(dict(row)))


@app.delete("/positions/{position_id}", status_code=204)
async def remove_position(position_id: int):
    conn = await get_connection()
    ok = await delete_position(conn, position_id)
    await conn.close()
    if not ok:
        raise HTTPException(status_code=404, detail="Position not found")


@app.post("/positions/refresh-prices")
async def refresh_prices():
    """
    Fetch live prices for all open positions via yfinance, update DB,
    and fire Telegram stop-loss alerts for any breaches.
    """
    import yfinance as yf

    conn = await get_connection()
    open_positions = await get_positions(conn, "open")

    if not open_positions:
        await conn.close()
        return {"updated": 0, "stop_alerts": []}

    # Batch fetch prices — Kite (real-time) or yfinance (15-min delayed)
    tickers = list({p["ticker"] for p in open_positions})
    loop = asyncio.get_event_loop()

    def _fetch_prices(tkrs):
        # Try Kite live quotes first
        try:
            from kite_data import get_live_quotes, is_available
            if is_available():
                return get_live_quotes(tkrs)
        except ImportError:
            pass
        # yfinance fallback
        try:
            data = yf.download(tkrs, period="1d", auto_adjust=True, progress=False)
            if data.empty:
                return {}
            close = data["Close"] if "Close" in data.columns else data
            if hasattr(close, "columns"):
                return {str(col): float(close[col].dropna().iloc[-1])
                        for col in close.columns if not close[col].dropna().empty}
            return {tkrs[0]: float(close.dropna().iloc[-1])}
        except Exception as e:
            print(f"[PriceRefresh] Error: {e}")
            return {}

    prices = await loop.run_in_executor(executor, lambda: _fetch_prices(tickers))

    stop_alerts = []
    updated = 0

    for pos in open_positions:
        ticker  = pos["ticker"]
        price   = prices.get(ticker)
        if price is None:
            # Try single fetch
            try:
                def _single(t=ticker):
                    d = yf.download(t, period="1d", auto_adjust=True, progress=False)
                    return float(d["Close"].dropna().iloc[-1]) if not d.empty else None
                price = await loop.run_in_executor(executor, _single)
            except Exception:
                price = None

        if price is not None:
            await update_position_price(conn, pos["id"], price)
            updated += 1

            # Stop-loss breach check
            if price <= pos["stop_price"]:
                stop_alerts.append({
                    "ticker":     ticker,
                    "position_id": pos["id"],
                    "current":    round(price, 2),
                    "stop":       pos["stop_price"],
                })
                # Send Telegram alert
                try:
                    from telegram_alerts import send_message
                    msg = (
                        f"🚨 *STOP LOSS BREACH*\n"
                        f"*{ticker.replace('.NS','')}* hit ₹{price:.2f} "
                        f"(stop: ₹{pos['stop_price']:.2f})\n"
                        f"Action: Close position immediately"
                    )
                    await loop.run_in_executor(executor, lambda m=msg: send_message(m))
                except Exception as te:
                    print(f"[Telegram] Stop alert failed: {te}")

    await conn.close()
    return {"updated": updated, "stop_alerts": stop_alerts}


@app.get("/chart/{ticker}")
async def get_chart(ticker: str, days: int = Query(120, ge=30, le=365)):
    """
    Return OHLCV + 10-EMA + 50-SMA for a ticker.
    Uses Kite Connect if available, falls back to yfinance.
    """
    if not ticker.endswith(".NS"):
        ticker = ticker + ".NS"

    loop = asyncio.get_event_loop()

    def _fetch():
        try:
            from kite_data import get_chart_data
            bars = get_chart_data(ticker, days=days)
            if bars:
                return bars
        except ImportError:
            pass

        # yfinance fallback
        import yfinance as yf
        import numpy as np
        df = yf.download(ticker, period=f"{days + 60}d", auto_adjust=True, progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        if df.empty:
            return []
        df = df.tail(days).copy()
        df["ema10"]  = df["Close"].ewm(span=10, adjust=False).mean()
        df["sma50"]  = df["Close"].rolling(50).mean()
        df["sma200"] = df["Close"].rolling(200).mean()
        records = []
        for ts, row in df.iterrows():
            records.append({
                "date":   ts.strftime("%Y-%m-%d"),
                "open":   round(float(row["Open"]),  2),
                "high":   round(float(row["High"]),  2),
                "low":    round(float(row["Low"]),   2),
                "close":  round(float(row["Close"]), 2),
                "volume": int(row["Volume"]) if not np.isnan(row["Volume"]) else 0,
                "ema10":  round(float(row["ema10"]),  2) if not np.isnan(row["ema10"])  else None,
                "sma50":  round(float(row["sma50"]),  2) if not np.isnan(row["sma50"])  else None,
                "sma200": round(float(row["sma200"]), 2) if not np.isnan(row["sma200"]) else None,
                "source": "yfinance",
            })
        return records

    data = await loop.run_in_executor(executor, _fetch)
    if not data:
        raise HTTPException(status_code=404, detail=f"No data for {ticker}")
    return {"ticker": ticker, "bars": data}


# ── Backtest ──────────────────────────────────────────────────

@app.post("/backtest", response_model=BacktestResponse)
async def run_backtest_endpoint(body: BacktestRequest):
    """
    Run a full backtest. Use a small universe for fast results.
    Full Nifty 500 runs can take 5-30 min — run via CLI for those.
    """
    from data_manager import get_multiple_tickers
    from indicators import add_all_indicators
    from patterns import find_all_setups, deduplicate_setups
    from backtest_engine import run_portfolio_backtest
    from reporter import compute_stats, compute_max_drawdown
    from nifty500_universe import get_momentum_universe

    # Override account size if provided
    orig_account = cfg.ACCOUNT_SIZE
    cfg.ACCOUNT_SIZE = body.account_size

    # Resolve tickers
    if body.tickers:
        tickers = body.tickers
    elif body.universe == "nifty50":
        from nifty500_universe import NIFTY_50
        tickers = NIFTY_50
    else:
        from nifty500_universe import get_full_universe
        tickers = get_full_universe()  # full 500 from NSE cache

    t0 = time.time()
    loop = asyncio.get_event_loop()

    def _run():
        ticker_data = get_multiple_tickers(tickers, start=body.start, end=body.end)
        all_setups = []
        for ticker, df in ticker_data.items():
            df_ind = add_all_indicators(df, cfg)
            ticker_data[ticker] = df_ind
            all_setups.extend(find_all_setups(df_ind, ticker))
        all_setups = deduplicate_setups(all_setups)
        result = run_portfolio_backtest(ticker_data, all_setups)
        return result

    result = await loop.run_in_executor(executor, _run)
    cfg.ACCOUNT_SIZE = orig_account  # restore

    duration = round(time.time() - t0, 1)

    stats_dict = compute_stats(result.trades, body.account_size)
    max_dd     = compute_max_drawdown(result.equity_curve)
    stats_dict["max_drawdown_pct"] = max_dd

    # Equity curve → JSON-serializable list
    eq_curve = []
    for ts, val in result.equity_curve.items():
        if pd.notna(val):
            eq_curve.append(EquityPoint(date=ts.strftime("%Y-%m-%d"), value=float(val)))

    # Trades
    trade_records = [
        TradeRecord(
            ticker=t.ticker,
            pattern=t.pattern,
            entry_date=t.entry_date.strftime("%Y-%m-%d"),
            exit_date=t.exit_date.strftime("%Y-%m-%d") if t.exit_date else "",
            entry_price=t.entry_price,
            exit_price=t.exit_price,
            exit_reason=t.exit_reason,
            shares=t.shares,
            pnl=round(t.pnl, 2),
            pnl_pct=round(t.pnl_pct * 100, 2),
            r_multiple=round(t.r_multiple, 3),
            hold_days=t.hold_days,
        )
        for t in result.trades
    ]

    # Build BacktestStats safely
    s = stats_dict
    bt_stats = BacktestStats(
        total_trades=s.get("total_trades", 0),
        winners=s.get("winners", 0),
        losers=s.get("losers", 0),
        win_rate_pct=s.get("win_rate_pct", 0),
        avg_win_pct=s.get("avg_win_pct", 0),
        avg_loss_pct=s.get("avg_loss_pct", 0),
        profit_factor=s.get("profit_factor", 0),
        expectancy_r=s.get("expectancy_r", 0),
        avg_r=s.get("avg_r", 0),
        total_pnl_dollars=s.get("total_pnl_dollars", 0),
        total_return_pct=s.get("total_return_pct", 0),
        cagr_pct=s.get("cagr_pct", 0),
        max_drawdown_pct=max_dd,
        best_trade_r=s.get("best_trade_r", 0),
        worst_trade_r=s.get("worst_trade_r", 0),
        avg_hold_days=s.get("avg_hold_days", 0),
        breakout_trades=s.get("breakout_trades", 0),
        breakout_win_rate=s.get("breakout_win_rate", 0),
        ep_trades=s.get("ep_trades", 0),
        ep_win_rate=s.get("ep_win_rate", 0),
    )

    return BacktestResponse(
        stats=bt_stats,
        equity_curve=eq_curve,
        trades=trade_records,
        run_duration_seconds=duration,
    )


# ── Journal ───────────────────────────────────────────────────

def _enrich_journal(entry: dict) -> dict:
    ep = entry.get("exit_price")
    ent = entry["entry_price"]
    stp = entry.get("stop_price")
    sh  = entry.get("shares", 1)
    entry["status"] = "open" if not ep else "closed"
    if ep:
        entry["pnl"]       = round((ep - ent) * sh, 2)
        entry["pnl_pct"]   = round((ep - ent) / ent * 100, 2)
        risk = (ent - stp) * sh if stp and stp < ent else None
        entry["r_multiple"] = round(entry["pnl"] / risk, 2) if risk and risk > 0 else None
    else:
        entry["pnl"] = entry["pnl_pct"] = entry["r_multiple"] = None
    if entry.get("entry_date") and entry.get("exit_date"):
        from datetime import date
        d1 = date.fromisoformat(entry["entry_date"])
        d2 = date.fromisoformat(entry["exit_date"])
        entry["hold_days"] = (d2 - d1).days
    else:
        entry["hold_days"] = None
    return entry

@app.get("/journal", response_model=list[JournalSchema])
async def list_journal():
    conn = await get_connection()
    rows = await get_journal(conn)
    await conn.close()
    return [JournalSchema(**_enrich_journal(r)) for r in rows]

@app.post("/journal", response_model=JournalSchema, status_code=201)
async def add_journal_entry(body: JournalCreate):
    conn = await get_connection()
    data = body.model_dump()
    new_id = await create_journal_entry(conn, data)
    row = await get_journal_entry(conn, new_id)
    await conn.close()
    return JournalSchema(**_enrich_journal(dict(row)))

@app.put("/journal/{entry_id}", response_model=JournalSchema)
async def edit_journal_entry(entry_id: int, body: JournalUpdate):
    conn = await get_connection()
    exists = await get_journal_entry(conn, entry_id)
    if not exists:
        await conn.close()
        raise HTTPException(status_code=404, detail="Journal entry not found")
    await update_journal_entry(conn, entry_id, body.model_dump(exclude_none=True))
    row = await get_journal_entry(conn, entry_id)
    await conn.close()
    return JournalSchema(**_enrich_journal(dict(row)))

@app.delete("/journal/{entry_id}", status_code=204)
async def remove_journal_entry(entry_id: int):
    conn = await get_connection()
    await delete_journal_entry(conn, entry_id)
    await conn.close()

@app.get("/journal/analytics")
async def journal_analytics():
    conn = await get_connection()
    rows = await get_journal(conn)
    await conn.close()

    closed = [_enrich_journal(r) for r in rows if r.get("exit_price")]
    if not closed:
        return {
            "total": len(rows), "closed": 0, "open": len(rows),
            "win_rate": 0, "profit_factor": 0, "total_pnl": 0,
            "avg_win": 0, "avg_loss": 0, "avg_r": 0,
            "best_r": 0, "worst_r": 0, "expectancy_r": 0,
            "avg_hold_days": 0, "by_pattern": {}, "monthly": {},
        }

    winners = [t for t in closed if t["pnl"] and t["pnl"] > 0]
    losers  = [t for t in closed if t["pnl"] and t["pnl"] <= 0]
    rs      = [t["r_multiple"] for t in closed if t["r_multiple"] is not None]
    pnls    = [t["pnl"] for t in closed if t["pnl"] is not None]

    by_pattern: dict = {}
    for t in closed:
        p = t.get("pattern", "UNKNOWN") or "UNKNOWN"
        by_pattern.setdefault(p, {"trades": 0, "wins": 0, "total_pnl": 0.0})
        by_pattern[p]["trades"] += 1
        if t["pnl"] and t["pnl"] > 0:
            by_pattern[p]["wins"] += 1
        by_pattern[p]["total_pnl"] += t["pnl"] or 0

    monthly: dict = {}
    for t in closed:
        month = (t.get("exit_date") or "")[:7]
        monthly.setdefault(month, {"trades": 0, "pnl": 0.0})
        monthly[month]["trades"] += 1
        monthly[month]["pnl"] += t["pnl"] or 0

    gross_win  = sum(t["pnl"] for t in winners)
    gross_loss = abs(sum(t["pnl"] for t in losers)) or 1

    return {
        "total":           len(rows),
        "closed":          len(closed),
        "open":            len(rows) - len(closed),
        "win_rate":        round(len(winners) / len(closed) * 100, 1) if closed else 0,
        "profit_factor":   round(gross_win / gross_loss, 2),
        "total_pnl":       round(sum(pnls), 2),
        "avg_win":         round(sum(t["pnl"] for t in winners) / len(winners), 2) if winners else 0,
        "avg_loss":        round(sum(t["pnl"] for t in losers)  / len(losers),  2) if losers  else 0,
        "avg_r":           round(sum(rs) / len(rs), 2) if rs else 0,
        "best_r":          round(max(rs), 2) if rs else 0,
        "worst_r":         round(min(rs), 2) if rs else 0,
        "expectancy_r":    round(sum(rs) / len(rs), 2) if rs else 0,
        "avg_hold_days":   round(sum(t["hold_days"] for t in closed if t["hold_days"]) / len(closed), 1),
        "by_pattern":      by_pattern,
        "monthly":         dict(sorted(monthly.items())),
    }

@app.get("/journal/export")
async def export_journal():
    """Download full journal as CSV."""
    from fastapi.responses import StreamingResponse
    import csv, io
    conn = await get_connection()
    rows = await get_journal(conn)
    await conn.close()

    output = io.StringIO()
    fields = ["id","ticker","pattern","entry_date","exit_date","entry_price","exit_price",
              "shares","stop_price","pnl","pnl_pct","r_multiple","hold_days","notes","tags"]
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for r in rows:
        writer.writerow(_enrich_journal(r))

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=trade_journal.csv"},
    )


# ── Watchlist ─────────────────────────────────────────────────

@app.get("/watchlist", response_model=list[WatchlistSchema])
async def list_watchlist():
    conn = await get_connection()
    rows = await get_watchlist(conn)
    today = datetime.now().strftime("%Y-%m-%d")
    scan_tickers = {r["ticker"] for r in await _get_scan_tickers(conn, today)}
    await conn.close()
    return [WatchlistSchema(**{**r, "alert_on_scan": bool(r["alert_on_scan"]),
                               "in_todays_scan": r["ticker"] in scan_tickers}) for r in rows]

@app.post("/watchlist", response_model=WatchlistSchema, status_code=201)
async def add_watchlist(body: WatchlistCreate):
    ticker = body.ticker.upper()
    if not ticker.endswith(".NS"):
        ticker += ".NS"
    conn = await get_connection()
    await add_to_watchlist(conn, {"ticker": ticker, "notes": body.notes, "alert_on_scan": int(body.alert_on_scan)})
    rows = await get_watchlist(conn)
    today = datetime.now().strftime("%Y-%m-%d")
    scan_tickers = {r["ticker"] for r in await _get_scan_tickers(conn, today)}
    await conn.close()
    row = next((r for r in rows if r["ticker"] == ticker), rows[0])
    return WatchlistSchema(**{**row, "alert_on_scan": bool(row["alert_on_scan"]),
                              "in_todays_scan": row["ticker"] in scan_tickers})

@app.delete("/watchlist/{ticker}", status_code=204)
async def remove_watchlist(ticker: str):
    if not ticker.endswith(".NS"):
        ticker += ".NS"
    conn = await get_connection()
    await remove_from_watchlist(conn, ticker)
    await conn.close()

async def _get_scan_tickers(conn, scan_date: str) -> list[dict]:
    from api.database import get_scan_setups_for_date
    return await get_scan_setups_for_date(conn, scan_date)


# ── Paper Trading ──────────────────────────────────────────────

def _enrich_paper_trade(pt: dict) -> dict:
    """Add computed pnl / r-multiple fields to a paper trade dict."""
    entry  = pt["entry_price"]
    stop   = pt["stop_price"]
    shares = pt.get("shares", 1)
    ep     = pt.get("exit_price")
    cur    = pt.get("current_price")
    risk   = (entry - stop) * shares if stop < entry else None

    if ep:
        pt["pnl"]       = round((ep - entry) * shares, 2)
        pt["pnl_pct"]   = round((ep - entry) / entry * 100, 2)
        pt["r_multiple"] = round(pt["pnl"] / risk, 2) if risk and risk > 0 else None
        pt["unrealized_pnl"]     = None
        pt["unrealized_pnl_pct"] = None
    else:
        pt["pnl"] = pt["pnl_pct"] = pt["r_multiple"] = None
        if cur:
            pt["unrealized_pnl"]     = round((float(cur) - entry) * shares, 2)
            pt["unrealized_pnl_pct"] = round((float(cur) - entry) / entry * 100, 2)
        else:
            pt["unrealized_pnl"] = pt["unrealized_pnl_pct"] = None

    if pt.get("entry_date") and pt.get("exit_date"):
        from datetime import date
        d1 = date.fromisoformat(pt["entry_date"])
        d2 = date.fromisoformat(pt["exit_date"])
        pt["hold_days"] = (d2 - d1).days
    else:
        pt["hold_days"] = None

    pt.setdefault("exit_reason", "")
    pt.setdefault("signal_date", "")
    pt.setdefault("notes", "")
    return pt


@app.get("/paper", response_model=list[PaperTradeSchema])
async def list_paper_trades(status: Optional[str] = Query(None)):
    conn = await get_connection()
    rows = await get_paper_trades(conn, status)
    await conn.close()
    return [PaperTradeSchema(**_enrich_paper_trade(r)) for r in rows]


@app.post("/paper", response_model=PaperTradeSchema, status_code=201)
async def add_paper_trade(body: PaperTradeCreate):
    conn = await get_connection()
    data = body.model_dump()
    new_id = await create_paper_trade(conn, data)
    row = await get_paper_trade(conn, new_id)
    await conn.close()
    return PaperTradeSchema(**_enrich_paper_trade(dict(row)))


@app.put("/paper/{trade_id}", response_model=PaperTradeSchema)
async def edit_paper_trade(trade_id: int, body: PaperTradeUpdate):
    conn = await get_connection()
    exists = await get_paper_trade(conn, trade_id)
    if not exists:
        await conn.close()
        raise HTTPException(status_code=404, detail="Paper trade not found")
    await update_paper_trade(conn, trade_id, body.model_dump(exclude_none=True))
    row = await get_paper_trade(conn, trade_id)
    await conn.close()
    return PaperTradeSchema(**_enrich_paper_trade(dict(row)))


@app.delete("/paper/{trade_id}", status_code=204)
async def remove_paper_trade(trade_id: int):
    conn = await get_connection()
    await delete_paper_trade(conn, trade_id)
    await conn.close()


@app.get("/paper/stats")
async def paper_trade_stats():
    """System-level statistics for all paper trades."""
    conn = await get_connection()
    rows = await get_paper_trades(conn)
    await conn.close()

    all_trades = [_enrich_paper_trade(r) for r in rows]
    closed = [t for t in all_trades if t.get("exit_price")]
    open_  = [t for t in all_trades if not t.get("exit_price")]

    if not closed:
        return {"total": len(all_trades), "closed": 0, "open": len(open_), "win_rate": 0,
                "profit_factor": 0, "expectancy_r": 0, "total_pnl": 0, "avg_r": 0,
                "by_pattern": {}}

    winners = [t for t in closed if t["pnl"] and t["pnl"] > 0]
    losers  = [t for t in closed if t["pnl"] and t["pnl"] <= 0]
    rs      = [t["r_multiple"] for t in closed if t["r_multiple"] is not None]

    gross_win  = sum(t["pnl"] for t in winners)
    gross_loss = abs(sum(t["pnl"] for t in losers)) or 1

    by_pattern: dict = {}
    for t in closed:
        p = t.get("pattern", "UNKNOWN") or "UNKNOWN"
        by_pattern.setdefault(p, {"trades": 0, "wins": 0, "total_pnl": 0.0})
        by_pattern[p]["trades"] += 1
        if t["pnl"] and t["pnl"] > 0:
            by_pattern[p]["wins"] += 1
        by_pattern[p]["total_pnl"] += t["pnl"] or 0

    return {
        "total":          len(all_trades),
        "closed":         len(closed),
        "open":           len(open_),
        "win_rate":       round(len(winners) / len(closed) * 100, 1),
        "profit_factor":  round(gross_win / gross_loss, 2),
        "expectancy_r":   round(sum(rs) / len(rs), 2) if rs else 0,
        "total_pnl":      round(sum(t["pnl"] for t in closed if t["pnl"]), 2),
        "avg_r":          round(sum(rs) / len(rs), 2) if rs else 0,
        "best_r":         round(max(rs), 2) if rs else 0,
        "worst_r":        round(min(rs), 2) if rs else 0,
        "by_pattern":     by_pattern,
    }


@app.post("/paper/refresh-prices")
async def refresh_paper_prices():
    """Update current_price for all open paper trades."""
    import yfinance as yf

    conn = await get_connection()
    open_trades = await get_paper_trades(conn, "open")
    if not open_trades:
        await conn.close()
        return {"updated": 0}

    tickers = list({t["ticker"] for t in open_trades})
    loop = asyncio.get_event_loop()

    def _fetch():
        data = yf.download(tickers, period="1d", auto_adjust=True, progress=False)
        if data.empty:
            return {}
        close = data["Close"]
        if isinstance(close.columns if hasattr(close, "columns") else None, object):
            return {str(c): float(close[c].dropna().iloc[-1])
                    for c in close.columns if not close[c].dropna().empty}
        return {tickers[0]: float(close.dropna().iloc[-1])}

    prices = await loop.run_in_executor(executor, _fetch)
    updated = 0
    for pt in open_trades:
        price = prices.get(pt["ticker"])
        if price:
            await update_paper_trade_price(conn, pt["id"], price)
            updated += 1

    await conn.close()
    return {"updated": updated}


# ── Kite Connect data source ──────────────────────────────────

@app.get("/kite/status")
async def kite_status():
    """Check if Kite Connect is configured and the access token is valid."""
    try:
        from kite_data import status
        return status()
    except ImportError:
        return {"connected": False, "reason": "kiteconnect package not installed — pip install kiteconnect"}

@app.get("/kite/login-url")
async def kite_login_url():
    """Return the Zerodha login URL for today's session."""
    try:
        from kite_data import login_url
        return {"url": login_url()}
    except ImportError:
        return {"url": None, "error": "pip install kiteconnect"}

@app.post("/kite/set-token")
async def kite_set_token(request_token: str = Query(..., description="request_token from Zerodha redirect")):
    """
    Exchange a Zerodha request_token for an access_token.
    Call once per day after visiting the login URL.
    """
    try:
        from kite_data import set_access_token
        token = set_access_token(request_token)
        return {"access_token": token, "saved_to_env": True}
    except ImportError:
        raise HTTPException(status_code=500, detail="pip install kiteconnect")

@app.get("/kite/instruments/refresh")
async def kite_refresh_instruments():
    """Refresh the NSE instrument token map from Kite."""
    try:
        from kite_data import _refresh_instrument_map, _TOKEN_MAP
        _refresh_instrument_map()
        from kite_data import _TOKEN_MAP as tm
        return {"instruments_loaded": len(tm)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Scan history ──────────────────────────────────────────────

@app.get("/scan/history")
async def scan_history(limit: int = Query(30)):
    conn = await get_connection()
    history = await get_scan_history(conn, limit)
    await conn.close()
    return history


# ── Corporate Announcements ────────────────────────────────────

@app.get("/announcements")
async def get_announcements(days: int = Query(7, ge=1, le=30)):
    """Disabled — NSE scraping is too resource-heavy for personal use."""
    return {"announcements": [], "count": 0, "days": days}


# ── Sector Performance ─────────────────────────────────────────

_sector_cache: dict = {}
_sector_cache_ts: float = 0.0
_SECTOR_TTL = 1800  # 30 min

SECTOR_INDICES = {
    "IT & Tech":    "^CNXIT",
    "Banking":      "^NSEBANK",
    "Pharma":       "^CNXPHARMA",
    "Auto":         "^CNXAUTO",
    "Metals":       "^CNXMETAL",
    "Realty":       "^CNXREALTY",
    "Energy":       "^CNXENERGY",
    "Infra":        "^CNXINFRA",
    "FMCG":         "^CNXFMCG",
    "Media":        "^CNXMEDIA",
    "PSU Bank":     "^CNXPSUBANK",
    "Midcap":       "^NSMIDCP",
}

def _fetch_sector_performance() -> list[dict]:
    global _sector_cache, _sector_cache_ts
    if _sector_cache and (time.time() - _sector_cache_ts) < _SECTOR_TTL:
        return _sector_cache

    import yfinance as yf
    import numpy as np

    tickers = list(SECTOR_INDICES.values())
    names   = list(SECTOR_INDICES.keys())

    try:
        df = yf.download(tickers, period="100d", auto_adjust=True, progress=False)
        close = df["Close"] if isinstance(df.columns, pd.MultiIndex) else df
    except Exception:
        return []

    results = []
    for name, ticker in SECTOR_INDICES.items():
        try:
            s = close[ticker].dropna() if ticker in close.columns else None
            if s is None or len(s) < 5:
                continue
            price  = float(s.iloc[-1])
            sma50  = float(s.rolling(50).mean().iloc[-1]) if len(s) >= 50 else None

            def ret(n):
                if len(s) <= n:
                    return None
                prev = float(s.iloc[-n - 1])
                return round((price - prev) / prev * 100, 2) if prev else None

            r1d = ret(1); r1w = ret(5); r1m = ret(21); r3m = ret(63)

            # Status
            if r1m is not None and r3m is not None:
                if r1m > 3 and r3m > 0:
                    status = "HOT"
                elif r1m > 0:
                    status = "WARM"
                elif r1m > -5:
                    status = "COLD"
                else:
                    status = "WEAK"
            else:
                status = "COLD"

            results.append({
                "sector":        name,
                "ticker":        ticker,
                "price":         round(price, 1),
                "sma50":         round(sma50, 1) if sma50 else None,
                "above_sma50":   bool(sma50 and price > sma50),
                "return_1d":     r1d,
                "return_1w":     r1w,
                "return_1m":     r1m,
                "return_3m":     r3m,
                "status":        status,
            })
        except Exception:
            continue

    results.sort(key=lambda x: (x.get("return_1m") or -999), reverse=True)
    _sector_cache = results
    _sector_cache_ts = time.time()
    return results


@app.get("/sectors/performance")
async def sector_performance():
    """NSE sector index returns — 1D/1W/1M/3M. Cached 30 min."""
    loop = asyncio.get_event_loop()
    data = await loop.run_in_executor(executor, _fetch_sector_performance)
    return {"sectors": data, "count": len(data)}


# ── Market Quadrant (breadth-based) ────────────────────────────

_quadrant_cache: dict = {}
_quadrant_cache_ts: float = 0.0
_QUADRANT_TTL = 3600  # 1 hour


def _fetch_market_quadrant() -> dict:
    global _quadrant_cache, _quadrant_cache_ts
    if _quadrant_cache and (time.time() - _quadrant_cache_ts) < _QUADRANT_TTL:
        return _quadrant_cache

    try:
        import sys as _sys
        _sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
        from nifty500_universe import get_nifty500
        import yfinance as yf

        tickers = get_nifty500()
        closes = yf.download(tickers, period="1y", auto_adjust=True, progress=False)["Close"]
        closes = closes.dropna(axis=1, how="all")

        n = len(closes.columns)
        if n == 0:
            return {}

        # ── Moving averages ──────────────────────────────────────
        sma10  = closes.rolling(10).mean()
        sma50  = closes.rolling(50).mean()
        sma200 = closes.rolling(200).mean()

        latest = closes.iloc[-1]
        above_10  = int((latest > sma10.iloc[-1]).sum())
        above_50  = int((latest > sma50.iloc[-1]).sum())
        above_200 = int((latest > sma200.iloc[-1]).sum())

        pct10  = round(above_10  / n * 100, 1)
        pct50  = round(above_50  / n * 100, 1)
        pct200 = round(above_200 / n * 100, 1)

        # ── Net New Highs (NNH) — Nitin uses 20d, 65d, 52w ──────
        def _nnh(window: int) -> int:
            rh = closes.rolling(window, min_periods=window // 2).max()
            rl = closes.rolling(window, min_periods=window // 2).min()
            return int((latest >= rh.iloc[-1] * 0.99).sum()) - int((latest <= rl.iloc[-1] * 1.01).sum())

        nnh_20  = _nnh(20)
        nnh_65  = _nnh(65)
        nnh_52w = _nnh(252)

        # 52-week raw counts for display
        high52    = closes.rolling(252, min_periods=200).max().iloc[-1]
        low52     = closes.rolling(252, min_periods=200).min().iloc[-1]
        new_highs = int((latest >= high52 * 0.99).sum())
        new_lows  = int((latest <= low52  * 1.01).sum())

        # ── Weekly breadth series (last 13 weeks) ────────────────
        weekly_p50: list[float] = []
        for i in range(13, 0, -1):
            idx = -(i * 5)
            if abs(idx) > len(closes):
                continue
            c = closes.iloc[idx]
            s = sma50.iloc[idx]
            weekly_p50.append(float((c > s).sum() / n * 100))

        # ── Momentum: ROC vs its own 9-week SMA (like Nitin) ─────
        if len(weekly_p50) >= 5:
            roc_series = [weekly_p50[i] - weekly_p50[i - 4] for i in range(4, len(weekly_p50))]
            mom_raw  = roc_series[-1]
            mom_ma9  = sum(roc_series) / len(roc_series)
            momentum_change = round(mom_raw, 1)
            momentum = "RISING" if mom_raw > mom_ma9 else "FALLING"
        else:
            fallback = float((closes.iloc[-20] > sma50.iloc[-20]).sum() / n * 100)
            momentum_change = round(pct50 - fallback, 1)
            momentum = "RISING" if momentum_change > 0 else "FALLING"

        # ── Swing Confidence 0–100 (composite like Nitin) ────────
        sc = min(round(pct10 * 0.40), 40)   # 0–40 from short-term breadth
        sc += 20 if nnh_20  > 0 else 0       # +20 if 20-day NNH positive
        sc += 20 if nnh_65  > 0 else 0       # +20 if 65-day NNH positive
        sc += 20 if momentum == "RISING" else 0  # +20 if momentum improving
        swing_confidence = sc

        # ── Quadrant labels ───────────────────────────────────────
        bias  = "BULL" if pct200 >= 50 else "BEAR"
        # Trend: needs both 50-SMA breadth AND 52w NNH positive (Nitin's rule)
        trend = "UP" if pct50 >= 50 and nnh_52w > 0 else "DOWN"
        swing = ("HOT"  if pct10 >= 70 else
                 "WARM" if pct10 >= 50 else
                 "COOL" if pct10 >= 30 else "COLD")

        bulls   = sum([bias == "BULL", trend == "UP", pct10 >= 50, momentum == "RISING"])
        overall = "INVEST" if bulls >= 3 else "SELECTIVE" if bulls == 2 else "CASH"

        # ── Breadth Thrust (Zweig-style) ──────────────────────────
        # Swing breadth < 25% any time in last 10 sessions → now > 40%
        thrust = False
        if pct10 > 40:
            for i in range(2, min(12, len(closes))):
                pp = float((closes.iloc[-i] > sma10.iloc[-i]).sum() / n * 100)
                if pp < 25:
                    thrust = True
                    break

        # ── Phase duration: consecutive weeks in same overall ─────
        phase_weeks = 0
        for i in range(1, min(53, len(closes) // 5)):
            idx = -(i * 5)
            if abs(idx) > len(closes):
                break
            c   = closes.iloc[idx]
            p10  = float((c > sma10.iloc[idx]).sum()  / n * 100)
            p50  = float((c > sma50.iloc[idx]).sum()  / n * 100)
            p200 = float((c > sma200.iloc[idx]).sum() / n * 100)
            idx2 = idx - 20
            mom_p = p50 - float((closes.iloc[idx2] > sma50.iloc[idx2]).sum() / n * 100) if abs(idx2) <= len(closes) else 0
            nnh_p = _nnh(252)  # use current as proxy (expensive to recompute)
            b_p   = "BULL" if p200 >= 50 else "BEAR"
            t_p   = "UP"   if p50  >= 50 and nnh_p > 0 else "DOWN"
            bulls_p = sum([b_p == "BULL", t_p == "UP", p10 >= 50, mom_p > 0])
            ov_p    = "INVEST" if bulls_p >= 3 else "SELECTIVE" if bulls_p == 2 else "CASH"
            if ov_p == overall:
                phase_weeks += 1
            else:
                break

        # ── What Would Change This ────────────────────────────────
        to_upgrade: list[dict] = []
        if overall in ("CASH", "SELECTIVE"):
            target = "INVEST" if overall == "SELECTIVE" else "SELECTIVE"
            conditions = []
            if pct10 < 50:
                conditions.append({"metric": "Swing breadth (10-SMA)", "current": pct10,
                                    "needs": 50.0, "gap": round(50 - pct10, 1)})
            if momentum == "FALLING":
                conditions.append({"metric": "Momentum", "current": momentum_change,
                                    "needs": 0.0, "gap": round(-momentum_change, 1) if momentum_change < 0 else 0})
            if conditions:
                to_upgrade.append({"to": target, "conditions": conditions})

        if overall == "CASH":
            invest_conds = []
            if pct200 < 50:
                invest_conds.append({"metric": "Bias (200-SMA breadth)", "current": pct200,
                                     "needs": 50.0, "gap": round(50 - pct200, 1)})
            if pct50 < 50:
                invest_conds.append({"metric": "Trend (50-SMA breadth)", "current": pct50,
                                     "needs": 50.0, "gap": round(50 - pct50, 1)})
            if nnh_52w <= 0:
                invest_conds.append({"metric": "52-week Net New Highs", "current": float(nnh_52w),
                                     "needs": 1.0, "gap": float(1 - nnh_52w)})
            if invest_conds:
                to_upgrade.append({"to": "INVEST", "conditions": invest_conds})

        result = {
            "bias": bias, "trend": trend, "swing": swing, "momentum": momentum,
            "swing_confidence": swing_confidence,
            "momentum_change": momentum_change,
            "pct_above_10": pct10, "pct_above_50": pct50, "pct_above_200": pct200,
            "above_10": above_10, "above_50": above_50, "above_200": above_200,
            "total": n,
            "nnh_20": nnh_20, "nnh_65": nnh_65, "nnh_52w": nnh_52w,
            "new_highs": new_highs, "new_lows": new_lows,
            "overall": overall,
            "phase_weeks": phase_weeks,
            "thrust_detected": thrust,
            "to_upgrade": to_upgrade,
            "updated_at": datetime.now(pytz.timezone("Asia/Kolkata")).isoformat(),
        }
        _quadrant_cache = result
        _quadrant_cache_ts = time.time()
        return result

    except Exception as e:
        print(f"[quadrant] Error: {e}")
        return {}


@app.post("/market-quadrant/refresh")
async def refresh_market_quadrant():
    """Force-clear the quadrant cache so next GET recomputes fresh."""
    global _quadrant_cache, _quadrant_cache_ts
    _quadrant_cache = {}
    _quadrant_cache_ts = 0.0
    return {"cleared": True}


@app.get("/market-quadrant")
async def get_market_quadrant():
    """Nifty 500 breadth-based market quadrant. Cached 1 h."""
    loop = asyncio.get_event_loop()
    data = await loop.run_in_executor(executor, _fetch_market_quadrant)
    if not data:
        raise HTTPException(status_code=503, detail="Could not compute market quadrant")
    return data

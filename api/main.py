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
    db, get_connection, init_db,
    get_positions, get_position, create_position, update_position, delete_position,
    save_scan_results, get_scan_history, get_cached_scan, get_most_recent_cached_scan,
    update_position_price, fetch_live_prices,
    get_journal, get_journal_entry, create_journal_entry, update_journal_entry, delete_journal_entry,
    get_watchlist, add_to_watchlist, remove_from_watchlist, get_watchlist_tickers,
    get_paper_trades, get_paper_trade, create_paper_trade, update_paper_trade,
    delete_paper_trade, update_paper_trade_price,
    get_scan_setups_for_date, get_market_cache, set_market_cache,
    enrich_trade, compute_trade_stats,
)
from api.scheduler import create_scheduler


# ── App Lifecycle ─────────────────────────────────────────────

executor = ThreadPoolExecutor(max_workers=8)
_scheduler = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _scheduler
    async with db() as conn:
        await init_db(conn)
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
_REGIME_TTL = 300

def _market_regime() -> dict:
    global _regime_cache, _regime_cache_ts
    if _regime_cache and (time.time() - _regime_cache_ts) < _REGIME_TTL:
        return _regime_cache
    try:
        import yfinance as yf
        df = yf.download("^NSEI", period="300d", auto_adjust=True, progress=False)
        if df.empty or len(df) < 50:
            return {"bullish": True, "index_price": None, "sma200": None, "note": "No data"}
        close = df["Close"].squeeze()
        price = float(close.iloc[-1])
        sma200 = float(close.rolling(200).mean().iloc[-1]) if len(close) >= 200 else float(close.rolling(50).mean().iloc[-1])
        bullish = price > sma200
        result = {
            "bullish": bullish, "index_price": round(price, 1), "sma200": round(sma200, 1),
            "note": "Above 200-SMA — Bull market" if bullish else "Below 200-SMA — Bear market, trade small",
        }
        _regime_cache = result
        _regime_cache_ts = time.time()
        return result
    except Exception as e:
        return {"bullish": True, "index_price": None, "sma200": None, "note": f"Regime check failed: {e}"}


def _compute_sizing(setup_row: dict, account_size: float) -> dict:
    entry = float(setup_row.get("entry_price", 0))
    stop = float(setup_row.get("stop_price", 0))
    atr14 = float(setup_row.get("atr14", 0) or 0)
    risk_per_share = entry - stop
    if risk_per_share <= 0:
        return {"position_size_shares": 0, "position_value": 0.0, "risk_amount": 0.0}
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
    current = pos.get("current_price")
    if current and pos.get("status") == "open":
        entry = pos["entry_price"]
        shares = pos["shares"]
        pos["unrealized_pnl"] = round((float(current) - entry) * shares, 2)
        pos["unrealized_pnl_pct"] = round((float(current) - entry) / entry * 100, 3)
    else:
        pos["unrealized_pnl"] = None
        pos["unrealized_pnl_pct"] = None
    risk = (pos["entry_price"] - pos["stop_price"]) * pos["shares"]
    pos["risk_amount"] = round(max(risk, 0), 2)
    return pos


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


# ── Routes ────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse)
async def health():
    db_ok = True
    try:
        async with db() as conn:
            await conn.execute("SELECT 1")
    except Exception:
        db_ok = False

    loop = asyncio.get_event_loop()
    regime = await loop.run_in_executor(executor, _market_regime)

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


# ── Scan ─────────────────────────────────────────────────────

def _run_scan_background(universe: str, fresh_bars: int) -> None:
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

    print(f"[BG Scan] Starting {universe} scan ({len(tickers)} tickers) for {today}…")
    t0 = time.time()
    try:
        df = run_screener(tickers, lookback_days=450, fresh_bars=fresh_bars)
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
    fresh_bars: int = Query(10),
    force: bool = Query(False),
):
    from screener import run_screener
    from nifty500_universe import get_momentum_universe

    today = datetime.now().strftime("%Y-%m-%d")

    if not force:
        async with db() as conn:
            cached = await get_cached_scan(conn, today)
            if cached is not None:
                cur = await conn.execute(
                    "SELECT universe_sz FROM scan_runs WHERE scan_date = ? ORDER BY created_at DESC LIMIT 1", (today,)
                )
                run = await cur.fetchone()
                universe_sz = run[0] if run else len(cached)
                return ScanResponse(
                    scan_date=today, setups=_build_setups_from_rows(cached),
                    total_found=len(cached), universe_size=universe_sz,
                    scan_duration_seconds=0.0, cached=True, stale=False,
                )

            stale_date, stale_rows = await get_most_recent_cached_scan(conn)
            stale_universe_sz = 0
            if stale_date:
                cur = await conn.execute(
                    "SELECT universe_sz FROM scan_runs WHERE scan_date = ? ORDER BY created_at DESC LIMIT 1", (stale_date,)
                )
                run = await cur.fetchone()
                stale_universe_sz = run[0] if run else 0

        if stale_date:
            background_tasks.add_task(
                lambda: executor.submit(_run_scan_background, universe, fresh_bars)
            )
            print(f"[Scan] Returning stale data from {stale_date}, background scan started for {today}")
            return ScanResponse(
                scan_date=stale_date, setups=_build_setups_from_rows(stale_rows),
                total_found=len(stale_rows), universe_size=stale_universe_sz,
                scan_duration_seconds=0.0, cached=True, stale=True,
            )

    # Force scan
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
        executor, lambda: run_screener(tickers, lookback_days=450, fresh_bars=fresh_bars),
    )
    duration = round(time.time() - t0, 1)
    setups_raw = df.to_dict(orient="records") if not df.empty else []

    try:
        async with db() as conn:
            await save_scan_results(conn, today, setups_raw, duration, len(tickers))
    except Exception as e:
        print(f"[DB] Failed to save scan: {e}")

    return ScanResponse(
        scan_date=today, setups=_build_setups_from_rows(setups_raw),
        total_found=len(setups_raw), universe_size=len(tickers),
        scan_duration_seconds=duration, cached=False, stale=False,
    )


# ── Positions ─────────────────────────────────────────────────

@app.get("/positions", response_model=list[PositionSchema])
async def list_positions(status: Optional[str] = Query(None)):
    async with db() as conn:
        rows = await get_positions(conn, status)
    return [PositionSchema(**_enrich_position(r)) for r in rows]


@app.post("/positions", response_model=PositionSchema, status_code=201)
async def add_position(body: PositionCreate):
    async with db() as conn:
        new_id = await create_position(conn, body.model_dump())
        row = await get_position(conn, new_id)
    return PositionSchema(**_enrich_position(dict(row)))


@app.put("/positions/{position_id}", response_model=PositionSchema)
async def edit_position(position_id: int, body: PositionUpdate):
    async with db() as conn:
        exists = await get_position(conn, position_id)
        if not exists:
            raise HTTPException(status_code=404, detail="Position not found")
        await update_position(conn, position_id, body.model_dump(exclude_none=True))
        row = await get_position(conn, position_id)
    return PositionSchema(**_enrich_position(dict(row)))


@app.delete("/positions/{position_id}", status_code=204)
async def remove_position(position_id: int):
    async with db() as conn:
        await delete_position(conn, position_id)


@app.post("/positions/refresh-prices")
async def refresh_prices():
    async with db() as conn:
        open_positions = await get_positions(conn, "open")
        if not open_positions:
            return {"updated": 0, "stop_alerts": []}

        tickers = list({p["ticker"] for p in open_positions})
        prices = await fetch_live_prices(tickers)

        stop_alerts = []
        updated = 0

        for pos in open_positions:
            price = prices.get(pos["ticker"])
            if price is None:
                continue
            await update_position_price(conn, pos["id"], price)
            updated += 1

            if price <= pos["stop_price"]:
                stop_alerts.append({
                    "ticker": pos["ticker"], "position_id": pos["id"],
                    "current": round(price, 2), "stop": pos["stop_price"],
                })
                try:
                    from telegram_alerts import send_message
                    msg = (f"🚨 *STOP LOSS BREACH*\n"
                           f"*{pos['ticker'].replace('.NS','')}* hit ₹{price:.2f} "
                           f"(stop: ₹{pos['stop_price']:.2f})\nAction: Close position immediately")
                    loop = asyncio.get_event_loop()
                    await loop.run_in_executor(executor, lambda m=msg: send_message(m))
                except Exception as te:
                    print(f"[Telegram] Stop alert failed: {te}")

    return {"updated": updated, "stop_alerts": stop_alerts}


# ── Chart ────────────────────────────────────────────────────

@app.get("/chart/{ticker}")
async def get_chart(ticker: str, days: int = Query(120, ge=30, le=365)):
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
        import yfinance as yf
        import numpy as np
        df = yf.download(ticker, period=f"{days + 220}d", auto_adjust=True, progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        if df.empty:
            return []
        df = df.tail(days).copy()
        df["ema10"] = df["Close"].ewm(span=10, adjust=False).mean()
        df["sma50"] = df["Close"].rolling(50).mean()
        df["sma200"] = df["Close"].rolling(200).mean()
        records = []
        for ts, row in df.iterrows():
            records.append({
                "date": ts.strftime("%Y-%m-%d"),
                "open": round(float(row["Open"]), 2), "high": round(float(row["High"]), 2),
                "low": round(float(row["Low"]), 2), "close": round(float(row["Close"]), 2),
                "volume": int(row["Volume"]) if not np.isnan(row["Volume"]) else 0,
                "ema10": round(float(row["ema10"]), 2) if not np.isnan(row["ema10"]) else None,
                "sma50": round(float(row["sma50"]), 2) if not np.isnan(row["sma50"]) else None,
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
    from data_manager import get_multiple_tickers
    from indicators import add_all_indicators
    from patterns import find_all_setups, deduplicate_setups
    from backtest_engine import run_portfolio_backtest
    from reporter import compute_stats, compute_max_drawdown

    account_size = body.account_size
    orig_account = cfg.ACCOUNT_SIZE
    cfg.ACCOUNT_SIZE = account_size

    if body.tickers:
        tickers = body.tickers
    elif body.universe == "nifty50":
        from nifty500_universe import NIFTY_50
        tickers = NIFTY_50
    else:
        from nifty500_universe import get_full_universe
        tickers = get_full_universe()

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
        return run_portfolio_backtest(ticker_data, all_setups)

    result = await loop.run_in_executor(executor, _run)
    cfg.ACCOUNT_SIZE = orig_account

    duration = round(time.time() - t0, 1)
    stats_dict = compute_stats(result.trades, account_size)
    max_dd = compute_max_drawdown(result.equity_curve)
    stats_dict["max_drawdown_pct"] = max_dd

    eq_curve = [
        EquityPoint(date=ts.strftime("%Y-%m-%d"), value=float(val))
        for ts, val in result.equity_curve.items() if pd.notna(val)
    ]
    trade_records = [
        TradeRecord(
            ticker=t.ticker, pattern=t.pattern,
            entry_date=t.entry_date.strftime("%Y-%m-%d"),
            exit_date=t.exit_date.strftime("%Y-%m-%d") if t.exit_date else "",
            entry_price=t.entry_price, exit_price=t.exit_price,
            exit_reason=t.exit_reason, shares=t.shares,
            pnl=round(t.pnl, 2), pnl_pct=round(t.pnl_pct * 100, 2),
            r_multiple=round(t.r_multiple, 3), hold_days=t.hold_days,
        ) for t in result.trades
    ]

    s = stats_dict
    bt_stats = BacktestStats(
        total_trades=s.get("total_trades", 0), winners=s.get("winners", 0),
        losers=s.get("losers", 0), win_rate_pct=s.get("win_rate_pct", 0),
        avg_win_pct=s.get("avg_win_pct", 0), avg_loss_pct=s.get("avg_loss_pct", 0),
        profit_factor=s.get("profit_factor", 0), expectancy_r=s.get("expectancy_r", 0),
        avg_r=s.get("avg_r", 0), total_pnl_dollars=s.get("total_pnl_dollars", 0),
        total_return_pct=s.get("total_return_pct", 0), cagr_pct=s.get("cagr_pct", 0),
        max_drawdown_pct=max_dd, best_trade_r=s.get("best_trade_r", 0),
        worst_trade_r=s.get("worst_trade_r", 0), avg_hold_days=s.get("avg_hold_days", 0),
        breakout_trades=s.get("breakout_trades", 0), breakout_win_rate=s.get("breakout_win_rate", 0),
        ep_trades=s.get("ep_trades", 0), ep_win_rate=s.get("ep_win_rate", 0),
    )

    return BacktestResponse(
        stats=bt_stats, equity_curve=eq_curve,
        trades=trade_records, run_duration_seconds=duration,
    )


# ── Journal ───────────────────────────────────────────────────

@app.get("/journal", response_model=list[JournalSchema])
async def list_journal():
    async with db() as conn:
        rows = await get_journal(conn)
    return [JournalSchema(**enrich_trade(r)) for r in rows]

@app.post("/journal", response_model=JournalSchema, status_code=201)
async def add_journal_entry(body: JournalCreate):
    async with db() as conn:
        new_id = await create_journal_entry(conn, body.model_dump())
        row = await get_journal_entry(conn, new_id)
    return JournalSchema(**enrich_trade(dict(row)))

@app.put("/journal/{entry_id}", response_model=JournalSchema)
async def edit_journal_entry(entry_id: int, body: JournalUpdate):
    async with db() as conn:
        exists = await get_journal_entry(conn, entry_id)
        if not exists:
            raise HTTPException(status_code=404, detail="Journal entry not found")
        await update_journal_entry(conn, entry_id, body.model_dump(exclude_none=True))
        row = await get_journal_entry(conn, entry_id)
    return JournalSchema(**enrich_trade(dict(row)))

@app.delete("/journal/{entry_id}", status_code=204)
async def remove_journal_entry(entry_id: int):
    async with db() as conn:
        await delete_journal_entry(conn, entry_id)

@app.get("/journal/analytics")
async def journal_analytics():
    async with db() as conn:
        rows = await get_journal(conn)
    return compute_trade_stats([enrich_trade(r) for r in rows])

@app.get("/journal/export")
async def export_journal():
    from fastapi.responses import StreamingResponse
    import csv, io
    async with db() as conn:
        rows = await get_journal(conn)
    output = io.StringIO()
    fields = ["id", "ticker", "pattern", "entry_date", "exit_date", "entry_price", "exit_price",
              "shares", "stop_price", "pnl", "pnl_pct", "r_multiple", "hold_days", "notes", "tags"]
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for r in rows:
        writer.writerow(enrich_trade(r))
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]), media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=trade_journal.csv"},
    )


# ── Watchlist ─────────────────────────────────────────────────

@app.get("/watchlist", response_model=list[WatchlistSchema])
async def list_watchlist():
    async with db() as conn:
        rows = await get_watchlist(conn)
        today = datetime.now().strftime("%Y-%m-%d")
        scan_tickers = {r["ticker"] for r in await get_scan_setups_for_date(conn, today)}
    return [WatchlistSchema(**{**r, "alert_on_scan": bool(r["alert_on_scan"]),
                               "in_todays_scan": r["ticker"] in scan_tickers}) for r in rows]

@app.post("/watchlist", response_model=WatchlistSchema, status_code=201)
async def add_watchlist(body: WatchlistCreate):
    ticker = body.ticker.upper()
    if not ticker.endswith(".NS"):
        ticker += ".NS"
    async with db() as conn:
        await add_to_watchlist(conn, {"ticker": ticker, "notes": body.notes, "alert_on_scan": int(body.alert_on_scan)})
        rows = await get_watchlist(conn)
        today = datetime.now().strftime("%Y-%m-%d")
        scan_tickers = {r["ticker"] for r in await get_scan_setups_for_date(conn, today)}
    row = next((r for r in rows if r["ticker"] == ticker), rows[0])
    return WatchlistSchema(**{**row, "alert_on_scan": bool(row["alert_on_scan"]),
                              "in_todays_scan": row["ticker"] in scan_tickers})

@app.delete("/watchlist/{ticker}", status_code=204)
async def remove_watchlist(ticker: str):
    if not ticker.endswith(".NS"):
        ticker += ".NS"
    async with db() as conn:
        await remove_from_watchlist(conn, ticker)


# ── Paper Trading ──────────────────────────────────────────────

@app.get("/paper", response_model=list[PaperTradeSchema])
async def list_paper_trades(status: Optional[str] = Query(None)):
    async with db() as conn:
        rows = await get_paper_trades(conn, status)
    enriched = []
    for r in rows:
        t = enrich_trade(r)
        t.setdefault("exit_reason", "")
        t.setdefault("signal_date", "")
        t.setdefault("notes", "")
        enriched.append(PaperTradeSchema(**t))
    return enriched

@app.post("/paper", response_model=PaperTradeSchema, status_code=201)
async def add_paper_trade(body: PaperTradeCreate):
    async with db() as conn:
        new_id = await create_paper_trade(conn, body.model_dump())
        row = await get_paper_trade(conn, new_id)
    t = enrich_trade(dict(row))
    t.setdefault("exit_reason", "")
    t.setdefault("signal_date", "")
    t.setdefault("notes", "")
    return PaperTradeSchema(**t)

@app.put("/paper/{trade_id}", response_model=PaperTradeSchema)
async def edit_paper_trade(trade_id: int, body: PaperTradeUpdate):
    async with db() as conn:
        exists = await get_paper_trade(conn, trade_id)
        if not exists:
            raise HTTPException(status_code=404, detail="Paper trade not found")
        await update_paper_trade(conn, trade_id, body.model_dump(exclude_none=True))
        row = await get_paper_trade(conn, trade_id)
    t = enrich_trade(dict(row))
    t.setdefault("exit_reason", "")
    t.setdefault("signal_date", "")
    t.setdefault("notes", "")
    return PaperTradeSchema(**t)

@app.delete("/paper/{trade_id}", status_code=204)
async def remove_paper_trade(trade_id: int):
    async with db() as conn:
        await delete_paper_trade(conn, trade_id)

@app.get("/paper/stats")
async def paper_trade_stats():
    async with db() as conn:
        rows = await get_paper_trades(conn)
    return compute_trade_stats([enrich_trade(r) for r in rows])

@app.post("/paper/refresh-prices")
async def refresh_paper_prices():
    async with db() as conn:
        open_trades = await get_paper_trades(conn, "open")
        if not open_trades:
            return {"updated": 0}
        tickers = list({t["ticker"] for t in open_trades})
        prices = await fetch_live_prices(tickers)
        updated = 0
        for pt in open_trades:
            price = prices.get(pt["ticker"])
            if price:
                await update_paper_trade_price(conn, pt["id"], price)
                updated += 1
    return {"updated": updated}


# ── Kite Connect ──────────────────────────────────────────────

@app.get("/kite/status")
async def kite_status():
    try:
        from kite_data import status
        return status()
    except ImportError:
        return {"connected": False, "reason": "kiteconnect not installed"}

@app.get("/kite/login-url")
async def kite_login_url():
    try:
        from kite_data import login_url
        return {"url": login_url()}
    except ImportError:
        return {"url": None, "error": "pip install kiteconnect"}

@app.post("/kite/set-token")
async def kite_set_token(request_token: str = Query(...)):
    try:
        from kite_data import set_access_token
        token = set_access_token(request_token)
        return {"access_token": token, "saved_to_env": True}
    except ImportError:
        raise HTTPException(status_code=500, detail="pip install kiteconnect")

@app.get("/kite/instruments/refresh")
async def kite_refresh_instruments():
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
    async with db() as conn:
        return await get_scan_history(conn, limit)


# ── Momentum Leaders ─────────────────────────────────────────

@app.get("/momentum")
async def get_momentum():
    async with db() as conn:
        cached = await get_market_cache(conn, "momentum_leaders")
        if not cached:
            return {"leaders": [], "count": 0, "cached": False}
        data = cached.get("data", {})
        return {"leaders": data.get("leaders", []), "count": data.get("count", 0), "cached": True}


# ── Announcements (disabled) ─────────────────────────────────

@app.get("/announcements")
async def get_announcements(days: int = Query(7, ge=1, le=30)):
    return {"announcements": [], "count": 0, "days": days}


# ── Sector Performance (persistent cache) ────────────────────

SECTOR_INDICES = {
    "IT & Tech": "^CNXIT", "Banking": "^NSEBANK", "Pharma": "^CNXPHARMA",
    "Auto": "^CNXAUTO", "Metals": "^CNXMETAL", "Realty": "^CNXREALTY",
    "Energy": "^CNXENERGY", "Infra": "^CNXINFRA", "FMCG": "^CNXFMCG",
    "Media": "^CNXMEDIA", "PSU Bank": "^CNXPSUBANK", "Midcap": "^NSMIDCP",
}


def compute_sector_performance() -> list[dict]:
    """Compute sector returns — called by scheduler and on-demand."""
    import yfinance as yf
    import numpy as np

    tickers = list(SECTOR_INDICES.values())
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
            price = float(s.iloc[-1])
            sma50 = float(s.rolling(50).mean().iloc[-1]) if len(s) >= 50 else None

            def ret(n):
                return round((price - float(s.iloc[-n - 1])) / float(s.iloc[-n - 1]) * 100, 2) if len(s) > n else None

            r1d, r1w, r1m, r3m = ret(1), ret(5), ret(21), ret(63)
            if r1m is not None and r3m is not None:
                status = "HOT" if r1m > 3 and r3m > 0 else "WARM" if r1m > 0 else "COLD" if r1m > -5 else "WEAK"
            else:
                status = "COLD"

            results.append({
                "sector": name, "ticker": ticker, "price": round(price, 1),
                "sma50": round(sma50, 1) if sma50 else None,
                "above_sma50": bool(sma50 and price > sma50),
                "return_1d": r1d, "return_1w": r1w, "return_1m": r1m, "return_3m": r3m,
                "status": status,
            })
        except Exception:
            continue

    results.sort(key=lambda x: (x.get("return_1m") or -999), reverse=True)
    return results


@app.get("/sectors/performance")
async def sector_performance():
    """Serve from DB cache. If stale (>24h), recompute in background."""
    async with db() as conn:
        cached = await get_market_cache(conn, "sectors")

    if cached:
        # Check if data is from today
        updated = cached.get("updated_at", "")
        today = datetime.now().strftime("%Y-%m-%d")
        if updated[:10] == today:
            data = cached["data"]
            return {"sectors": data, "count": len(data)}

    # Stale or no cache — compute fresh
    loop = asyncio.get_event_loop()
    data = await loop.run_in_executor(executor, compute_sector_performance)

    # Save to DB
    async with db() as conn:
        await set_market_cache(conn, "sectors", data)

    return {"sectors": data, "count": len(data)}


# ── Market Quadrant (persistent cache) ───────────────────────

def compute_market_quadrant() -> dict:
    """Compute Nifty 500 breadth quadrant — called by scheduler and on-demand."""
    try:
        import pytz as _pytz
        from nifty500_universe import get_full_universe
        import yfinance as yf

        tickers = get_full_universe()
        print(f"[Quadrant] Computing breadth for {len(tickers)} tickers...")

        closes = yf.download(tickers, period="1y", auto_adjust=True, progress=False)["Close"]
        closes = closes.dropna(axis=1, how="all")

        n = len(closes.columns)
        if n == 0:
            return {}

        sma10 = closes.rolling(10).mean()
        sma50 = closes.rolling(50).mean()
        sma200 = closes.rolling(200).mean()

        latest = closes.iloc[-1]
        above_10 = int((latest > sma10.iloc[-1]).sum())
        above_50 = int((latest > sma50.iloc[-1]).sum())
        above_200 = int((latest > sma200.iloc[-1]).sum())

        pct10 = round(above_10 / n * 100, 1)
        pct50 = round(above_50 / n * 100, 1)
        pct200 = round(above_200 / n * 100, 1)

        # Net New Highs
        def _nnh(window: int) -> int:
            rh = closes.rolling(window, min_periods=window // 2).max()
            rl = closes.rolling(window, min_periods=window // 2).min()
            return int((latest >= rh.iloc[-1] * 0.99).sum()) - int((latest <= rl.iloc[-1] * 1.01).sum())

        nnh_20 = _nnh(20)
        nnh_65 = _nnh(65)
        nnh_52w = _nnh(252)

        high52 = closes.rolling(252, min_periods=200).max().iloc[-1]
        low52 = closes.rolling(252, min_periods=200).min().iloc[-1]
        new_highs = int((latest >= high52 * 0.99).sum())
        new_lows = int((latest <= low52 * 1.01).sum())

        # Weekly breadth series
        weekly_p50: list[float] = []
        for i in range(13, 0, -1):
            idx = -(i * 5)
            if abs(idx) > len(closes):
                continue
            c = closes.iloc[idx]
            s = sma50.iloc[idx]
            weekly_p50.append(float((c > s).sum() / n * 100))

        if len(weekly_p50) >= 5:
            roc_series = [weekly_p50[i] - weekly_p50[i - 4] for i in range(4, len(weekly_p50))]
            mom_raw = roc_series[-1]
            mom_ma9 = sum(roc_series) / len(roc_series)
            momentum_change = round(mom_raw, 1)
            momentum = "RISING" if mom_raw > mom_ma9 else "FALLING"
        else:
            fallback = float((closes.iloc[-20] > sma50.iloc[-20]).sum() / n * 100)
            momentum_change = round(pct50 - fallback, 1)
            momentum = "RISING" if momentum_change > 0 else "FALLING"

        # Swing Confidence
        sc = min(round(pct10 * 0.40), 40)
        sc += 20 if nnh_20 > 0 else 0
        sc += 20 if nnh_65 > 0 else 0
        sc += 20 if momentum == "RISING" else 0
        swing_confidence = sc

        # Quadrant labels
        bias = "BULL" if pct200 >= 50 else "BEAR"
        trend = "UP" if pct50 >= 50 and nnh_52w > 0 else "DOWN"
        swing = "HOT" if pct10 >= 70 else "WARM" if pct10 >= 50 else "COOL" if pct10 >= 30 else "COLD"

        bulls = sum([bias == "BULL", trend == "UP", pct10 >= 50, momentum == "RISING"])
        overall = "INVEST" if bulls >= 3 else "SELECTIVE" if bulls == 2 else "CASH"

        # Breadth Thrust
        thrust = False
        if pct10 > 40:
            for i in range(2, min(12, len(closes))):
                pp = float((closes.iloc[-i] > sma10.iloc[-i]).sum() / n * 100)
                if pp < 25:
                    thrust = True
                    break

        # Phase duration
        phase_weeks = 0
        max_w = min(52, len(closes) // 5)
        for i in range(1, max_w):
            idx = -(i * 5)
            if abs(idx) >= len(closes):
                break
            c = closes.iloc[idx]
            p10 = float((c > sma10.iloc[idx]).sum() / n * 100)
            p50 = float((c > sma50.iloc[idx]).sum() / n * 100)
            p200 = float((c > sma200.iloc[idx]).sum() / n * 100)
            idx2 = idx - 20
            mom_p = (p50 - float((closes.iloc[idx2] > sma50.iloc[idx2]).sum() / n * 100)
                     if abs(idx2) < len(closes) else 0)
            bulls_p = sum([p200 >= 50, p50 >= 50, p10 >= 50, mom_p > 0])
            ov_p = "INVEST" if bulls_p >= 3 else "SELECTIVE" if bulls_p == 2 else "CASH"
            if ov_p == overall:
                phase_weeks += 1
            else:
                break

        # Upgrade conditions
        to_upgrade: list[dict] = []
        if overall in ("CASH", "SELECTIVE"):
            target = "INVEST" if overall == "SELECTIVE" else "SELECTIVE"
            conditions = []
            if pct10 < 50:
                conditions.append({"metric": "Swing breadth (10-SMA)", "current": pct10, "needs": 50.0, "gap": round(50 - pct10, 1)})
            if momentum == "FALLING":
                conditions.append({"metric": "Momentum", "current": momentum_change, "needs": 0.0, "gap": round(-momentum_change, 1) if momentum_change < 0 else 0})
            if conditions:
                to_upgrade.append({"to": target, "conditions": conditions})

        if overall == "CASH":
            invest_conds = []
            if pct200 < 50:
                invest_conds.append({"metric": "Bias (200-SMA breadth)", "current": pct200, "needs": 50.0, "gap": round(50 - pct200, 1)})
            if pct50 < 50:
                invest_conds.append({"metric": "Trend (50-SMA breadth)", "current": pct50, "needs": 50.0, "gap": round(50 - pct50, 1)})
            if nnh_52w <= 0:
                invest_conds.append({"metric": "52-week Net New Highs", "current": float(nnh_52w), "needs": 1.0, "gap": float(1 - nnh_52w)})
            if invest_conds:
                to_upgrade.append({"to": "INVEST", "conditions": invest_conds})

        result = {
            "bias": bias, "trend": trend, "swing": swing, "momentum": momentum,
            "swing_confidence": swing_confidence, "momentum_change": momentum_change,
            "pct_above_10": pct10, "pct_above_50": pct50, "pct_above_200": pct200,
            "above_10": above_10, "above_50": above_50, "above_200": above_200,
            "total": n,
            "nnh_20": nnh_20, "nnh_65": nnh_65, "nnh_52w": nnh_52w,
            "new_highs": new_highs, "new_lows": new_lows,
            "overall": overall, "phase_weeks": phase_weeks,
            "thrust_detected": thrust, "to_upgrade": to_upgrade,
            "updated_at": datetime.now(_pytz.timezone("Asia/Kolkata")).isoformat(),
        }
        return result

    except Exception as e:
        print(f"[Quadrant] Error: {e}")
        import traceback; traceback.print_exc()
        return {}


@app.post("/market-quadrant/refresh")
async def refresh_market_quadrant():
    """Force recompute and save to DB."""
    loop = asyncio.get_event_loop()
    data = await loop.run_in_executor(executor, compute_market_quadrant)
    if data:
        async with db() as conn:
            await set_market_cache(conn, "quadrant", data)
    return {"refreshed": bool(data)}


@app.get("/market-quadrant")
async def get_market_quadrant():
    """Serve from DB cache. If stale (>24h), recompute."""
    async with db() as conn:
        cached = await get_market_cache(conn, "quadrant")

    if cached:
        updated = cached.get("updated_at", "")
        today = datetime.now().strftime("%Y-%m-%d")
        if updated[:10] == today:
            return cached["data"]

    # Stale or no cache — compute fresh
    loop = asyncio.get_event_loop()
    data = await loop.run_in_executor(executor, compute_market_quadrant)
    if not data:
        raise HTTPException(status_code=503, detail="Could not compute market quadrant")

    async with db() as conn:
        await set_market_cache(conn, "quadrant", data)

    return data

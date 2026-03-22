"""
SQLite persistence layer using aiosqlite.
Stores positions, scan history, journal, paper trades, and cached market data.
"""
from __future__ import annotations
import json
import aiosqlite
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path
from typing import Optional

DB_PATH = Path(__file__).parent / "trading.db"


# ── Schema ────────────────────────────────────────────────────

DDL = """
CREATE TABLE IF NOT EXISTS positions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker       TEXT    NOT NULL,
    pattern      TEXT    NOT NULL,
    entry_price  REAL    NOT NULL,
    stop_price   REAL    NOT NULL,
    current_price REAL,
    shares       INTEGER NOT NULL,
    entry_date   TEXT    NOT NULL,
    exit_price   REAL,
    exit_date    TEXT,
    status       TEXT    DEFAULT 'open',
    notes        TEXT    DEFAULT '',
    created_at   TEXT    DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS scan_results (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_date    TEXT    NOT NULL,
    ticker       TEXT    NOT NULL,
    pattern      TEXT    NOT NULL,
    entry_price  REAL,
    stop_price   REAL,
    risk_pct     REAL,
    volume_ratio REAL,
    raw_json     TEXT,
    created_at   TEXT    DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS scan_runs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_date    TEXT    NOT NULL,
    total_found  INTEGER DEFAULT 0,
    universe_sz  INTEGER DEFAULT 0,
    duration_s   REAL    DEFAULT 0,
    created_at   TEXT    DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS journal (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker       TEXT    NOT NULL,
    pattern      TEXT    NOT NULL DEFAULT '',
    entry_date   TEXT    NOT NULL,
    exit_date    TEXT,
    entry_price  REAL    NOT NULL,
    exit_price   REAL,
    shares       INTEGER NOT NULL DEFAULT 1,
    stop_price   REAL,
    notes        TEXT    DEFAULT '',
    tags         TEXT    DEFAULT '',
    created_at   TEXT    DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS watchlist (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker       TEXT    NOT NULL UNIQUE,
    notes        TEXT    DEFAULT '',
    alert_on_scan INTEGER DEFAULT 1,
    created_at   TEXT    DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS paper_trades (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker        TEXT    NOT NULL,
    pattern       TEXT    NOT NULL DEFAULT '',
    entry_price   REAL    NOT NULL,
    stop_price    REAL    NOT NULL,
    shares        INTEGER NOT NULL DEFAULT 1,
    entry_date    TEXT    NOT NULL,
    signal_date   TEXT    NOT NULL DEFAULT '',
    current_price REAL,
    exit_price    REAL,
    exit_date     TEXT,
    exit_reason   TEXT    DEFAULT '',
    status        TEXT    DEFAULT 'open',
    notes         TEXT    DEFAULT '',
    created_at    TEXT    DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS market_cache (
    key          TEXT    PRIMARY KEY,
    data_json    TEXT    NOT NULL,
    updated_at   TEXT    NOT NULL DEFAULT (datetime('now'))
);
"""


async def init_db(conn: aiosqlite.Connection) -> None:
    for statement in DDL.strip().split(";"):
        stmt = statement.strip()
        if stmt:
            await conn.execute(stmt)
    await conn.commit()


async def get_connection() -> aiosqlite.Connection:
    conn = await aiosqlite.connect(DB_PATH)
    conn.row_factory = aiosqlite.Row
    return conn


@asynccontextmanager
async def db():
    """Async context manager — guarantees connection is closed even on errors."""
    conn = await get_connection()
    try:
        yield conn
    finally:
        await conn.close()


# ── Market Cache (sectors, quadrant — persists across restarts) ──

async def get_market_cache(conn: aiosqlite.Connection, key: str) -> Optional[dict]:
    cur = await conn.execute("SELECT data_json, updated_at FROM market_cache WHERE key = ?", (key,))
    row = await cur.fetchone()
    if not row:
        return None
    return {"data": json.loads(row[0]), "updated_at": row[1]}


async def set_market_cache(conn: aiosqlite.Connection, key: str, data: dict) -> None:
    await conn.execute(
        "INSERT OR REPLACE INTO market_cache (key, data_json, updated_at) VALUES (?, ?, datetime('now'))",
        (key, json.dumps(data)),
    )
    await conn.commit()


# ── Shared Trade Enrichment ──────────────────────────────────

def enrich_trade(t: dict) -> dict:
    """Compute PnL, R-multiple, hold_days for any trade-like dict (journal or paper trade)."""
    entry = t["entry_price"]
    stop = t.get("stop_price")
    shares = t.get("shares", 1)
    ep = t.get("exit_price")
    cur = t.get("current_price")
    risk = (entry - stop) * shares if stop and stop < entry else None

    if ep:
        t["pnl"] = round((ep - entry) * shares, 2)
        t["pnl_pct"] = round((ep - entry) / entry * 100, 2)
        t["r_multiple"] = round(t["pnl"] / risk, 2) if risk and risk > 0 else None
        t["unrealized_pnl"] = None
        t["unrealized_pnl_pct"] = None
        t["status"] = t.get("status", "closed")
    else:
        t["pnl"] = t["pnl_pct"] = t["r_multiple"] = None
        if cur:
            t["unrealized_pnl"] = round((float(cur) - entry) * shares, 2)
            t["unrealized_pnl_pct"] = round((float(cur) - entry) / entry * 100, 2)
        else:
            t["unrealized_pnl"] = t["unrealized_pnl_pct"] = None
        t.setdefault("status", "open")

    if t.get("entry_date") and t.get("exit_date"):
        d1 = date.fromisoformat(t["entry_date"])
        d2 = date.fromisoformat(t["exit_date"])
        t["hold_days"] = (d2 - d1).days
    else:
        t["hold_days"] = None

    return t


def compute_trade_stats(all_trades: list[dict]) -> dict:
    """Shared analytics for journal or paper trades. Expects enriched dicts."""
    closed = [t for t in all_trades if t.get("exit_price")]
    open_ = [t for t in all_trades if not t.get("exit_price")]

    if not closed:
        return {
            "total": len(all_trades), "closed": 0, "open": len(open_),
            "win_rate": 0, "profit_factor": 0, "total_pnl": 0,
            "avg_win": 0, "avg_loss": 0, "avg_r": 0, "best_r": 0,
            "worst_r": 0, "expectancy_r": 0, "avg_hold_days": 0,
            "by_pattern": {}, "monthly": {},
        }

    winners = [t for t in closed if t.get("pnl") and t["pnl"] > 0]
    losers = [t for t in closed if t.get("pnl") and t["pnl"] <= 0]
    rs = [t["r_multiple"] for t in closed if t.get("r_multiple") is not None]
    pnls = [t["pnl"] for t in closed if t.get("pnl") is not None]

    gross_win = sum(t["pnl"] for t in winners)
    gross_loss = abs(sum(t["pnl"] for t in losers)) or 1

    by_pattern: dict = {}
    for t in closed:
        p = t.get("pattern", "UNKNOWN") or "UNKNOWN"
        by_pattern.setdefault(p, {"trades": 0, "wins": 0, "total_pnl": 0.0})
        by_pattern[p]["trades"] += 1
        if t.get("pnl") and t["pnl"] > 0:
            by_pattern[p]["wins"] += 1
        by_pattern[p]["total_pnl"] += t.get("pnl") or 0

    monthly: dict = {}
    for t in closed:
        month = (t.get("exit_date") or "")[:7]
        monthly.setdefault(month, {"trades": 0, "pnl": 0.0})
        monthly[month]["trades"] += 1
        monthly[month]["pnl"] += t.get("pnl") or 0

    hold_days_list = [t["hold_days"] for t in closed if t.get("hold_days") is not None]

    return {
        "total": len(all_trades),
        "closed": len(closed),
        "open": len(open_),
        "win_rate": round(len(winners) / len(closed) * 100, 1),
        "profit_factor": round(gross_win / gross_loss, 2),
        "total_pnl": round(sum(pnls), 2),
        "avg_win": round(gross_win / len(winners), 2) if winners else 0,
        "avg_loss": round(sum(t["pnl"] for t in losers) / len(losers), 2) if losers else 0,
        "avg_r": round(sum(rs) / len(rs), 2) if rs else 0,
        "best_r": round(max(rs), 2) if rs else 0,
        "worst_r": round(min(rs), 2) if rs else 0,
        "expectancy_r": round(sum(rs) / len(rs), 2) if rs else 0,
        "avg_hold_days": round(sum(hold_days_list) / len(hold_days_list), 1) if hold_days_list else 0,
        "by_pattern": by_pattern,
        "monthly": dict(sorted(monthly.items())),
    }


# ── Shared Price Fetcher ─────────────────────────────────────

async def fetch_live_prices(tickers: list[str]) -> dict[str, float]:
    """Fetch latest prices — Kite first, yfinance fallback. Returns {ticker: price}."""
    import asyncio

    prices: dict = {}

    # Try Kite live quotes first
    try:
        from kite_data import get_live_quotes, is_available
        if is_available():
            prices = get_live_quotes(tickers)
    except (ImportError, Exception):
        pass

    if prices:
        return prices

    # yfinance fallback
    loop = asyncio.get_event_loop()

    def _fetch():
        import yfinance as yf
        data = yf.download(tickers, period="1d", auto_adjust=True, progress=False)
        if data.empty:
            return {}
        close = data["Close"]
        if hasattr(close, "columns"):
            return {str(c): float(close[c].dropna().iloc[-1])
                    for c in close.columns if not close[c].dropna().empty}
        return {tickers[0]: float(close.dropna().iloc[-1])}

    return await loop.run_in_executor(None, _fetch)


# ── Positions CRUD ────────────────────────────────────────────

async def get_positions(conn: aiosqlite.Connection, status: Optional[str] = None) -> list[dict]:
    if status:
        cur = await conn.execute(
            "SELECT * FROM positions WHERE status = ? ORDER BY created_at DESC", (status,)
        )
    else:
        cur = await conn.execute("SELECT * FROM positions ORDER BY created_at DESC")
    return [dict(r) for r in await cur.fetchall()]


async def get_position(conn: aiosqlite.Connection, position_id: int) -> Optional[dict]:
    cur = await conn.execute("SELECT * FROM positions WHERE id = ?", (position_id,))
    row = await cur.fetchone()
    return dict(row) if row else None


async def create_position(conn: aiosqlite.Connection, data: dict) -> int:
    cur = await conn.execute(
        """INSERT INTO positions (ticker, pattern, entry_price, stop_price, shares, entry_date, notes)
           VALUES (:ticker, :pattern, :entry_price, :stop_price, :shares, :entry_date, :notes)""",
        data,
    )
    await conn.commit()
    return cur.lastrowid


async def update_position(conn: aiosqlite.Connection, position_id: int, updates: dict) -> bool:
    updates = {k: v for k, v in updates.items() if v is not None}
    if not updates:
        return False
    if "exit_price" in updates and updates.get("status") is None:
        updates["status"] = "closed"
    set_clause = ", ".join(f"{k} = :{k}" for k in updates)
    updates["id"] = position_id
    await conn.execute(f"UPDATE positions SET {set_clause} WHERE id = :id", updates)
    await conn.commit()
    return True


async def delete_position(conn: aiosqlite.Connection, position_id: int) -> bool:
    await conn.execute("DELETE FROM positions WHERE id = ?", (position_id,))
    await conn.commit()
    return True


async def update_position_price(conn: aiosqlite.Connection, position_id: int, price: float) -> None:
    await conn.execute("UPDATE positions SET current_price = ? WHERE id = ?", (price, position_id))
    await conn.commit()


# ── Scan Results ──────────────────────────────────────────────

async def save_scan_results(
    conn: aiosqlite.Connection, scan_date: str, setups: list[dict],
    duration_s: float, universe_sz: int,
) -> None:
    # Clear previous scan results for this date to avoid duplicates
    await conn.execute("DELETE FROM scan_results WHERE scan_date = ?", (scan_date,))
    await conn.execute(
        "INSERT INTO scan_runs (scan_date, total_found, universe_sz, duration_s) VALUES (?, ?, ?, ?)",
        (scan_date, len(setups), universe_sz, duration_s),
    )
    for setup in setups:
        await conn.execute(
            """INSERT INTO scan_results (scan_date, ticker, pattern, entry_price, stop_price, risk_pct, volume_ratio, raw_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (scan_date, setup.get("ticker", ""), setup.get("pattern", ""),
             setup.get("entry_price", 0), setup.get("stop_price", 0),
             setup.get("risk_pct", 0), setup.get("volume_ratio", 0), json.dumps(setup)),
        )
    await conn.commit()


async def get_cached_scan(conn: aiosqlite.Connection, scan_date: str) -> list[dict] | None:
    cur = await conn.execute("SELECT COUNT(*) FROM scan_runs WHERE scan_date = ?", (scan_date,))
    row = await cur.fetchone()
    if not row or row[0] == 0:
        return None
    return await get_scan_setups_for_date(conn, scan_date)


async def get_most_recent_cached_scan(conn: aiosqlite.Connection) -> tuple[str, list[dict]]:
    cur = await conn.execute("SELECT scan_date FROM scan_runs ORDER BY scan_date DESC LIMIT 1")
    row = await cur.fetchone()
    if not row:
        return "", []
    d = row[0]
    return d, await get_scan_setups_for_date(conn, d)


async def get_scan_history(conn: aiosqlite.Connection, limit: int = 30) -> list[dict]:
    cur = await conn.execute("SELECT * FROM scan_runs ORDER BY created_at DESC LIMIT ?", (limit,))
    return [dict(r) for r in await cur.fetchall()]


async def get_scan_setups_for_date(conn: aiosqlite.Connection, scan_date: str) -> list[dict]:
    cur = await conn.execute(
        "SELECT * FROM scan_results WHERE scan_date = ? ORDER BY volume_ratio DESC", (scan_date,),
    )
    results = []
    for r in await cur.fetchall():
        d = dict(r)
        if d.get("raw_json"):
            d.update(json.loads(d["raw_json"]))
        results.append(d)
    return results


# ── Journal CRUD ──────────────────────────────────────────────

async def get_journal(conn: aiosqlite.Connection) -> list[dict]:
    cur = await conn.execute("SELECT * FROM journal ORDER BY entry_date DESC")
    return [dict(r) for r in await cur.fetchall()]

async def get_journal_entry(conn: aiosqlite.Connection, entry_id: int) -> Optional[dict]:
    cur = await conn.execute("SELECT * FROM journal WHERE id = ?", (entry_id,))
    row = await cur.fetchone()
    return dict(row) if row else None

async def create_journal_entry(conn: aiosqlite.Connection, data: dict) -> int:
    cur = await conn.execute(
        """INSERT INTO journal (ticker, pattern, entry_date, exit_date, entry_price, exit_price, shares, stop_price, notes, tags)
           VALUES (:ticker, :pattern, :entry_date, :exit_date, :entry_price, :exit_price, :shares, :stop_price, :notes, :tags)""",
        data,
    )
    await conn.commit()
    return cur.lastrowid

async def update_journal_entry(conn: aiosqlite.Connection, entry_id: int, updates: dict) -> bool:
    updates = {k: v for k, v in updates.items() if v is not None}
    if not updates:
        return False
    set_clause = ", ".join(f"{k} = :{k}" for k in updates)
    updates["id"] = entry_id
    await conn.execute(f"UPDATE journal SET {set_clause} WHERE id = :id", updates)
    await conn.commit()
    return True

async def delete_journal_entry(conn: aiosqlite.Connection, entry_id: int) -> bool:
    await conn.execute("DELETE FROM journal WHERE id = ?", (entry_id,))
    await conn.commit()
    return True


# ── Watchlist CRUD ────────────────────────────────────────────

async def get_watchlist(conn: aiosqlite.Connection) -> list[dict]:
    cur = await conn.execute("SELECT * FROM watchlist ORDER BY created_at DESC")
    return [dict(r) for r in await cur.fetchall()]

async def add_to_watchlist(conn: aiosqlite.Connection, data: dict) -> int:
    cur = await conn.execute(
        "INSERT OR IGNORE INTO watchlist (ticker, notes, alert_on_scan) VALUES (:ticker, :notes, :alert_on_scan)",
        data,
    )
    await conn.commit()
    return cur.lastrowid

async def remove_from_watchlist(conn: aiosqlite.Connection, ticker: str) -> bool:
    await conn.execute("DELETE FROM watchlist WHERE ticker = ?", (ticker,))
    await conn.commit()
    return True

async def get_watchlist_tickers(conn: aiosqlite.Connection) -> list[str]:
    cur = await conn.execute("SELECT ticker FROM watchlist WHERE alert_on_scan = 1")
    return [row[0] for row in await cur.fetchall()]


# ── Paper Trades CRUD ─────────────────────────────────────────

async def get_paper_trades(conn: aiosqlite.Connection, status: Optional[str] = None) -> list[dict]:
    if status:
        cur = await conn.execute(
            "SELECT * FROM paper_trades WHERE status = ? ORDER BY entry_date DESC", (status,)
        )
    else:
        cur = await conn.execute("SELECT * FROM paper_trades ORDER BY entry_date DESC")
    return [dict(r) for r in await cur.fetchall()]

async def get_paper_trade(conn: aiosqlite.Connection, trade_id: int) -> Optional[dict]:
    cur = await conn.execute("SELECT * FROM paper_trades WHERE id = ?", (trade_id,))
    row = await cur.fetchone()
    return dict(row) if row else None

async def create_paper_trade(conn: aiosqlite.Connection, data: dict) -> int:
    cur = await conn.execute(
        """INSERT INTO paper_trades
           (ticker, pattern, entry_price, stop_price, shares, entry_date, signal_date, notes)
           VALUES (:ticker, :pattern, :entry_price, :stop_price, :shares, :entry_date, :signal_date, :notes)""",
        data,
    )
    await conn.commit()
    return cur.lastrowid

async def update_paper_trade(conn: aiosqlite.Connection, trade_id: int, updates: dict) -> bool:
    updates = {k: v for k, v in updates.items() if v is not None}
    if not updates:
        return False
    if "exit_price" in updates:
        updates.setdefault("status", "closed")
    set_clause = ", ".join(f"{k} = :{k}" for k in updates)
    updates["id"] = trade_id
    await conn.execute(f"UPDATE paper_trades SET {set_clause} WHERE id = :id", updates)
    await conn.commit()
    return True

async def delete_paper_trade(conn: aiosqlite.Connection, trade_id: int) -> bool:
    await conn.execute("DELETE FROM paper_trades WHERE id = ?", (trade_id,))
    await conn.commit()
    return True

async def update_paper_trade_price(conn: aiosqlite.Connection, trade_id: int, price: float) -> None:
    await conn.execute("UPDATE paper_trades SET current_price = ? WHERE id = ?", (price, trade_id))
    await conn.commit()

async def get_paper_trades_by_date(conn: aiosqlite.Connection, entry_date: str) -> list[dict]:
    cur = await conn.execute("SELECT * FROM paper_trades WHERE entry_date = ?", (entry_date,))
    return [dict(r) for r in await cur.fetchall()]

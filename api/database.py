"""
SQLite persistence layer using aiosqlite.
Stores open/closed positions and daily scan history.
"""
from __future__ import annotations
import json
import aiosqlite
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


# ── Positions CRUD ────────────────────────────────────────────

async def get_positions(conn: aiosqlite.Connection, status: Optional[str] = None) -> list[dict]:
    if status:
        cur = await conn.execute(
            "SELECT * FROM positions WHERE status = ? ORDER BY created_at DESC", (status,)
        )
    else:
        cur = await conn.execute(
            "SELECT * FROM positions ORDER BY created_at DESC"
        )
    rows = await cur.fetchall()
    return [dict(r) for r in rows]


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

    # Auto-close logic
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


# ── Scan Results ──────────────────────────────────────────────

async def save_scan_results(
    conn: aiosqlite.Connection,
    scan_date: str,
    setups: list[dict],
    duration_s: float,
    universe_sz: int,
) -> None:
    # Record the run
    await conn.execute(
        "INSERT INTO scan_runs (scan_date, total_found, universe_sz, duration_s) VALUES (?, ?, ?, ?)",
        (scan_date, len(setups), universe_sz, duration_s),
    )
    # Record each setup
    for setup in setups:
        await conn.execute(
            """INSERT INTO scan_results (scan_date, ticker, pattern, entry_price, stop_price, risk_pct, volume_ratio, raw_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                scan_date,
                setup.get("ticker", ""),
                setup.get("pattern", ""),
                setup.get("entry_price", 0),
                setup.get("stop_price", 0),
                setup.get("risk_pct", 0),
                setup.get("volume_ratio", 0),
                json.dumps(setup),
            ),
        )
    await conn.commit()


async def get_cached_scan(conn: aiosqlite.Connection, scan_date: str) -> list[dict]:
    """Return today's scan results if they already exist in the DB."""
    cur = await conn.execute(
        "SELECT COUNT(*) FROM scan_runs WHERE scan_date = ?", (scan_date,)
    )
    row = await cur.fetchone()
    if not row or row[0] == 0:
        return []
    return await get_scan_setups_for_date(conn, scan_date)


async def get_most_recent_cached_scan(conn: aiosqlite.Connection) -> tuple[str, list[dict]]:
    """Return the most recently cached scan date + its setups (any date)."""
    cur = await conn.execute(
        "SELECT scan_date FROM scan_runs ORDER BY scan_date DESC LIMIT 1"
    )
    row = await cur.fetchone()
    if not row:
        return "", []
    date = row[0]
    setups = await get_scan_setups_for_date(conn, date)
    return date, setups


async def update_position_price(conn: aiosqlite.Connection, position_id: int, price: float) -> None:
    await conn.execute(
        "UPDATE positions SET current_price = ? WHERE id = ?", (price, position_id)
    )
    await conn.commit()


async def get_scan_history(conn: aiosqlite.Connection, limit: int = 30) -> list[dict]:
    cur = await conn.execute(
        "SELECT * FROM scan_runs ORDER BY created_at DESC LIMIT ?", (limit,)
    )
    rows = await cur.fetchall()
    return [dict(r) for r in rows]


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
    await conn.execute(
        "UPDATE paper_trades SET current_price = ? WHERE id = ?", (price, trade_id)
    )
    await conn.commit()


async def get_paper_trades_by_date(conn: aiosqlite.Connection, entry_date: str) -> list[dict]:
    cur = await conn.execute(
        "SELECT * FROM paper_trades WHERE entry_date = ?", (entry_date,)
    )
    return [dict(r) for r in await cur.fetchall()]


async def get_scan_setups_for_date(conn: aiosqlite.Connection, scan_date: str) -> list[dict]:
    cur = await conn.execute(
        "SELECT * FROM scan_results WHERE scan_date = ? ORDER BY volume_ratio DESC",
        (scan_date,),
    )
    rows = await cur.fetchall()
    results = []
    for r in rows:
        d = dict(r)
        if d.get("raw_json"):
            d.update(json.loads(d["raw_json"]))
        results.append(d)
    return results

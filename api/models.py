from __future__ import annotations
from typing import List, Optional, Union, Literal
from pydantic import BaseModel, Field


# ── Screener / Setup ──────────────────────────────────────────

class SetupSchema(BaseModel):
    ticker: str
    date: str
    pattern: Literal["BREAKOUT", "EP", "VCP", "SA", "EMERGING", "S2HIGH"]
    patterns: str = ""                    # All detected patterns, comma-separated (e.g. "BREAKOUT, S2HIGH")
    entry_price: float
    stop_price: float
    risk_pct: float
    volume_ratio: float
    distance_52w_pct: float
    base_weeks: Union[float, str]
    gap_pct: float
    atr14: float = 0.0
    rs_rank: int = 0
    near_earnings: bool = False
    # Fundamental context (from yfinance / NSE announcements)
    eps_qoq: float = 0.0
    eps_yoy: float = 0.0
    revenue_qoq: float = 0.0
    revenue_yoy: float = 0.0
    has_announcement: bool = False
    strong_catalyst: bool = False
    # Quality grading + regime sizing
    grade: str = ""                    # A/B/C quality grade
    regime_size_pct: float = 1.0       # Regime-aware sizing multiplier (1.0 = full, 0.5 = half)
    # Computed by API layer
    position_size_shares: int = 0
    position_value: float = 0.0
    risk_amount: float = 0.0


class ScanResponse(BaseModel):
    scan_date: str
    setups: List[SetupSchema]
    total_found: int
    universe_size: int
    scan_duration_seconds: float
    cached: bool = False
    stale: bool = False   # True when returning a previous day's scan while today's runs in background


# ── Positions ─────────────────────────────────────────────────

class PositionCreate(BaseModel):
    ticker: str
    pattern: str
    entry_price: float
    stop_price: float
    shares: int
    entry_date: str
    notes: Optional[str] = ""


class PositionUpdate(BaseModel):
    current_price: Optional[float] = None
    stop_price: Optional[float] = None
    exit_price: Optional[float] = None
    exit_date: Optional[str] = None
    status: Optional[Literal["open", "closed"]] = None
    notes: Optional[str] = None


class PositionSchema(BaseModel):
    id: int
    ticker: str
    pattern: str
    entry_price: float
    stop_price: float
    current_price: Optional[float] = None
    shares: int
    entry_date: str
    exit_price: Optional[float] = None
    exit_date: Optional[str] = None
    status: str
    notes: Optional[str] = ""
    unrealized_pnl: Optional[float] = None
    unrealized_pnl_pct: Optional[float] = None
    risk_amount: float = 0.0
    created_at: str


# ── Backtest ──────────────────────────────────────────────────

class BacktestRequest(BaseModel):
    start: str = "2020-01-01"
    end: str = "2024-12-31"
    universe: Literal["nifty500", "momentum", "nifty50", "custom"] = "nifty500"
    tickers: Optional[List[str]] = None
    account_size: float = 1_000_000


class EquityPoint(BaseModel):
    date: str
    value: float


class TradeRecord(BaseModel):
    ticker: str
    pattern: str
    entry_date: str
    exit_date: str
    entry_price: float
    exit_price: float
    exit_reason: str
    shares: int
    pnl: float
    pnl_pct: float
    r_multiple: float
    hold_days: int


class BacktestStats(BaseModel):
    total_trades: int
    winners: int
    losers: int
    win_rate_pct: float
    avg_win_pct: float
    avg_loss_pct: float
    profit_factor: float
    expectancy_r: float
    avg_r: float
    total_pnl_dollars: float
    total_return_pct: float
    cagr_pct: float
    max_drawdown_pct: float
    best_trade_r: float
    worst_trade_r: float
    avg_hold_days: float
    breakout_trades: int = 0
    breakout_win_rate: float = 0.0
    ep_trades: int = 0
    ep_win_rate: float = 0.0


class BacktestResponse(BaseModel):
    stats: BacktestStats
    equity_curve: List[EquityPoint]
    trades: List[TradeRecord]
    run_duration_seconds: float


# ── Journal ───────────────────────────────────────────────────

class JournalCreate(BaseModel):
    ticker: str
    pattern: str = ""
    entry_date: str
    entry_price: float
    shares: int
    stop_price: Optional[float] = None
    exit_date: Optional[str] = None
    exit_price: Optional[float] = None
    notes: str = ""
    tags: str = ""

class JournalUpdate(BaseModel):
    exit_date: Optional[str] = None
    exit_price: Optional[float] = None
    stop_price: Optional[float] = None
    notes: Optional[str] = None
    tags: Optional[str] = None

class JournalSchema(BaseModel):
    id: int
    ticker: str
    pattern: str
    entry_date: str
    entry_price: float
    shares: int
    stop_price: Optional[float] = None
    exit_date: Optional[str] = None
    exit_price: Optional[float] = None
    notes: str = ""
    tags: str = ""
    created_at: str
    # Computed
    pnl: Optional[float] = None
    pnl_pct: Optional[float] = None
    r_multiple: Optional[float] = None
    hold_days: Optional[int] = None
    status: str = "open"


# ── Watchlist ─────────────────────────────────────────────────

class WatchlistCreate(BaseModel):
    ticker: str
    notes: str = ""
    alert_on_scan: bool = True

class WatchlistSchema(BaseModel):
    id: int
    ticker: str
    notes: str = ""
    alert_on_scan: bool = True
    created_at: str
    in_todays_scan: bool = False


# ── Paper Trading ─────────────────────────────────────────────

class PaperTradeCreate(BaseModel):
    ticker: str
    pattern: str
    entry_price: float
    stop_price: float
    shares: int
    entry_date: str
    signal_date: str = ""
    notes: str = ""

class PaperTradeUpdate(BaseModel):
    current_price: Optional[float] = None
    exit_price: Optional[float] = None
    exit_date: Optional[str] = None
    exit_reason: Optional[str] = None
    notes: Optional[str] = None

class PaperTradeSchema(BaseModel):
    id: int
    ticker: str
    pattern: str
    entry_price: float
    stop_price: float
    shares: int
    entry_date: str
    signal_date: str = ""
    current_price: Optional[float] = None
    exit_price: Optional[float] = None
    exit_date: Optional[str] = None
    exit_reason: str = ""
    status: str
    notes: str = ""
    created_at: str
    unrealized_pnl: Optional[float] = None
    unrealized_pnl_pct: Optional[float] = None
    pnl: Optional[float] = None
    pnl_pct: Optional[float] = None
    r_multiple: Optional[float] = None
    hold_days: Optional[int] = None


# ── Health ────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    timestamp: str
    scheduler_running: bool
    db_ok: bool
    market_bullish: bool = True
    regime_note: str = ""
    nifty500_price: Optional[float] = None
    nifty500_sma200: Optional[float] = None
    kite_connected: bool = False
    kite_user: str = ""
    data_source: str = "yfinance"

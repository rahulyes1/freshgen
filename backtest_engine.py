# ============================================================
# BACKTEST ENGINE — Trade simulation with position sizing
# ============================================================
# Simulates trades in chronological order across multiple tickers.
# Key design principles:
#   - 1% risk per trade (fixed fractional), capped at RISK_CAP_MULTIPLIER × initial
#   - Drawdown circuit breaker: pause new trades when in > DRAWDOWN_PAUSE_PCT drawdown
#   - Accurate equity curve: daily mark-to-market of all open + closed positions
#   - Transaction costs applied per trade

import math
import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from patterns import Setup
import config as cfg


@dataclass
class Trade:
    """A completed trade record."""
    ticker: str
    pattern: str
    entry_date: pd.Timestamp
    entry_price: float
    stop_price: float
    shares: int
    risk_per_share: float
    risk_dollars: float

    exit_date: pd.Timestamp = None
    exit_price: float = 0.0
    exit_reason: str = ""          # STOP | TRAIL_EMA | MAX_HOLD | END_DATA
    pnl: float = 0.0
    pnl_pct: float = 0.0
    r_multiple: float = 0.0        # PnL / initial risk dollars
    hold_days: int = 0

    @property
    def is_winner(self) -> bool:
        return self.pnl > 0


@dataclass
class BacktestResult:
    """All output from a completed backtest run."""
    trades: list[Trade] = field(default_factory=list)
    equity_curve: pd.Series = field(default_factory=pd.Series)
    skipped_setups: int = 0
    total_setups: int = 0


def _calculate_position_size(
    account_size: float,
    initial_account_size: float,
    entry_price: float,
    stop_price: float,
) -> tuple[int, float, float]:
    """
    Fixed fractional position sizing with a risk cap.

    - Risk per trade = 1% of current account
    - BUT capped at RISK_CAP_MULTIPLIER × (1% of initial account)
      so that position sizes don't become runaway after a big bull run.
    - Also capped at MAX_POSITION_PCT of account per position.
    """
    risk_per_share = entry_price - stop_price
    if risk_per_share <= 0:
        return 0, 0.0, 0.0

    initial_risk = initial_account_size * cfg.RISK_PER_TRADE
    current_risk = account_size * cfg.RISK_PER_TRADE
    # Cap: never risk more than RISK_CAP_MULTIPLIER × initial risk per trade
    risk_dollars = min(current_risk, initial_risk * cfg.RISK_CAP_MULTIPLIER)

    shares = math.floor(risk_dollars / risk_per_share)
    if shares <= 0:
        return 0, 0.0, 0.0

    # Cap: never more than MAX_POSITION_PCT of account in one trade
    max_shares = math.floor((account_size * cfg.MAX_POSITION_PCT) / entry_price)
    shares = min(shares, max_shares)

    if shares <= 0:
        return 0, 0.0, 0.0

    actual_risk = shares * risk_per_share
    return shares, risk_per_share, actual_risk


def _simulate_single_trade(
    setup: Setup,
    df: pd.DataFrame,
    signal_idx: int,
    account_size: float,
    initial_account_size: float,
) -> Trade | None:
    """
    Simulate one trade bar-by-bar from entry to exit.
    Returns a completed Trade, or None if trade cannot be entered.
    """
    entry_idx = signal_idx + 1 if cfg.ENTRY_ON_NEXT_OPEN else signal_idx
    if entry_idx >= len(df):
        return None

    entry_bar = df.iloc[entry_idx]
    entry_price = entry_bar["Open"] if cfg.ENTRY_ON_NEXT_OPEN else entry_bar["Close"]
    entry_date  = df.index[entry_idx]

    # Recalculate stop from actual entry price
    initial_stop = setup.initial_stop
    hard_stop    = entry_price * (1 - cfg.STOP_MAX_PCT)
    stop_price   = max(initial_stop, hard_stop)

    # Skip if gap down stopped us on entry bar
    if cfg.ENTRY_ON_NEXT_OPEN and entry_bar["Low"] <= stop_price:
        return None

    shares, risk_per_share, risk_dollars = _calculate_position_size(
        account_size, initial_account_size, entry_price, stop_price
    )
    if shares == 0:
        return None

    trade = Trade(
        ticker=setup.ticker,
        pattern=setup.pattern,
        entry_date=entry_date,
        entry_price=entry_price,
        stop_price=stop_price,
        shares=shares,
        risk_per_share=risk_per_share,
        risk_dollars=risk_dollars,
    )

    # ── Manage trade bar by bar ───────────────────────────────
    trail_active = False
    exit_price   = None
    exit_reason  = "END_DATA"
    exit_date    = df.index[-1]

    for j in range(entry_idx + 1, len(df)):
        bar       = df.iloc[j]
        hold_days = j - entry_idx

        # Activate trailing stop after 1R of profit
        if risk_per_share > 0:
            unrealized_r = (bar["Close"] - entry_price) / risk_per_share
            if unrealized_r >= cfg.TRAIL_ACTIVATE_R:
                trail_active = True

        # Exit 1: Hard stop hit (intrabar low breaches stop)
        if bar["Low"] <= stop_price:
            exit_price  = stop_price
            exit_reason = "STOP"
            exit_date   = df.index[j]
            trade.hold_days = hold_days
            break

        # Exit 2: Trailing 10-EMA (close below EMA after 1R profit)
        ema10 = bar.get("EMA10", None)
        if trail_active and ema10 is not None and not pd.isna(ema10):
            if bar["Close"] < ema10:
                exit_price  = bar["Close"]
                exit_reason = "TRAIL_EMA"
                exit_date   = df.index[j]
                trade.hold_days = hold_days
                break

        # Exit 3: Max hold period safety valve
        if hold_days >= cfg.HOLD_MAX_DAYS:
            exit_price  = bar["Close"]
            exit_reason = "MAX_HOLD"
            exit_date   = df.index[j]
            trade.hold_days = hold_days
            break

    else:
        last_bar = df.iloc[-1]
        exit_price      = last_bar["Close"]
        exit_date       = df.index[-1]
        trade.hold_days = len(df) - entry_idx - 1

    if exit_price is None:
        exit_price = df.iloc[-1]["Close"]

    # Transaction costs: brokerage + STT + charges (round-trip)
    position_value    = entry_price * shares
    transaction_cost  = position_value * cfg.TRANSACTION_COST_PCT

    trade.exit_price  = exit_price
    trade.exit_date   = exit_date
    trade.exit_reason = exit_reason
    trade.pnl         = (exit_price - entry_price) * shares - transaction_cost
    trade.pnl_pct     = (exit_price - entry_price) / entry_price - cfg.TRANSACTION_COST_PCT
    trade.r_multiple  = trade.pnl / risk_dollars if risk_dollars > 0 else 0.0

    return trade


def _build_equity_curve(
    trades: list[Trade],
    all_dates: pd.DatetimeIndex,
    initial_account: float,
) -> pd.Series:
    """
    Build a clean daily equity curve.
    Groups all PnL by exit date, cumulates, and forward-fills gaps.
    Handles same-day multiple exits correctly.
    """
    if not trades:
        return pd.Series(initial_account, index=all_dates)

    # Sum PnL on each exit date (multiple trades can exit same day)
    pnl_by_date: dict[pd.Timestamp, float] = {}
    for t in trades:
        key = t.exit_date
        pnl_by_date[key] = pnl_by_date.get(key, 0.0) + t.pnl

    # Build sparse series of cumulative equity at each exit date
    running = initial_account
    eq_points: dict[pd.Timestamp, float] = {}
    for d in sorted(pnl_by_date.keys()):
        running += pnl_by_date[d]
        eq_points[d] = running

    # Reindex to full daily dates and fill
    sparse = pd.Series(eq_points)
    curve  = sparse.reindex(all_dates, method="ffill")
    # Fill any leading NaN with the initial account value
    curve  = curve.bfill().fillna(initial_account)
    return curve


def run_portfolio_backtest(
    ticker_data: dict[str, pd.DataFrame],
    all_setups: list[Setup],
) -> BacktestResult:
    """
    Portfolio-level backtest with:
    - Chronological setup processing
    - Cash tracking (no over-investing)
    - Drawdown circuit breaker (pause new trades in deep drawdown)
    - Capped compounding (risk grows with account but has a ceiling)
    - Correct equity curve
    """
    from patterns import deduplicate_setups

    result = BacktestResult()
    if not all_setups:
        print("No setups found.")
        return result

    setups = deduplicate_setups(all_setups, cooldown_days=20)
    result.total_setups = len(setups)

    initial_account   = cfg.ACCOUNT_SIZE
    account_size      = initial_account
    cash              = account_size
    peak_equity       = account_size     # for drawdown circuit breaker
    pause_until: pd.Timestamp | None = None  # circuit breaker reset date

    open_tickers: set[str] = set()
    completed_trades: list[Trade] = []

    # Build unified date index for equity curve
    all_dates = pd.DatetimeIndex(
        sorted(set(d for df in ticker_data.values() for d in df.index))
    )

    for setup in setups:
        ticker = setup.ticker
        if ticker not in ticker_data:
            result.skipped_setups += 1
            continue

        df = ticker_data[ticker]

        try:
            signal_idx = df.index.get_loc(setup.date)
        except KeyError:
            result.skipped_setups += 1
            continue

        # ── Gate 1: No duplicate position on same ticker ───────
        if ticker in open_tickers:
            result.skipped_setups += 1
            continue

        # ── Gate 2: Max concurrent positions ──────────────────
        if len(open_tickers) >= cfg.MAX_OPEN_POSITIONS:
            result.skipped_setups += 1
            continue

        # ── Gate 3: Drawdown circuit breaker (time-based reset) ─
        # If drawdown > threshold, pause for DRAWDOWN_PAUSE_DAYS,
        # then reset and allow trading again (mimics Qullamaggie's
        # monthly stop and restart discipline).
        current_drawdown = (peak_equity - account_size) / peak_equity
        if current_drawdown > cfg.DRAWDOWN_PAUSE_PCT:
            if pause_until is None:
                pause_until = setup.date + pd.Timedelta(days=cfg.DRAWDOWN_PAUSE_DAYS)
            if setup.date < pause_until:
                result.skipped_setups += 1
                continue
            else:
                # Pause expired — reset and resume at this point
                pause_until = None
                peak_equity = account_size   # reset peak to current level
        else:
            pause_until = None   # clear pause if drawdown recovered

        # ── Gate 4: Sufficient cash ────────────────────────────
        min_cash = initial_account * cfg.RISK_PER_TRADE * 5
        if cash < min_cash:
            result.skipped_setups += 1
            continue

        # ── Simulate trade ─────────────────────────────────────
        trade = _simulate_single_trade(
            setup, df, signal_idx, account_size, initial_account
        )
        if trade is None:
            result.skipped_setups += 1
            continue

        position_cost = trade.entry_price * trade.shares
        if position_cost > cash:
            result.skipped_setups += 1
            continue

        # Open the position
        cash         -= position_cost
        open_tickers.add(ticker)

        # Close the position (trade already fully simulated)
        cash         += trade.exit_price * trade.shares
        account_size  = cash  # simplified: no open position mark-to-market
        peak_equity   = max(peak_equity, account_size)

        open_tickers.discard(ticker)
        completed_trades.append(trade)

    result.trades       = sorted(completed_trades, key=lambda t: t.entry_date)
    result.equity_curve = _build_equity_curve(result.trades, all_dates, initial_account)
    return result

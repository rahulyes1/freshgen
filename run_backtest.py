#!/usr/bin/env python3
# ============================================================
# RUN BACKTEST — Main entry point for backtesting
# ============================================================
# Usage:
#   python run_backtest.py                          # Nifty 500 momentum universe
#   python run_backtest.py --universe nifty500      # Full Nifty 500
#   python run_backtest.py --universe momentum      # Curated ~200 high-growth stocks
#   python run_backtest.py --universe us            # US market watchlist
#   python run_backtest.py --tickers RELIANCE.NS TCS.NS INFY.NS
#   python run_backtest.py --start 2021-01-01 --end 2024-12-31
#   python run_backtest.py --account 500000         # Rs. 5 lakh account
#   python run_backtest.py --refresh                # Re-download all data
#
# Results saved to: output/

import argparse
import sys
import os
import pandas as pd

import config as cfg
from data_manager import get_multiple_tickers
from indicators import add_all_indicators
from patterns import find_all_setups, deduplicate_setups
from backtest_engine import run_portfolio_backtest
from reporter import generate_report
from nifty500_universe import get_nifty500, get_momentum_universe


def parse_args():
    parser = argparse.ArgumentParser(
        description="Qullamaggie-style swing trading backtest — Nifty 500 / US"
    )
    parser.add_argument(
        "--tickers", nargs="+", default=None,
        help="Specific tickers to test (e.g. RELIANCE.NS TCS.NS)"
    )
    parser.add_argument(
        "--universe",
        choices=["nifty500", "momentum", "us"],
        default="momentum",
        help="Universe to backtest: nifty500 (all 500), momentum (curated ~200), us (US watchlist). Default: momentum"
    )
    parser.add_argument(
        "--start", default=cfg.DEFAULT_START,
        help=f"Start date YYYY-MM-DD (default: {cfg.DEFAULT_START})"
    )
    parser.add_argument(
        "--end", default=cfg.DEFAULT_END,
        help=f"End date YYYY-MM-DD (default: {cfg.DEFAULT_END})"
    )
    parser.add_argument(
        "--account", type=float, default=None,
        help="Starting account size (e.g. 1000000 for Rs. 10 lakh)"
    )
    parser.add_argument(
        "--refresh", action="store_true",
        help="Force re-download of all data (ignore cache)"
    )
    return parser.parse_args()


def resolve_tickers(args) -> list[str]:
    """Determine the ticker list based on CLI args."""
    if args.tickers:
        return args.tickers

    if args.universe == "nifty500":
        tickers = get_nifty500()
        print(f"  Universe: Full Nifty 500 ({len(tickers)} tickers)")
    elif args.universe == "momentum":
        tickers = get_momentum_universe()
        print(f"  Universe: Momentum / Nifty Next 50 + Midcap leaders ({len(tickers)} tickers)")
    elif args.universe == "us":
        tickers = cfg.US_WATCHLIST
        print(f"  Universe: US watchlist ({len(tickers)} tickers)")
    else:
        tickers = cfg.DEFAULT_WATCHLIST

    return tickers


def main():
    args = parse_args()

    if args.account:
        cfg.ACCOUNT_SIZE = args.account

    tickers = resolve_tickers(args)
    start   = args.start
    end     = args.end

    os.makedirs(cfg.OUTPUT_DIR, exist_ok=True)
    os.makedirs(cfg.CACHE_DIR, exist_ok=True)

    print(f"\n{'='*60}")
    print(f"  QULLAMAGGIE SWING TRADING - NIFTY 500 BACKTEST")
    print(f"{'='*60}")
    print(f"  Market:     {'NSE India' if cfg.MARKET == 'IN' else 'US'}")
    print(f"  Tickers:    {len(tickers)}")
    print(f"  Period:     {start} to {end}")
    print(f"  Account:    {cfg.CURRENCY_SYMBOL}{cfg.ACCOUNT_SIZE:,.0f}")
    print(f"  Risk/Trade: {cfg.RISK_PER_TRADE*100:.1f}%  "
          f"({cfg.CURRENCY_SYMBOL}{cfg.ACCOUNT_SIZE * cfg.RISK_PER_TRADE:,.0f} per trade)")
    print(f"  Max Trades: {cfg.MAX_OPEN_POSITIONS} simultaneous")
    print(f"{'='*60}\n")

    # ── Step 1: Download Data ──────────────────────────────────
    print("Step 1/4: Downloading market data (using cache where available)...\n")
    ticker_data = get_multiple_tickers(
        tickers, start=start, end=end,
        force_download=args.refresh
    )

    if not ticker_data:
        print("ERROR: No data downloaded. Check tickers and internet connection.")
        sys.exit(1)

    print(f"\n  {len(ticker_data)} tickers loaded successfully.\n")

    # ── Step 2: Indicators + Pattern Detection ────────────────
    print("Step 2/4: Computing indicators and scanning for setups...\n")
    all_setups = []
    tickers_with_setups = 0

    for ticker, df in ticker_data.items():
        df_ind = add_all_indicators(df, cfg)
        ticker_data[ticker] = df_ind
        setups = find_all_setups(df_ind, ticker)
        if setups:
            tickers_with_setups += 1
            print(f"  {ticker:<20} {len(setups):>3} setup(s)  "
                  f"[B:{sum(1 for s in setups if s.pattern=='BREAKOUT')}  "
                  f"EP:{sum(1 for s in setups if s.pattern=='EP')}]")
        all_setups.extend(setups)

    all_setups_before = len(all_setups)
    all_setups = deduplicate_setups(all_setups, cooldown_days=20)

    print(f"\n  Tickers with setups:  {tickers_with_setups}")
    print(f"  Raw setups found:     {all_setups_before}")
    print(f"  After deduplication:  {len(all_setups)}\n")

    if not all_setups:
        print("No setups found. Try broadening parameters in config.py or a longer date range.")
        sys.exit(0)

    # ── Step 3: Backtest Simulation ───────────────────────────
    print("Step 3/4: Running backtest simulation...\n")
    result = run_portfolio_backtest(ticker_data, all_setups)

    print(f"  Setups processed: {result.total_setups}")
    print(f"  Setups skipped:   {result.skipped_setups}  "
          f"(no cash / position limit / position could not open)")
    print(f"  Trades completed: {len(result.trades)}\n")

    if not result.trades:
        print("No trades completed. Try adjusting parameters.")
        sys.exit(0)

    # ── Step 4: Report ─────────────────────────────────────────
    print("Step 4/4: Generating reports...\n")
    generate_report(result.trades, result.equity_curve, cfg.OUTPUT_DIR)

    print(f"\n  Output saved to: {os.path.abspath(cfg.OUTPUT_DIR)}/")
    print("  Done.\n")


if __name__ == "__main__":
    main()

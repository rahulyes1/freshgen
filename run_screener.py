#!/usr/bin/env python3
# ============================================================
# RUN SCREENER — Daily live screening for active setups
# ============================================================
# Run each morning 9:00-9:15 AM IST before market open.
# Usage:
#   python run_screener.py                      # Nifty 500 momentum universe
#   python run_screener.py --universe nifty500  # Full Nifty 500
#   python run_screener.py --tickers RELIANCE.NS TCS.NS
#   python run_screener.py --watchlist tickers.txt
#
# Output: console table + output/screener_YYYY-MM-DD.csv

import argparse
import os
import sys
import pandas as pd

import config as cfg
from screener import run_screener, print_screener_results
from nifty500_universe import get_nifty500, get_momentum_universe


def parse_args():
    parser = argparse.ArgumentParser(
        description="Qullamaggie-style daily screener — Nifty 500 / US"
    )
    parser.add_argument(
        "--tickers", nargs="+", default=None,
        help="Specific tickers to screen (e.g. RELIANCE.NS TCS.NS)"
    )
    parser.add_argument(
        "--universe",
        choices=["nifty500", "momentum", "us"],
        default="momentum",
        help="Universe: nifty500 | momentum (default) | us"
    )
    parser.add_argument(
        "--watchlist", default=None,
        help="Path to a text file with one ticker per line"
    )
    parser.add_argument(
        "--lookback", type=int, default=350,
        help="Days of history to download (default: 350)"
    )
    parser.add_argument(
        "--fresh", type=int, default=5,
        help="How many recent bars to consider 'fresh' (default: 5)"
    )
    return parser.parse_args()


def load_watchlist(path: str) -> list[str]:
    """Load tickers from a text file (one per line, ignore blank lines and # comments)."""
    if not os.path.exists(path):
        print(f"ERROR: Watchlist file not found: {path}")
        sys.exit(1)
    tickers = []
    with open(path) as f:
        for line in f:
            t = line.strip().upper()
            if t and not t.startswith("#"):
                tickers.append(t)
    return tickers


def main():
    args = parse_args()
    os.makedirs(cfg.OUTPUT_DIR, exist_ok=True)

    # Determine ticker list
    if args.tickers:
        tickers = [t.upper() for t in args.tickers]
    elif args.watchlist:
        tickers = load_watchlist(args.watchlist)
    elif args.universe == "nifty500":
        tickers = get_nifty500()
    elif args.universe == "momentum":
        tickers = get_momentum_universe()
    elif args.universe == "us":
        tickers = cfg.US_WATCHLIST
    else:
        tickers = cfg.DEFAULT_WATCHLIST

    print(f"\n{'='*55}")
    print(f"  QULLAMAGGIE SCREENER")
    print(f"  Date: {pd.Timestamp.today().strftime('%Y-%m-%d')}")
    print(f"  Screening {len(tickers)} tickers...")
    print(f"{'='*55}\n")

    setups = run_screener(tickers, lookback_days=args.lookback, fresh_bars=args.fresh)

    print_screener_results(setups)

    if not setups.empty:
        date_str = pd.Timestamp.today().strftime("%Y-%m-%d")
        out_path = os.path.join(cfg.OUTPUT_DIR, f"screener_{date_str}.csv")
        setups.to_csv(out_path, index=False)
        print(f"  Saved to: {out_path}\n")


if __name__ == "__main__":
    main()

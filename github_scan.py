#!/usr/bin/env python3
"""
GitHub Actions scanner — runs daily at 9:00 AM and 3:45 PM IST.
No database, no FastAPI — just scan + Telegram.
"""
import os
import sys
import asyncio
from datetime import datetime

# Ensure we can import from the repo root
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

import config as cfg
from screener import run_screener
from nifty500_universe import get_nifty500
from telegram_alerts import send_daily_digest, send_message, _escape


def _run_time_label() -> str:
    """Return 'Morning' or 'Close' based on UTC hour."""
    utc_hour = datetime.utcnow().hour
    # 3:30 AM UTC = 9:00 AM IST → morning scan
    # 10:15 AM UTC = 3:45 PM IST → close scan
    return "Morning" if utc_hour < 7 else "Close"


async def main():
    label = _run_time_label()
    date_str = datetime.now().strftime("%Y-%m-%d")
    print(f"[{date_str}] {label} scan starting — Nifty 500 universe")

    tickers = get_nifty500()
    print(f"  Universe: {len(tickers)} tickers")

    df = run_screener(tickers, lookback_days=350, fresh_bars=5)
    setups = df.to_dict(orient="records") if not df.empty else []
    print(f"  Setups found: {len(setups)}")

    # Add scan label to the digest header
    if setups:
        header_note = f"\n_\\({_escape(label)} scan \\| Nifty 500\\)_\n"
    else:
        header_note = f"\n_\\({_escape(label)} scan \\| Nifty 500\\)_"

    await send_daily_digest(setups, cfg.ACCOUNT_SIZE)
    print("  Telegram sent.")


if __name__ == "__main__":
    asyncio.run(main())

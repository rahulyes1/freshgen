"""
Telegram alerts for the Qullamaggie scanner.

Setup:
  1. Create a bot via @BotFather → get BOT_TOKEN
  2. Send any message to your bot, then visit:
     https://api.telegram.org/bot<TOKEN>/getUpdates
     to find your CHAT_ID
  3. Add to .env:
       TELEGRAM_BOT_TOKEN=123456:ABC...
       TELEGRAM_CHAT_ID=987654321

Usage:
  python telegram_alerts.py --test        # send a test message
  python telegram_alerts.py --scan        # run screener and send results
"""
from __future__ import annotations

import os
import re
import asyncio
import argparse
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID", "")


def _escape(text: str) -> str:
    """Escape special characters for Telegram MarkdownV2."""
    special = r"_*[]()~`>#+-=|{}.!\\"
    return re.sub(r"([" + re.escape(special) + r"])", r"\\\1", str(text))


def format_setup(setup: dict, account_size: float = 1_000_000) -> str:
    """Format one setup as a clean Telegram MarkdownV2 message."""
    pattern_emoji = "\U0001f680" if setup.get("pattern") == "EP" else "\U0001f4c8"  # 🚀 or 📈
    ticker   = _escape(setup.get("ticker", "").replace(".NS", ""))
    pattern  = _escape(setup.get("pattern", ""))
    date_str = _escape(setup.get("date", ""))
    entry    = float(setup.get("entry_price", 0))
    stop     = float(setup.get("stop_price", 0))
    risk_pct = float(setup.get("risk_pct", 0))
    vol_r    = float(setup.get("volume_ratio", 0))
    d52w     = float(setup.get("distance_52w_pct", 0))

    risk_per_share = entry - stop
    position_risk  = account_size * 0.01  # 1%
    shares = int(position_risk / risk_per_share) if risk_per_share > 0 else 0
    pos_val = shares * entry

    lines = [
        f"{pattern_emoji} *{ticker}* \\— {pattern}",
        f"Date: {date_str}",
        f"Entry: `Rs\\.{_escape(f'{entry:.2f}')}`   Stop: `Rs\\.{_escape(f'{stop:.2f}')}`",
        f"Risk: `{_escape(f'{risk_pct:.1f}')}%`   Volume: `{_escape(f'{vol_r:.1f}')}x`",
        f"52W dist: `{_escape(f'{d52w:.1f}')}%`",
        f"Sizing \\(1% risk\\): `{shares} shares` \\= `Rs\\.{_escape(f'{pos_val:,.0f}')}`",
    ]

    extra = []
    if setup.get("pattern") == "EP" and setup.get("gap_pct", 0):
        gap_str = _escape(f'{float(setup["gap_pct"]):.1f}')
        extra.append(f"Gap: `\\+{gap_str}%`")
    if setup.get("pattern") == "BREAKOUT" and setup.get("base_weeks") not in ("-", "", None):
        extra.append(f"Base: `{_escape(str(setup['base_weeks']))}w`")
    if extra:
        lines.append("   ".join(extra))

    return "\n".join(lines)


def format_daily_digest(setups: list[dict], account_size: float = 1_000_000) -> str:
    """Format all setups as one digest header + individual blocks."""
    now  = datetime.now().strftime("%d %b %Y  %H:%M IST")
    date = datetime.now().strftime("%Y-%m-%d")

    if not setups:
        return (
            f"\U0001f4ca *Qullamaggie Scanner \\— {_escape(date)}*\n"
            f"_{_escape(now)}_\n\n"
            "No setups found today\\. Market may be in consolidation\\."
        )

    header = (
        f"\U0001f4ca *Qullamaggie Scanner \\— {_escape(date)}*\n"
        f"_{_escape(now)}_\n"
        f"{_escape(str(len(setups)))} setup\\(s\\) found\n"
    )

    breakouts = [s for s in setups if s.get("pattern") == "BREAKOUT"]
    eps       = [s for s in setups if s.get("pattern") == "EP"]

    blocks = []
    if eps:
        blocks.append(f"*\\-\\-\\- Episodic Pivots \\({_escape(str(len(eps)))}\\) \\-\\-\\-*")
        blocks.extend(format_setup(s, account_size) for s in eps)
    if breakouts:
        blocks.append(f"*\\-\\-\\- Breakouts \\({_escape(str(len(breakouts)))}\\) \\-\\-\\-*")
        blocks.extend(format_setup(s, account_size) for s in breakouts)

    return header + "\n\n".join(blocks)


async def send_message(text: str) -> bool:
    """Send a Telegram message. Returns True on success."""
    if not BOT_TOKEN or not CHAT_ID:
        print("  [Telegram] BOT_TOKEN or CHAT_ID not set — skipping send.")
        return False
    try:
        from telegram import Bot
        bot = Bot(token=BOT_TOKEN)
        # Split if over 4096 char limit
        if len(text) <= 4096:
            await bot.send_message(chat_id=CHAT_ID, text=text, parse_mode="MarkdownV2")
        else:
            # Send in chunks
            chunks = [text[i:i+4000] for i in range(0, len(text), 4000)]
            for chunk in chunks:
                await bot.send_message(chat_id=CHAT_ID, text=chunk, parse_mode="MarkdownV2")
        print(f"  [Telegram] Sent successfully to chat {CHAT_ID}")
        return True
    except Exception as e:
        print(f"  [Telegram] Error: {e}")
        return False


async def send_daily_digest(setups: list[dict], account_size: float = 1_000_000) -> None:
    text = format_daily_digest(setups, account_size)
    await send_message(text)


async def send_test_message() -> None:
    text = (
        "\U0001f9ea *Qullamaggie Scanner \\— Test Message*\n\n"
        "If you see this, Telegram alerts are working correctly\\!\n\n"
        "Sample setup:\n\n"
        + format_setup({
            "ticker": "HAL.NS",
            "pattern": "BREAKOUT",
            "date": datetime.now().strftime("%Y-%m-%d"),
            "entry_price": 4250.0,
            "stop_price": 3910.0,
            "risk_pct": 8.0,
            "volume_ratio": 2.3,
            "distance_52w_pct": 5.2,
            "base_weeks": 5.0,
            "gap_pct": 0,
        })
    )
    await send_message(text)


# ── CLI ───────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

    parser = argparse.ArgumentParser(description="Telegram alerts for Qullamaggie scanner")
    parser.add_argument("--test", action="store_true", help="Send test message")
    parser.add_argument("--scan", action="store_true", help="Run screener and send results")
    args = parser.parse_args()

    if args.test:
        asyncio.run(send_test_message())
    elif args.scan:
        import config as cfg
        from screener import run_screener
        print("Running screener...")
        df = run_screener(cfg.DEFAULT_WATCHLIST)
        setups = df.to_dict(orient="records") if not df.empty else []
        print(f"Found {len(setups)} setups. Sending to Telegram...")
        asyncio.run(send_daily_digest(setups, cfg.ACCOUNT_SIZE))
    else:
        parser.print_help()

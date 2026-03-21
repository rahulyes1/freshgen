"""
kite_auth.py — Fully automated Zerodha Kite login for fresh gen.

Flow (zero manual steps):
  1. Playwright headless Chromium opens Kite login page
  2. Fills User ID + Password
  3. Generates TOTP via pyotp (from KITE_TOTP_SECRET in .env)
  4. Submits → captures request_token from redirect URL
  5. Exchanges for access_token via KiteConnect SDK
  6. Writes access_token to .env (so kite_data.py picks it up instantly)
  7. Sends Telegram confirmation / failure alert

Ported from Gen99 auth/auth.py — all Supabase/Gen99 dependencies removed.
Uses fresh gen's .env + SQLite + telegram_alerts.

Run standalone to test:
  python kite_auth.py

Scheduled automatically at 8:00 AM IST Mon–Fri by api/scheduler.py.
"""
from __future__ import annotations

import re
import os
import time
import asyncio
from datetime import datetime
from pathlib import Path

# Load .env before anything else
from dotenv import load_dotenv
load_dotenv()

KITE_API_KEY    = os.getenv("KITE_API_KEY", "")
KITE_API_SECRET = os.getenv("KITE_API_SECRET", "")
KITE_USER_ID    = os.getenv("KITE_USER_ID", "")
KITE_PASSWORD   = os.getenv("KITE_PASSWORD", "")
KITE_TOTP_SECRET = os.getenv("KITE_TOTP_SECRET", "")

_ENV_PATH = Path(__file__).parent / ".env"
_LOGIN_URL = "https://kite.zerodha.com/connect/login?api_key={api_key}&v=3"
_TOKEN_RE  = re.compile(r"request_token=([A-Za-z0-9]+)")


# ── Headless Playwright login ──────────────────────────────────

async def _playwright_login() -> str:
    """
    Open Kite in headless Chromium, fill credentials + TOTP,
    and return the request_token captured from the redirect URL.
    """
    import pyotp
    from playwright.async_api import async_playwright, TimeoutError as PWTimeout

    login_url = _LOGIN_URL.format(api_key=KITE_API_KEY)
    totp_gen  = pyotp.TOTP(KITE_TOTP_SECRET)
    captured: list[str] = []

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        page    = await browser.new_page()

        # Intercept ALL outgoing requests — the redirect URL is in a request,
        # not a page load (headless Chrome can't load the redirect target).
        page.on("request", lambda req: captured.append(req.url)
                if "request_token=" in req.url else None)

        print(f"[KiteAuth] Opening login page...")
        await page.goto(login_url, wait_until="networkidle")

        # ── Step 1: User ID + Password ─────────────────────────
        await page.wait_for_selector("input#userid", timeout=10_000)
        await page.fill("input#userid", KITE_USER_ID)
        await page.fill('input[type="password"]', KITE_PASSWORD)
        await page.click('button[type="submit"]')
        await page.wait_for_timeout(3000)

        # ── Step 2: TOTP ───────────────────────────────────────
        # Try clicking "Problem with Mobile App Code?" link first
        try:
            link = await page.wait_for_selector(
                'a:has-text("Problem with Mobile App Code")', timeout=5_000
            )
            await link.click()
            await page.wait_for_timeout(1500)
            print("[KiteAuth] Switched to TOTP mode")
        except PWTimeout:
            print("[KiteAuth] TOTP input directly available")

        # Wait for the 6-digit input
        try:
            await page.wait_for_selector('input[maxlength="6"]', timeout=8_000)
        except PWTimeout:
            await page.wait_for_selector('input[id="pin"]', timeout=5_000)

        # Guard: wait if TOTP window expires within 5 seconds
        secs_left = 30 - (int(time.time()) % 30)
        if secs_left < 5:
            print(f"[KiteAuth] TOTP window expires in {secs_left}s — waiting...")
            await page.wait_for_timeout((secs_left + 1) * 1000)

        otp = totp_gen.now()
        print(f"[KiteAuth] Generated TOTP: {otp[:2]}****")

        totp_input = (
            await page.query_selector('input[maxlength="6"]') or
            await page.query_selector('input[id="pin"]')
        )
        if totp_input:
            await totp_input.click()
            await totp_input.type(otp)
        else:
            await page.keyboard.type(otp)

        # Kite auto-submits on TOTP fill; give it a second, then check for submit btn
        await page.wait_for_timeout(1000)
        try:
            btn = await page.query_selector('button[type="submit"]')
            if btn and not await btn.get_attribute("disabled"):
                await btn.click()
        except Exception:
            pass  # already navigated

        # Wait up to 15 s for redirect to be captured
        for _ in range(30):
            if captured:
                break
            await page.wait_for_timeout(500)

        await browser.close()

    if not captured:
        raise RuntimeError("Kite login timed out — request_token not captured. Check credentials.")

    match = _TOKEN_RE.search(captured[0])
    if not match:
        raise ValueError(f"request_token missing in redirect URL: {captured[0][:100]}")

    return match.group(1)


# ── Token exchange ──────────────────────────────────────────────

def _exchange_token(request_token: str) -> dict:
    """Exchange request_token → access_token via Kite SDK."""
    from kiteconnect import KiteConnect
    kite    = KiteConnect(api_key=KITE_API_KEY)
    session = kite.generate_session(request_token, api_secret=KITE_API_SECRET)
    return session


# ── Persist token ───────────────────────────────────────────────

def _save_token_to_env(access_token: str) -> None:
    """Write KITE_ACCESS_TOKEN into .env so kite_data.py picks it up on next call."""
    if not _ENV_PATH.exists():
        return
    lines  = _ENV_PATH.read_text(encoding="utf-8").splitlines()
    found  = False
    result = []
    for line in lines:
        if line.startswith("KITE_ACCESS_TOKEN="):
            result.append(f"KITE_ACCESS_TOKEN={access_token}")
            found = True
        else:
            result.append(line)
    if not found:
        result.append(f"KITE_ACCESS_TOKEN={access_token}")
    _ENV_PATH.write_text("\n".join(result) + "\n", encoding="utf-8")

    # Also update the running process environment so kite_data._kite resets
    os.environ["KITE_ACCESS_TOKEN"] = access_token

    # Reset the cached kite instance so it picks up the new token
    try:
        import kite_data
        kite_data._kite = None
    except ImportError:
        pass


async def _save_token_to_db(access_token: str, user_name: str) -> None:
    """Record the daily login in SQLite (kite_logins table) for audit trail."""
    try:
        import aiosqlite
        from api.database import DB_PATH
        async with aiosqlite.connect(DB_PATH) as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS kite_logins (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    login_date   TEXT NOT NULL,
                    user_name    TEXT,
                    token_prefix TEXT,
                    success      INTEGER DEFAULT 1,
                    created_at   TEXT DEFAULT (datetime('now'))
                )
            """)
            await conn.execute(
                "INSERT INTO kite_logins (login_date, user_name, token_prefix) VALUES (?, ?, ?)",
                (datetime.now().strftime("%Y-%m-%d"), user_name, access_token[:8] + "..."),
            )
            await conn.commit()
    except Exception as e:
        print(f"[KiteAuth] DB log failed (non-fatal): {e}")


# ── Telegram alert ──────────────────────────────────────────────

def _telegram(msg: str) -> None:
    """Non-blocking Telegram send — best effort."""
    try:
        import asyncio
        from telegram_alerts import send_message
        asyncio.run(send_message(msg))
    except Exception as e:
        print(f"[KiteAuth] Telegram alert failed: {e}")


# ── Main entry point ────────────────────────────────────────────

async def refresh_kite_token() -> str:
    """
    Full automated Kite auth flow. Returns the new access_token.
    Called by the scheduler at 8:00 AM IST every weekday.
    """
    now = datetime.now().strftime("%H:%M:%S")
    print(f"[KiteAuth] Starting automated login at {now} IST...")

    if not all([KITE_API_KEY, KITE_API_SECRET, KITE_USER_ID, KITE_PASSWORD, KITE_TOTP_SECRET]):
        msg = "[KiteAuth] Missing Kite credentials in .env — skipping auto-login"
        print(msg)
        return ""

    try:
        request_token = await _playwright_login()
        session       = _exchange_token(request_token)
        access_token  = session["access_token"]
        user_name     = session.get("user_name", KITE_USER_ID)

        _save_token_to_env(access_token)
        await _save_token_to_db(access_token, user_name)

        print(f"[KiteAuth] ✅ Login successful — {user_name} — token: {access_token[:8]}...")
        _telegram(
            f"✅ *Kite Login OK*\n"
            f"User: *{user_name}*\n"
            f"Time: `{now} IST`\n"
            f"Data source: *LIVE NSE feed*"
        )
        return access_token

    except Exception as e:
        print(f"[KiteAuth] ❌ Login FAILED: {e}")
        _telegram(
            f"❌ *Kite Login FAILED*\n"
            f"`{str(e)[:200]}`\n"
            f"Falling back to *yfinance* (15-min delayed)"
        )
        return ""


async def check_token_health() -> bool:
    """
    Verify the current access_token is still valid by calling kite.profile().
    Returns True if healthy, False if expired/invalid.
    Called at 8:30 AM as a safety check before market open.
    """
    try:
        import kite_data
        info = kite_data.status()
        if info.get("connected"):
            from kiteconnect import KiteConnect
            kite = KiteConnect(api_key=KITE_API_KEY)
            kite.set_access_token(os.environ.get("KITE_ACCESS_TOKEN", ""))
            profile = kite.profile()

            # Also fetch available funds for morning briefing
            funds_msg = ""
            try:
                margins   = kite.margins()
                available = margins.get("equity", {}).get("available", {}).get("live_balance", 0)
                funds_msg = f"\nFunds available: *₹{available:,.0f}*"
            except Exception:
                pass

            _telegram(
                f"✅ *Token Health Check PASSED*\n"
                f"User: *{profile.get('user_name')}*{funds_msg}\n"
                f"System ready for *9:00 AM scan*"
            )
            print(f"[KiteAuth] Health check OK — {profile.get('user_name')}")
            return True
        else:
            raise ValueError(info.get("reason", "Token not connected"))

    except Exception as e:
        print(f"[KiteAuth] Health check FAILED: {e}")
        _telegram(
            f"⚠️ *Token Health FAILED at 8:30 AM*\n"
            f"`{str(e)[:150]}`\n"
            f"Scanner will use *yfinance* fallback"
        )
        return False


# ── Standalone test ─────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else "login"
    if cmd == "health":
        result = asyncio.run(check_token_health())
        print("Healthy:", result)
    else:
        token = asyncio.run(refresh_kite_token())
        print("Token:", token[:12] + "..." if token else "FAILED")

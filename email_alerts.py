"""
HTML email daily summary for the Q-Scanner system.
Configure via .env:
    EMAIL_FROM=you@gmail.com
    EMAIL_PASSWORD=your_app_password   # Gmail App Password (not main password)
    EMAIL_TO=you@gmail.com             # Can be same or different
    EMAIL_SMTP=smtp.gmail.com          # Default: Gmail
    EMAIL_PORT=587                     # Default: 587 (TLS)

For Gmail: enable 2FA, then create an App Password at:
https://myaccount.google.com/apppasswords
"""
from __future__ import annotations
import os, smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

EMAIL_FROM     = os.getenv("EMAIL_FROM", "")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "")
EMAIL_TO       = os.getenv("EMAIL_TO", EMAIL_FROM)
EMAIL_SMTP     = os.getenv("EMAIL_SMTP", "smtp.gmail.com")
EMAIL_PORT     = int(os.getenv("EMAIL_PORT", "587"))


def _color(val: float, positive_green=True) -> str:
    if val > 0:
        return "#00c49a" if positive_green else "#ff4d4d"
    elif val < 0:
        return "#ff4d4d" if positive_green else "#00c49a"
    return "#8b949e"


def _setup_rows_html(setups: list[dict]) -> str:
    if not setups:
        return "<tr><td colspan='6' style='color:#8b949e;text-align:center;padding:12px'>No setups today</td></tr>"
    rows = ""
    for s in setups[:20]:  # cap at 20 in email
        ticker   = s.get("ticker","").replace(".NS","")
        pattern  = s.get("pattern","")
        entry    = s.get("entry_price", 0)
        stop     = s.get("stop_price", 0)
        vol      = s.get("volume_ratio", 0)
        risk_pct = s.get("risk_pct", 0)
        pat_color = "#4d9fff" if pattern == "BREAKOUT" else "#a78bfa"
        rows += f"""
        <tr>
          <td style='padding:8px 12px;font-weight:600;color:#e6edf3'>{ticker}</td>
          <td style='padding:8px 12px'><span style='color:{pat_color};font-size:11px;font-weight:600'>{pattern}</span></td>
          <td style='padding:8px 12px;color:#00c49a'>₹{entry:.2f}</td>
          <td style='padding:8px 12px;color:#ff4d4d'>₹{stop:.2f}</td>
          <td style='padding:8px 12px;color:#e6edf3'>{vol:.1f}×</td>
          <td style='padding:8px 12px;color:#8b949e'>{risk_pct:.1f}%</td>
        </tr>"""
    return rows


def build_daily_html(
    setups: list[dict],
    regime: dict,
    scan_date: str,
    universe_size: int,
) -> str:
    breakouts = [s for s in setups if s.get("pattern") == "BREAKOUT"]
    eps       = [s for s in setups if s.get("pattern") == "EP"]
    bull      = regime.get("bullish", True)
    regime_color  = "#00c49a" if bull else "#ff4d4d"
    regime_text   = regime.get("note", "")
    n500_price    = regime.get("index_price", "—")
    n500_sma      = regime.get("sma200", "—")

    setup_rows = _setup_rows_html(setups)

    return f"""<!DOCTYPE html>
<html>
<head><meta charset='utf-8'></head>
<body style='margin:0;padding:0;background:#0d1117;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif'>
  <div style='max-width:640px;margin:0 auto;padding:24px 16px'>

    <!-- Header -->
    <div style='background:#161b22;border:1px solid #30363d;border-radius:12px;padding:24px;margin-bottom:16px'>
      <div style='display:flex;align-items:center;gap:12px;margin-bottom:4px'>
        <span style='color:#00c49a;font-size:20px'>⚡</span>
        <span style='color:#e6edf3;font-size:18px;font-weight:700'>Q-Scanner Daily Digest</span>
      </div>
      <div style='color:#8b949e;font-size:13px'>{scan_date} · Nifty 500 ({universe_size} stocks scanned)</div>
    </div>

    <!-- Market Regime -->
    <div style='background:{"rgba(0,196,154,0.08)" if bull else "rgba(255,77,77,0.08)"};
                border:1px solid {"rgba(0,196,154,0.3)" if bull else "rgba(255,77,77,0.3)"};
                border-radius:10px;padding:14px 18px;margin-bottom:16px'>
      <div style='color:{regime_color};font-weight:600;font-size:13px'>
        {"📈" if bull else "📉"} {regime_text}
      </div>
      <div style='color:#8b949e;font-size:12px;margin-top:4px'>
        Nifty 500: {n500_price} · 200-SMA: {n500_sma}
      </div>
    </div>

    <!-- Summary Stats -->
    <div style='display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;margin-bottom:16px'>
      <div style='background:#161b22;border:1px solid #30363d;border-radius:10px;padding:14px;text-align:center'>
        <div style='color:#00c49a;font-size:24px;font-weight:700'>{len(setups)}</div>
        <div style='color:#8b949e;font-size:11px;margin-top:2px'>Total Setups</div>
      </div>
      <div style='background:#161b22;border:1px solid #30363d;border-radius:10px;padding:14px;text-align:center'>
        <div style='color:#4d9fff;font-size:24px;font-weight:700'>{len(breakouts)}</div>
        <div style='color:#8b949e;font-size:11px;margin-top:2px'>Breakouts</div>
      </div>
      <div style='background:#161b22;border:1px solid #30363d;border-radius:10px;padding:14px;text-align:center'>
        <div style='color:#a78bfa;font-size:24px;font-weight:700'>{len(eps)}</div>
        <div style='color:#8b949e;font-size:11px;margin-top:2px'>Episodic Pivots</div>
      </div>
    </div>

    <!-- Setups Table -->
    <div style='background:#161b22;border:1px solid #30363d;border-radius:12px;overflow:hidden;margin-bottom:16px'>
      <div style='padding:14px 16px;border-bottom:1px solid #30363d'>
        <span style='color:#e6edf3;font-weight:600;font-size:14px'>Today's Setups</span>
      </div>
      <table style='width:100%;border-collapse:collapse'>
        <thead>
          <tr style='background:rgba(48,54,61,0.4)'>
            <th style='padding:8px 12px;text-align:left;color:#8b949e;font-size:11px;font-weight:500'>Ticker</th>
            <th style='padding:8px 12px;text-align:left;color:#8b949e;font-size:11px;font-weight:500'>Pattern</th>
            <th style='padding:8px 12px;text-align:left;color:#8b949e;font-size:11px;font-weight:500'>Entry</th>
            <th style='padding:8px 12px;text-align:left;color:#8b949e;font-size:11px;font-weight:500'>Stop</th>
            <th style='padding:8px 12px;text-align:left;color:#8b949e;font-size:11px;font-weight:500'>Volume</th>
            <th style='padding:8px 12px;text-align:left;color:#8b949e;font-size:11px;font-weight:500'>Risk%</th>
          </tr>
        </thead>
        <tbody style='color:#8b949e;font-size:13px'>
          {setup_rows}
        </tbody>
      </table>
    </div>

    <!-- Footer -->
    <div style='color:#484f58;font-size:11px;text-align:center'>
      Q-Scanner · Qullamaggie Method · Auto-generated {datetime.now().strftime("%H:%M IST")}
    </div>
  </div>
</body>
</html>"""


def send_daily_email(setups: list[dict], regime: dict, scan_date: str, universe_size: int) -> bool:
    if not EMAIL_FROM or not EMAIL_PASSWORD:
        print("[Email] Skipped — EMAIL_FROM / EMAIL_PASSWORD not set in .env")
        return False
    try:
        html = build_daily_html(setups, regime, scan_date, universe_size)
        msg  = MIMEMultipart("alternative")
        msg["Subject"] = f"Q-Scanner: {len(setups)} setups for {scan_date}"
        msg["From"]    = EMAIL_FROM
        msg["To"]      = EMAIL_TO
        msg.attach(MIMEText(html, "html"))

        with smtplib.SMTP(EMAIL_SMTP, EMAIL_PORT) as server:
            server.ehlo()
            server.starttls()
            server.login(EMAIL_FROM, EMAIL_PASSWORD)
            server.sendmail(EMAIL_FROM, EMAIL_TO, msg.as_string())

        print(f"[Email] Sent daily digest to {EMAIL_TO}")
        return True
    except Exception as e:
        print(f"[Email] Failed: {e}")
        return False


if __name__ == "__main__":
    # Quick test — sends a sample email
    sample = [
        {"ticker": "RELIANCE.NS", "pattern": "BREAKOUT", "entry_price": 1390,
         "stop_price": 1350, "volume_ratio": 2.4, "risk_pct": 2.9},
        {"ticker": "TRENT.NS", "pattern": "EP", "entry_price": 5200,
         "stop_price": 4900, "volume_ratio": 4.1, "risk_pct": 5.8},
    ]
    regime = {"bullish": True, "note": "Above 200-SMA — Bull market",
              "index_price": 21800, "sma200": 21200}
    ok = send_daily_email(sample, regime, datetime.now().strftime("%Y-%m-%d"), 500)
    print("Sent:", ok)

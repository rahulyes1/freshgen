"use client"
import { useState } from "react"
import useSWR from "swr"
import { fetchHealth } from "@/lib/api"
import {
  Activity, Clock, Database, Wifi, WifiOff, AlertCircle,
  TrendingUp, Zap, BarChart2, RefreshCw, Bell, Server, Globe,
} from "lucide-react"

const JOBS = [
  { time: "08:00", label: "Kite Login", desc: "Auto-refresh Zerodha session token via Playwright + OTP", icon: "🔑", color: "rgba(77,159,255,0.15)", border: "rgba(77,159,255,0.3)" },
  { time: "08:30", label: "Token Health", desc: "Verify Kite access token is valid before market open", icon: "✅", color: "rgba(0,196,154,0.1)", border: "rgba(0,196,154,0.3)" },
  { time: "09:00", label: "Morning Scan", desc: "Scan Nifty 500 on yesterday's confirmed EOD closes — Breakout, EP, VCP", icon: "🔍", color: "rgba(0,196,154,0.1)", border: "rgba(0,196,154,0.3)" },
  { time: "09:15", label: "EP + ORH Alert", desc: "Check EP setups vs Opening Range High (5-min ORH from Kite 1-min candles). Sends Telegram with entry levels + EPS/announcement context", icon: "⚡", color: "rgba(255,180,0,0.1)", border: "rgba(255,180,0,0.3)" },
  { time: "15:40", label: "Trailing Stop Check", desc: "EOD close-based: fire alert if close < 10-day MA (fast stocks) or 20-day MA (slow stocks)", icon: "🛑", color: "rgba(255,77,77,0.1)", border: "rgba(255,77,77,0.3)" },
  { time: "15:45", label: "After-Close Scan ★", desc: "PRIMARY scan — confirmed EOD candles for tomorrow's setups. Checks 30-position limit. Sends 'Tonight's Setups' Telegram", icon: "🌙", color: "rgba(0,196,154,0.15)", border: "rgba(0,196,154,0.4)" },
  { time: "*/30", label: "Price Refresh", desc: "Kite live quotes (real-time) or yfinance (15-min delayed). Partial profit alert at +15% from entry. Hard stop breach alert (wait for EOD close)", icon: "💰", color: "rgba(48,54,61,0.5)", border: "rgba(100,110,120,0.4)" },
]

const DATA_SOURCES = [
  { name: "yfinance", desc: "Primary data: OHLCV history, fundamentals (EPS, revenue via quarterly_financials), 15-min delayed prices", reliable: true },
  { name: "Kite Connect", desc: "Real-time NSE quotes, 1-min intraday candles for ORH, instrument token map", reliable: null },
  { name: "NSE Corp. API", desc: "Corporate announcements (results, concalls). Fallback: yfinance news feed", reliable: true },
]

const FILTERS = [
  { name: "RS Rank", desc: "IBD-style weighted: 40% 1M + 20% 3M + 15% 6M + 15% 12M + 10% 18M. Only top-20% percentile pass" },
  { name: "Volume", desc: "Breakout bar volume ≥ 1.5× 20-day average" },
  { name: "ATR Contraction", desc: "Base volatility must compress vs. prior trend — no wide/loose bases" },
  { name: "Linearity", desc: "No gap-down > 3% more than once in base. No spike day > 2.5× avg range more than twice" },
  { name: "52W Proximity", desc: "Price within 25% of 52-week high" },
  { name: "Fundamentals", desc: "EPS QoQ/YoY + revenue growth enriched from yfinance. Strong catalyst = announcement + EPS > 20% YoY" },
]

const EXIT_RULES = [
  { rule: "Hard stop", desc: "Fixed stop at entry stop price. Alert fires intraday but action is EOD close-based" },
  { rule: "Trailing stop — fast", desc: "10-day MA. For stocks moving quickly (EP, fast breakouts)" },
  { rule: "Trailing stop — slow", desc: "20-day MA. For steady VCP / consolidation breakouts" },
  { rule: "Partial profit", desc: "One-time Telegram alert when position +15% from entry. No auto-sell." },
  { rule: "30-position warning", desc: "Qullamaggie heuristic: if hitting 30 open positions, market is likely topping" },
]

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-xl p-5 space-y-3" style={{ backgroundColor: "var(--bg-card)", border: "1px solid var(--border)" }}>
      <h2 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>{title}</h2>
      {children}
    </div>
  )
}

export default function SystemMapPage() {
  const { data: health } = useSWR("health", fetchHealth, { refreshInterval: 30_000 })

  return (
    <div className="max-w-5xl mx-auto space-y-5">
      <div>
        <h1 className="text-xl font-bold" style={{ color: "var(--text-primary)" }}>System Map</h1>
        <p className="text-xs mt-0.5" style={{ color: "var(--text-muted)" }}>
          Qullamaggie EOD swing trading system — Nifty 500 universe
        </p>
      </div>

      {/* Live status bar */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[
          {
            label: "Backend",
            value: health ? "Online" : "Offline",
            icon: health ? <Server size={13} /> : <AlertCircle size={13} />,
            ok: !!health,
          },
          {
            label: "Scheduler",
            value: health?.scheduler_running ? "Active" : "Stopped",
            icon: <Clock size={13} />,
            ok: !!health?.scheduler_running,
          },
          {
            label: "Kite Connect",
            value: health?.kite_connected ? `Connected (${health.kite_user})` : "Not connected",
            icon: health?.kite_connected ? <Wifi size={13} /> : <WifiOff size={13} />,
            ok: !!health?.kite_connected,
          },
          {
            label: "Data Source",
            value: health?.data_source === "kite" ? "Kite (real-time)" : "yfinance (15-min delay)",
            icon: <Globe size={13} />,
            ok: true,
          },
        ].map(({ label, value, icon, ok }) => (
          <div key={label} className="rounded-xl px-4 py-3" style={{ backgroundColor: "var(--bg-card)", border: "1px solid var(--border)" }}>
            <div className="flex items-center gap-1.5 text-xs mb-1" style={{ color: "var(--text-muted)" }}>
              <span style={{ color: ok ? "var(--green)" : "var(--red)" }}>{icon}</span>
              {label}
            </div>
            <div className="text-xs font-semibold" style={{ color: ok ? "var(--text-primary)" : "var(--red)" }}>{value}</div>
          </div>
        ))}
      </div>

      {/* Scheduler timeline */}
      <Section title="⏰ Daily Scheduler (IST, Mon–Fri)">
        <div className="space-y-2">
          {JOBS.map(j => (
            <div key={j.time} className="flex items-start gap-3 rounded-lg px-3 py-2.5"
                 style={{ backgroundColor: j.color, border: `1px solid ${j.border}` }}>
              <div className="text-xs font-mono font-bold pt-0.5 w-10 shrink-0" style={{ color: "var(--text-muted)" }}>{j.time}</div>
              <div className="text-base shrink-0">{j.icon}</div>
              <div>
                <div className="text-xs font-semibold" style={{ color: "var(--text-primary)" }}>{j.label}</div>
                <div className="text-xs mt-0.5" style={{ color: "var(--text-muted)" }}>{j.desc}</div>
              </div>
            </div>
          ))}
        </div>
      </Section>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
        {/* Data sources */}
        <Section title="📡 Data Sources">
          <div className="space-y-2">
            {DATA_SOURCES.map(d => (
              <div key={d.name} className="rounded-lg px-3 py-2" style={{ backgroundColor: "rgba(48,54,61,0.4)", border: "1px solid var(--border)" }}>
                <div className="flex items-center gap-2 text-xs font-semibold mb-0.5" style={{ color: "var(--text-primary)" }}>
                  {d.reliable === true ? <span style={{ color: "var(--green)" }}>●</span>
                   : d.reliable === false ? <span style={{ color: "var(--red)" }}>●</span>
                   : <span style={{ color: "rgb(255,180,0)" }}>●</span>}
                  {d.name}
                </div>
                <div className="text-xs" style={{ color: "var(--text-muted)" }}>{d.desc}</div>
              </div>
            ))}
          </div>
        </Section>

        {/* Alerts */}
        <Section title="📲 Telegram Alerts">
          <div className="space-y-2 text-xs" style={{ color: "var(--text-muted)" }}>
            {[
              ["9:00 AM", "Morning setups list (BO/EP/VCP counts)"],
              ["9:15 AM", "EP gap alert with ORH entry level, EPS context"],
              ["3:40 PM", "Trailing stop breach (10MA / 20MA)"],
              ["3:45 PM", "Tonight's setups for tomorrow"],
              ["Intraday", "Hard stop breach warning (wait for EOD close)"],
              ["Intraday", "+15% partial profit alert (one-time per position)"],
              ["Any time", "30-position market-top warning"],
            ].map(([time, msg]) => (
              <div key={msg} className="flex gap-2 items-start">
                <span className="font-mono w-16 shrink-0" style={{ color: "var(--blue)" }}>{time}</span>
                <span>{msg}</span>
              </div>
            ))}
          </div>
        </Section>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
        {/* Setup filters */}
        <Section title="🔍 Scanner Filters">
          <div className="space-y-2">
            {FILTERS.map(f => (
              <div key={f.name} className="rounded-lg px-3 py-2" style={{ backgroundColor: "rgba(48,54,61,0.4)", border: "1px solid var(--border)" }}>
                <div className="text-xs font-semibold mb-0.5" style={{ color: "var(--text-primary)" }}>{f.name}</div>
                <div className="text-xs" style={{ color: "var(--text-muted)" }}>{f.desc}</div>
              </div>
            ))}
          </div>
        </Section>

        {/* Exit rules */}
        <Section title="🚪 Exit Rules">
          <div className="space-y-2">
            {EXIT_RULES.map(e => (
              <div key={e.rule} className="rounded-lg px-3 py-2" style={{ backgroundColor: "rgba(48,54,61,0.4)", border: "1px solid var(--border)" }}>
                <div className="text-xs font-semibold mb-0.5" style={{ color: "var(--text-primary)" }}>{e.rule}</div>
                <div className="text-xs" style={{ color: "var(--text-muted)" }}>{e.desc}</div>
              </div>
            ))}
          </div>
        </Section>
      </div>

      {/* Data flow */}
      <Section title="🔄 Data Flow">
        <div className="flex items-center gap-2 flex-wrap text-xs" style={{ color: "var(--text-muted)" }}>
          {[
            "NSE / yfinance / Kite",
            "→",
            "screener.py (patterns + RS + linearity)",
            "→",
            "fundamentals.py (EPS + announcements)",
            "→",
            "SQLite DB",
            "→",
            "FastAPI /scan",
            "→",
            "Dashboard",
            "→",
            "Telegram",
          ].map((step, i) => (
            <span key={i}
                  className={step !== "→" ? "px-2 py-1 rounded" : ""}
                  style={step !== "→"
                    ? { backgroundColor: "rgba(48,54,61,0.6)", border: "1px solid var(--border)", color: "var(--text-primary)" }
                    : { color: "var(--border)" }
                  }>
              {step}
            </span>
          ))}
        </div>
      </Section>
    </div>
  )
}

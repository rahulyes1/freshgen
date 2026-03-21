"use client"

/* ============================================================
   SYSTEM ARCHITECTURE DIAGRAM
   Full visual map of the Qullamaggie Nifty 500 Trading System
   ============================================================ */

const C = {
  data:      { bg: "rgba(77,159,255,0.10)",  border: "rgba(77,159,255,0.35)",  text: "#4D9FFF",  label: "DATA"     },
  analysis:  { bg: "rgba(0,196,154,0.10)",   border: "rgba(0,196,154,0.35)",   text: "#00C49A",  label: "ANALYSIS" },
  storage:   { bg: "rgba(255,180,0,0.10)",   border: "rgba(255,180,0,0.35)",   text: "#FFB400",  label: "STORAGE"  },
  api:       { bg: "rgba(162,89,255,0.12)",  border: "rgba(162,89,255,0.40)",  text: "#A259FF",  label: "API"      },
  scheduler: { bg: "rgba(255,100,100,0.10)", border: "rgba(255,100,100,0.35)", text: "#FF6464",  label: "SCHEDULER"},
  output:    { bg: "rgba(255,140,0,0.10)",   border: "rgba(255,140,0,0.35)",   text: "#FF8C00",  label: "OUTPUT"   },
}

type LayerKey = keyof typeof C

function Box({ title, items, layer, wide, compact }: {
  title: string; items: string[]; layer: LayerKey; wide?: boolean; compact?: boolean
}) {
  const col = C[layer]
  return (
    <div style={{
      backgroundColor: col.bg,
      border: `1.5px solid ${col.border}`,
      borderRadius: 12,
      padding: compact ? "10px 14px" : "14px 16px",
      minWidth: wide ? 220 : 160,
      maxWidth: wide ? 280 : 220,
      flex: "0 0 auto",
    }}>
      <div style={{ color: col.text, fontWeight: 700, fontSize: 12, marginBottom: 8, letterSpacing: "0.06em" }}>
        {title}
      </div>
      {items.map((item, i) => (
        <div key={i} style={{
          color: "var(--text-muted)",
          fontSize: 11,
          padding: "2px 0",
          borderLeft: `2px solid ${col.border}`,
          paddingLeft: 8,
          marginBottom: 3,
        }}>
          {item}
        </div>
      ))}
    </div>
  )
}

function Arrow({ label, vertical }: { label?: string; vertical?: boolean }) {
  return (
    <div style={{
      display: "flex",
      flexDirection: vertical ? "column" : "row",
      alignItems: "center",
      justifyContent: "center",
      color: "var(--text-muted)",
      fontSize: 10,
      gap: 2,
      flexShrink: 0,
      minWidth: vertical ? "auto" : 32,
      minHeight: vertical ? 32 : "auto",
    }}>
      {label && <span style={{ fontSize: 9, opacity: 0.6, whiteSpace: "nowrap" }}>{label}</span>}
      <span style={{ fontSize: 16, opacity: 0.5 }}>{vertical ? "↓" : "→"}</span>
    </div>
  )
}

function LayerLabel({ label, color }: { label: string; color: string }) {
  return (
    <div style={{
      writingMode: "vertical-rl",
      textOrientation: "mixed",
      transform: "rotate(180deg)",
      color,
      fontSize: 9,
      fontWeight: 700,
      letterSpacing: "0.15em",
      opacity: 0.7,
      minWidth: 16,
    }}>
      {label}
    </div>
  )
}

function SectionHeader({ title, color, sub }: { title: string; color: string; sub?: string }) {
  return (
    <div style={{ marginBottom: 12 }}>
      <div style={{ color, fontWeight: 700, fontSize: 13, letterSpacing: "0.08em" }}>{title}</div>
      {sub && <div style={{ color: "var(--text-muted)", fontSize: 10, marginTop: 2 }}>{sub}</div>}
    </div>
  )
}

function Row({ children, gap = 10 }: { children: React.ReactNode; gap?: number }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap, flexWrap: "wrap" }}>
      {children}
    </div>
  )
}

function Pill({ text, color }: { text: string; color: string }) {
  return (
    <span style={{
      backgroundColor: `${color}18`,
      border: `1px solid ${color}50`,
      color,
      fontSize: 10,
      padding: "2px 8px",
      borderRadius: 20,
      fontWeight: 600,
      whiteSpace: "nowrap",
    }}>
      {text}
    </span>
  )
}

function ScheduleJob({ time, label, desc, color }: { time: string; label: string; desc: string; color: string }) {
  return (
    <div style={{
      display: "flex",
      alignItems: "flex-start",
      gap: 10,
      padding: "8px 12px",
      borderRadius: 8,
      backgroundColor: `${color}10`,
      border: `1px solid ${color}30`,
      flex: "1 1 160px",
      minWidth: 160,
    }}>
      <div style={{
        color,
        fontWeight: 700,
        fontSize: 11,
        minWidth: 44,
        borderRight: `1px solid ${color}40`,
        paddingRight: 8,
        paddingTop: 1,
      }}>
        {time}
      </div>
      <div>
        <div style={{ color, fontWeight: 600, fontSize: 11 }}>{label}</div>
        <div style={{ color: "var(--text-muted)", fontSize: 10, marginTop: 1 }}>{desc}</div>
      </div>
    </div>
  )
}

function ConfigBadge({ k, v }: { k: string; v: string }) {
  return (
    <div style={{
      display: "flex",
      alignItems: "center",
      gap: 6,
      padding: "3px 10px 3px 8px",
      borderRadius: 6,
      backgroundColor: "rgba(255,180,0,0.08)",
      border: "1px solid rgba(255,180,0,0.25)",
      fontSize: 10,
    }}>
      <span style={{ color: "#FFB400", fontWeight: 600 }}>{k}</span>
      <span style={{ color: "var(--text-muted)" }}>=</span>
      <span style={{ color: "var(--text-primary)", fontFamily: "monospace" }}>{v}</span>
    </div>
  )
}

function Card({ children, style = {} }: { children: React.ReactNode; style?: React.CSSProperties }) {
  return (
    <div style={{
      backgroundColor: "var(--bg-card)",
      border: "1px solid var(--border)",
      borderRadius: 16,
      padding: "20px 24px",
      ...style,
    }}>
      {children}
    </div>
  )
}

export default function ArchitecturePage() {
  return (
    <div style={{ maxWidth: 1100, margin: "0 auto", paddingBottom: 60 }}>

      {/* Title */}
      <div style={{ marginBottom: 28 }}>
        <h1 style={{ color: "var(--text-primary)", fontWeight: 800, fontSize: 22, margin: 0 }}>
          System Architecture
        </h1>
        <p style={{ color: "var(--text-muted)", fontSize: 12, marginTop: 4 }}>
          Complete visual map of the Qullamaggie Nifty 500 automated swing trading system
        </p>
      </div>

      {/* ── LAYER 1: MAIN PIPELINE ──────────────────────────────── */}
      <Card style={{ marginBottom: 16 }}>
        <SectionHeader title="① DATA → ANALYSIS → STORAGE PIPELINE"
                       color={C.data.text}
                       sub="Core flow: raw market data → pattern detection → database persistence" />
        <div style={{ overflowX: "auto", paddingBottom: 8 }}>
          <Row gap={4}>
            {/* Data Sources */}
            <Box layer="data" title="NSE API" items={[
              "fetch_live_nifty500()",
              "500 live tickers daily",
              "Cached → data/nifty500_cache.txt",
              "Refreshes once per day",
            ]} />
            <Arrow label="tickers" />
            <Box layer="data" title="yfinance (Data)" items={[
              "get_recent_data(ticker)",
              "350 days OHLCV history",
              "auto_adjust=True (splits)",
              "Multi-level col flattening",
            ]} />
            <Arrow label="OHLCV df" />

            {/* Analysis */}
            <Box layer="analysis" title="indicators.py" items={[
              "SMA 50 / 150",
              "EMA 10 (trailing stop)",
              "ATR 14 (volatility)",
              "Volume SMA 50",
              "VolRatio, GapPct",
              "InUptrend, Near52WHigh",
              "compute_rs_raw() ← NEW",
            ]} />
            <Arrow label="df + cols" />
            <Box layer="analysis" title="patterns.py" items={[
              "find_breakout_setups()",
              "  ∟ 3–12 week base",
              "  ∟ vol ≥ 1.5× avg",
              "find_ep_setups()",
              "  ∟ gap ≥ 4% + vol ≥ 2×",
              "find_vcp_setups() ← NEW",
              "  ∟ 4-segment contraction",
              "deduplicate_setups(20d)",
            ]} />
            <Arrow label="Setup[]" />
            <Box layer="analysis" title="screener.py" items={[
              "screen_ticker() per stock",
              "RS percentile rank (1–99)",
              "Earnings guard check ← NEW",
              "ATR14 per setup",
              "run_screener() → DataFrame",
              "sorted by rs_rank DESC",
            ]} />
            <Arrow label="rows[]" />

            {/* Storage */}
            <Box layer="storage" title="SQLite DB (trading.db)" items={[
              "scan_results — daily setups",
              "scan_runs — timing stats",
              "positions — live trades",
              "journal — trade log",
              "watchlist — alerts",
              "paper_trades ← NEW",
            ]} />
          </Row>
        </div>
      </Card>

      {/* ── LAYER 2: API LAYER ──────────────────────────────────── */}
      <Card style={{ marginBottom: 16 }}>
        <SectionHeader title="② FASTAPI BACKEND  (api/main.py  ·  :8000)"
                       color={C.api.text}
                       sub="Async REST API — serves the dashboard and processes all trading logic" />
        <div style={{ display: "flex", flexWrap: "wrap", gap: 10 }}>
          {[
            { route: "GET /health", desc: "Market regime (^CRSLDX vs 200-SMA)", tag: "health" },
            { route: "GET /scan", desc: "Cache-first daily scan · force=true bypasses", tag: "scan" },
            { route: "GET /chart/{ticker}", desc: "OHLCV + EMA10 + SMA50 + SMA200", tag: "chart" },
            { route: "CRUD /positions", desc: "Open/closed trades + unrealized P&L", tag: "pos" },
            { route: "POST /positions/refresh-prices", desc: "yfinance batch fetch + stop alerts", tag: "pos" },
            { route: "CRUD /journal", desc: "Trade journal + analytics + CSV export", tag: "journal" },
            { route: "GET /journal/analytics", desc: "Win rate, PF, expectancy, monthly P&L", tag: "journal" },
            { route: "CRUD /watchlist", desc: "Alert tickers highlighted in scan", tag: "watch" },
            { route: "CRUD /paper", desc: "Paper trades auto-logged from scanner", tag: "paper" },
            { route: "GET /paper/stats", desc: "System win rate, expectancy, by-pattern", tag: "paper" },
            { route: "POST /backtest", desc: "Full portfolio backtest, equity curve", tag: "bt" },
            { route: "GET /scan/history", desc: "Past scan run log", tag: "scan" },
          ].map(({ route, desc, tag }) => (
            <div key={route} style={{
              flex: "1 1 220px",
              backgroundColor: C.api.bg,
              border: `1px solid ${C.api.border}`,
              borderRadius: 8,
              padding: "8px 12px",
            }}>
              <div style={{ color: C.api.text, fontSize: 11, fontWeight: 700, fontFamily: "monospace", marginBottom: 3 }}>
                {route}
              </div>
              <div style={{ color: "var(--text-muted)", fontSize: 10 }}>{desc}</div>
            </div>
          ))}
        </div>

        {/* Sizing helper */}
        <div style={{ marginTop: 14, padding: "10px 14px", borderRadius: 8,
                      backgroundColor: "rgba(162,89,255,0.07)", border: "1px solid rgba(162,89,255,0.2)" }}>
          <div style={{ color: C.api.text, fontWeight: 700, fontSize: 11, marginBottom: 6 }}>
            _compute_sizing()  —  ATR-based position sizing  ← NEW
          </div>
          <Row gap={6}>
            <Pill text="risk_per_share = entry − stop" color={C.api.text} />
            <Arrow />
            <Pill text="ATR floor = max(risk, 2×ATR14)" color={C.analysis.text} />
            <Arrow />
            <Pill text="shares = floor(1%×account ÷ risk)" color={C.storage.text} />
            <Arrow />
            <Pill text="cap at 25% position" color={C.output.text} />
          </Row>
        </div>
      </Card>

      {/* ── LAYER 3: SCHEDULER ──────────────────────────────────── */}
      <Card style={{ marginBottom: 16 }}>
        <SectionHeader title="③ APSCHEDULER  (api/scheduler.py)"
                       color={C.scheduler.text}
                       sub="All automated jobs — Mon–Fri, IST timezone" />
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginBottom: 14 }}>
          <ScheduleJob time="09:00" label="Daily Full Scan" color={C.scheduler.text}
            desc="500 stocks · fresh_bars=5 · save DB · Telegram digest · auto-log paper trades" />
          <ScheduleJob time="09:15" label="Intraday Open" color="#FF9F43"
            desc="fresh_bars=1 · HQ Telegram alert · auto-log new paper trades" />
          <ScheduleJob time="12:00" label="Intraday Midday" color="#FF9F43"
            desc="fresh_bars=1 · catch midday breakouts · HQ alerts" />
          <ScheduleJob time="14:30" label="Intraday Pre-close" color="#FF9F43"
            desc="fresh_bars=1 · final session signals · paper trade log" />
          <ScheduleJob time="*/30min" label="Price Refresh" color={C.analysis.text}
            desc="9:15–15:30 · yfinance batch · update DB · fire stop-loss Telegram alerts" />
        </div>
        <div style={{ padding: "8px 12px", borderRadius: 8, backgroundColor: "rgba(255,100,100,0.07)",
                      border: "1px solid rgba(255,100,100,0.2)" }}>
          <div style={{ color: C.scheduler.text, fontSize: 11, fontWeight: 700, marginBottom: 4 }}>HQ Instant Alerts</div>
          <Row gap={8}>
            <Pill text="EP gap > 6%" color={C.scheduler.text} />
            <Pill text="OR volume > 3×" color={C.scheduler.text} />
            <Arrow label="fires" />
            <Pill text="Telegram HQ message" color="#FF9F43" />
            <Pill text="RS rank included" color={C.analysis.text} />
          </Row>
        </div>
      </Card>

      {/* ── LAYER 4: CONFIG ─────────────────────────────────────── */}
      <Card style={{ marginBottom: 16 }}>
        <SectionHeader title="④ CONFIG.PY  —  All Parameters"
                       color={C.storage.text}
                       sub="Single source of truth — nothing is hardcoded in other files" />
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
          <ConfigBadge k="ACCOUNT_SIZE"             v="₹10,00,000" />
          <ConfigBadge k="RISK_PER_TRADE"           v="1%" />
          <ConfigBadge k="MAX_POSITION_PCT"         v="25%" />
          <ConfigBadge k="STOP_MAX_PCT"             v="8%" />
          <ConfigBadge k="RISK_CAP_MULTIPLIER"      v="5×" />
          <ConfigBadge k="DRAWDOWN_PAUSE_PCT"       v="20%" />
          <ConfigBadge k="DRAWDOWN_PAUSE_DAYS"      v="30d" />
          <ConfigBadge k="SMA_SHORT"                v="50d" />
          <ConfigBadge k="SMA_LONG"                 v="150d" />
          <ConfigBadge k="EMA_TRAIL"                v="10d" />
          <ConfigBadge k="ATR_PERIOD"               v="14d" />
          <ConfigBadge k="CONSOLIDATION_DAYS_MIN"   v="15d" />
          <ConfigBadge k="CONSOLIDATION_DAYS_MAX"   v="60d" />
          <ConfigBadge k="CONSOLIDATION_RANGE_MAX"  v="20%" />
          <ConfigBadge k="ATR_CONTRACTION_RATIO"    v="0.85" />
          <ConfigBadge k="BREAKOUT_VOLUME_MULT"     v="1.5×" />
          <ConfigBadge k="EP_GAP_MIN"               v="4%" />
          <ConfigBadge k="EP_VOLUME_MULT"           v="2×" />
          <ConfigBadge k="TRANSACTION_COST_PCT"     v="0.3%" />
          <ConfigBadge k="MARKET"                   v='"IN"' />
        </div>
      </Card>

      {/* ── LAYER 5: DASHBOARD PAGES ───────────────────────────── */}
      <Card style={{ marginBottom: 16 }}>
        <SectionHeader title="⑤ NEXT.JS DASHBOARD  (:3000)"
                       color={C.output.text}
                       sub="Dark-themed React UI — SWR polling, Recharts, Tailwind CSS" />
        <div style={{ display: "flex", flexWrap: "wrap", gap: 10 }}>
          {[
            { page: "/setups", icon: "📡", desc: "Live setups grid · regime banner · RS rank badge · Earnings warning · Pattern filter (Breakout/EP/VCP) · chart modal · Add to Positions" },
            { page: "/positions", icon: "📋", desc: "Open/closed table · Portfolio Risk Meter · stop-loss alert banner · Refresh Prices button · unrealized P&L" },
            { page: "/journal", icon: "📓", desc: "Trade log form · analytics (win rate, PF, expectancy) · monthly P&L bar chart · by-pattern breakdown · CSV export" },
            { page: "/watchlist", icon: "👁️", desc: "Add/remove tickers · alert toggle · green highlight when in today's scan" },
            { page: "/paper", icon: "🧪", desc: "Auto-logged from scanner · win rate / expectancy · inline close with exit price · stats grid by pattern · Refresh Prices" },
            { page: "/backtest", icon: "📈", desc: "Full Nifty 500 backtest · equity curve + drawdown chart · stats grid · trade log table" },
            { page: "/sectors", icon: "🗺️", desc: "10 NSE sector heatmap · intensity by setup count · live data" },
            { page: "/architecture", icon: "🗂️", desc: "This page — full system diagram" },
          ].map(({ page, icon, desc }) => (
            <div key={page} style={{
              flex: "1 1 220px",
              backgroundColor: C.output.bg,
              border: `1px solid ${C.output.border}`,
              borderRadius: 10,
              padding: "10px 14px",
            }}>
              <div style={{ color: C.output.text, fontWeight: 700, fontSize: 12, marginBottom: 5 }}>
                {icon} {page}
              </div>
              <div style={{ color: "var(--text-muted)", fontSize: 10, lineHeight: 1.5 }}>{desc}</div>
            </div>
          ))}
        </div>
      </Card>

      {/* ── LAYER 6: ALERTS ─────────────────────────────────────── */}
      <Card style={{ marginBottom: 16 }}>
        <SectionHeader title="⑥ ALERT CHANNELS"
                       color="#FF9F43"
                       sub="Multi-channel notifications for key trading events" />
        <div style={{ display: "flex", flexWrap: "wrap", gap: 10 }}>
          <div style={{ flex: "1 1 200px", backgroundColor: "rgba(0,136,204,0.10)",
                        border: "1px solid rgba(0,136,204,0.30)", borderRadius: 10, padding: "12px 16px" }}>
            <div style={{ color: "#0088CC", fontWeight: 700, fontSize: 12, marginBottom: 8 }}>📱 Telegram Bot</div>
            {[
              "Daily digest — all setups at 9:00 AM",
              "HQ instant — EP gap>6% or vol>3×",
              "Intraday — 09:15, 12:00, 14:30",
              "Stop-loss breach — real-time",
              "Watchlist match alert",
              "RS rank shown on HQ alerts ← NEW",
            ].map((t, i) => <div key={i} style={{ color: "var(--text-muted)", fontSize: 10, padding: "2px 0 2px 8px", borderLeft: "2px solid rgba(0,136,204,0.4)", marginBottom: 2 }}>{t}</div>)}
          </div>
          <div style={{ flex: "1 1 200px", backgroundColor: "rgba(234,67,53,0.10)",
                        border: "1px solid rgba(234,67,53,0.30)", borderRadius: 10, padding: "12px 16px" }}>
            <div style={{ color: "#EA4335", fontWeight: 700, fontSize: 12, marginBottom: 8 }}>📧 Email (Gmail SMTP)</div>
            {[
              "Dark-themed HTML daily digest",
              "Bull / Bear market regime header",
              "All setups with sizing info",
              "Config: EMAIL_FROM, EMAIL_TO",
              "Config: EMAIL_PASSWORD (App Password)",
              "Sent alongside Telegram at 9:00 AM",
            ].map((t, i) => <div key={i} style={{ color: "var(--text-muted)", fontSize: 10, padding: "2px 0 2px 8px", borderLeft: "2px solid rgba(234,67,53,0.4)", marginBottom: 2 }}>{t}</div>)}
          </div>
          <div style={{ flex: "1 1 200px", backgroundColor: "rgba(0,196,154,0.10)",
                        border: "1px solid rgba(0,196,154,0.30)", borderRadius: 10, padding: "12px 16px" }}>
            <div style={{ color: "#00C49A", fontWeight: 700, fontSize: 12, marginBottom: 8 }}>🖥️ Dashboard (live)</div>
            {[
              "Market regime banner (bull/bear)",
              "Scan cache indicator (from DB)",
              "Stop-loss alert banner in Positions",
              "Portfolio Risk Meter widget",
              "Earnings warning on setup cards ← NEW",
              "RS rank badge on setup cards ← NEW",
            ].map((t, i) => <div key={i} style={{ color: "var(--text-muted)", fontSize: 10, padding: "2px 0 2px 8px", borderLeft: "2px solid rgba(0,196,154,0.4)", marginBottom: 2 }}>{t}</div>)}
          </div>
        </div>
      </Card>

      {/* ── LAYER 7: PATTERN LOGIC ─────────────────────────────── */}
      <Card style={{ marginBottom: 16 }}>
        <SectionHeader title="⑦ PATTERN DETECTION LOGIC"
                       color={C.analysis.text}
                       sub="Three trading patterns, each with distinct entry criteria (no look-ahead bias)" />
        <div style={{ display: "flex", flexWrap: "wrap", gap: 10 }}>
          <div style={{ flex: "1 1 200px", backgroundColor: C.analysis.bg,
                        border: `1.5px solid ${C.analysis.border}`, borderRadius: 10, padding: "12px 16px" }}>
            <div style={{ color: C.analysis.text, fontWeight: 700, fontSize: 12, marginBottom: 8 }}>📈 BREAKOUT</div>
            {[
              "Close > SMA50 and SMA150 (uptrend)",
              "Within 25% of 52-week high",
              "3–12 week tight base (≤20% range)",
              "ATR contraction ≤ 85% of prior period",
              "Volume ≥ 1.5× 50-day average",
              "Close breaks above base high",
              "Stop: base low (max 8% from entry)",
            ].map((t, i) => <div key={i} style={{ color: "var(--text-muted)", fontSize: 10, padding: "2px 0 2px 8px", borderLeft: `2px solid ${C.analysis.border}`, marginBottom: 2 }}>{t}</div>)}
          </div>
          <div style={{ flex: "1 1 200px", backgroundColor: C.data.bg,
                        border: `1.5px solid ${C.data.border}`, borderRadius: 10, padding: "12px 16px" }}>
            <div style={{ color: C.data.text, fontWeight: 700, fontSize: 12, marginBottom: 8 }}>⚡ EPISODIC PIVOT (EP)</div>
            {[
              "Gap-up: open ≥ prev close × 1.04",
              "Volume ≥ 2× 50-day average",
              "Closes in top 50% of day's range",
              "Close > SMA50 × 0.90 (10% tolerance)",
              "No recent gap-up in last 15 days",
              "Stop: EP candle low (max 8%)",
              "Catalyst: earnings / news / sector move",
            ].map((t, i) => <div key={i} style={{ color: "var(--text-muted)", fontSize: 10, padding: "2px 0 2px 8px", borderLeft: `2px solid ${C.data.border}`, marginBottom: 2 }}>{t}</div>)}
          </div>
          <div style={{ flex: "1 1 200px", backgroundColor: "rgba(162,89,255,0.10)",
                        border: "1.5px solid rgba(162,89,255,0.35)", borderRadius: 10, padding: "12px 16px" }}>
            <div style={{ color: "#A259FF", fontWeight: 700, fontSize: 12, marginBottom: 8 }}>🔮 VCP  ← NEW</div>
            {[
              "Close > SMA50 and SMA150 (uptrend)",
              "Within 25% of 52-week high",
              "4 segments over ~16-week window",
              "Each segment range ≤ 80% of previous",
              "Volume declining across ≥ 2 segments",
              "Final contraction range ≤ 10%",
              "Volume surge ≥ 1.5× on breakout bar",
              "Stop: last contraction low",
            ].map((t, i) => <div key={i} style={{ color: "var(--text-muted)", fontSize: 10, padding: "2px 0 2px 8px", borderLeft: "2px solid rgba(162,89,255,0.35)", marginBottom: 2 }}>{t}</div>)}
          </div>
        </div>
      </Card>

      {/* ── LAYER 8: RS RANKING ──────────────────────────────────── */}
      <Card style={{ marginBottom: 16 }}>
        <SectionHeader title="⑧ RS RANKING + EARNINGS GUARD  ← NEW"
                       color={C.analysis.text}
                       sub="IBD-style Relative Strength scoring across the full 500-stock universe" />
        <div style={{ display: "flex", flexWrap: "wrap", gap: 12 }}>
          <div style={{ flex: "1 1 300px", backgroundColor: C.analysis.bg,
                        border: `1px solid ${C.analysis.border}`, borderRadius: 10, padding: "12px 16px" }}>
            <div style={{ color: C.analysis.text, fontWeight: 700, fontSize: 11, marginBottom: 8 }}>RS Raw Score Formula</div>
            <div style={{ fontFamily: "monospace", fontSize: 11, color: "var(--text-primary)",
                          backgroundColor: "rgba(0,0,0,0.2)", padding: "10px 12px", borderRadius: 6, lineHeight: 1.7 }}>
              <div style={{ color: C.analysis.text }}>compute_rs_raw(df)</div>
              <div style={{ color: "var(--text-muted)" }}>r1m  = return(21d)   × 0.40</div>
              <div style={{ color: "var(--text-muted)" }}>r3m  = return(63d)   × 0.20</div>
              <div style={{ color: "var(--text-muted)" }}>r6m  = return(126d)  × 0.20</div>
              <div style={{ color: "var(--text-muted)" }}>r12m = return(252d)  × 0.20</div>
              <div style={{ color: "var(--text-primary)", marginTop: 4 }}>score = r1m+r3m+r6m+r12m</div>
            </div>
            <div style={{ color: "var(--text-muted)", fontSize: 10, marginTop: 8 }}>
              Score computed for all 500 tickers → percentile ranked → each setup gets RS 1–99
            </div>
          </div>
          <div style={{ flex: "1 1 260px", backgroundColor: "rgba(255,180,0,0.08)",
                        border: "1px solid rgba(255,180,0,0.25)", borderRadius: 10, padding: "12px 16px" }}>
            <div style={{ color: "#FFB400", fontWeight: 700, fontSize: 11, marginBottom: 8 }}>Earnings Calendar Guard</div>
            {[
              "Calls yf.Ticker(ticker).calendar",
              "Checks if earnings within 7 days",
              "Flags setup with near_earnings=True",
              "Shown as amber warning on setup card",
              "Trade is NOT blocked — just flagged",
              "Helps avoid pre-earnings volatility",
            ].map((t, i) => <div key={i} style={{ color: "var(--text-muted)", fontSize: 10, padding: "2px 0 2px 8px", borderLeft: "2px solid rgba(255,180,0,0.35)", marginBottom: 2 }}>{t}</div>)}
          </div>
        </div>
      </Card>

      {/* ── LAYER 9: PAPER TRADING ──────────────────────────────── */}
      <Card>
        <SectionHeader title="⑨ PAPER TRADING SYSTEM  ← NEW"
                       color={C.scheduler.text}
                       sub="Zero-risk system tracker — measures real-world scanner performance over time" />
        <div style={{ display: "flex", flexWrap: "wrap", gap: 10 }}>
          <div style={{ flex: "1 1 200px", backgroundColor: C.scheduler.bg,
                        border: `1px solid ${C.scheduler.border}`, borderRadius: 10, padding: "12px 16px" }}>
            <div style={{ color: C.scheduler.text, fontWeight: 700, fontSize: 11, marginBottom: 8 }}>Auto-Logging Flow</div>
            <Row gap={6}>
              <Pill text="9:00 AM scan" color={C.scheduler.text} />
            </Row>
            <div style={{ textAlign: "center", color: "var(--text-muted)", fontSize: 14, margin: "6px 0" }}>↓</div>
            <Row gap={6}>
              <Pill text="new setups" color={C.analysis.text} />
            </Row>
            <div style={{ textAlign: "center", color: "var(--text-muted)", fontSize: 14, margin: "6px 0" }}>↓</div>
            <Row gap={6}>
              <Pill text="paper_trades table" color={C.storage.text} />
            </Row>
            <div style={{ textAlign: "center", color: "var(--text-muted)", fontSize: 14, margin: "6px 0" }}>↓</div>
            <Row gap={6}>
              <Pill text="track daily price" color={C.data.text} />
            </Row>
            <div style={{ textAlign: "center", color: "var(--text-muted)", fontSize: 14, margin: "6px 0" }}>↓</div>
            <Row gap={6}>
              <Pill text="manual close + R" color={C.output.text} />
            </Row>
          </div>
          <div style={{ flex: "1 1 200px", backgroundColor: C.scheduler.bg,
                        border: `1px solid ${C.scheduler.border}`, borderRadius: 10, padding: "12px 16px" }}>
            <div style={{ color: C.scheduler.text, fontWeight: 700, fontSize: 11, marginBottom: 8 }}>Stats Computed</div>
            {[
              "Win rate % (closed trades)",
              "Profit factor (gross win / loss)",
              "Expectancy R (avg R per trade)",
              "Total P&L in ₹",
              "Best R / Worst R",
              "By-pattern breakdown",
              "Open unrealized P&L",
            ].map((t, i) => <div key={i} style={{ color: "var(--text-muted)", fontSize: 10, padding: "2px 0 2px 8px", borderLeft: `2px solid ${C.scheduler.border}`, marginBottom: 2 }}>{t}</div>)}
          </div>
          <div style={{ flex: "1 1 200px", backgroundColor: C.scheduler.bg,
                        border: `1px solid ${C.scheduler.border}`, borderRadius: 10, padding: "12px 16px" }}>
            <div style={{ color: C.scheduler.text, fontWeight: 700, fontSize: 11, marginBottom: 8 }}>API Endpoints</div>
            {[
              "GET /paper — list trades",
              "POST /paper — add trade",
              "PUT /paper/{id} — close/update",
              "DELETE /paper/{id}",
              "GET /paper/stats — system metrics",
              "POST /paper/refresh-prices",
            ].map((t, i) => <div key={i} style={{ color: "var(--text-muted)", fontFamily: "monospace", fontSize: 10, padding: "2px 0 2px 8px", borderLeft: `2px solid ${C.scheduler.border}`, marginBottom: 2 }}>{t}</div>)}
          </div>
        </div>

        {/* Legend */}
        <div style={{ marginTop: 20, paddingTop: 16, borderTop: "1px solid var(--border)",
                      display: "flex", flexWrap: "wrap", gap: 14, alignItems: "center" }}>
          <span style={{ color: "var(--text-muted)", fontSize: 10, fontWeight: 600 }}>LEGEND:</span>
          {Object.entries(C).map(([k, v]) => (
            <div key={k} style={{ display: "flex", alignItems: "center", gap: 5 }}>
              <div style={{ width: 10, height: 10, borderRadius: 3, backgroundColor: v.bg, border: `1.5px solid ${v.border}` }} />
              <span style={{ color: v.text, fontSize: 10, fontWeight: 600 }}>{v.label}</span>
            </div>
          ))}
          <span style={{ color: "var(--text-muted)", fontSize: 10, marginLeft: 8 }}>← NEW = added in Phase 6</span>
        </div>
      </Card>
    </div>
  )
}

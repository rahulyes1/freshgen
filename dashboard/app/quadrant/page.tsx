"use client"
import useSWR from "swr"
import { RefreshCw, TrendingUp, TrendingDown, ArrowUp, ArrowDown } from "lucide-react"
import { fetchMarketQuadrant } from "@/lib/api"
import type { MarketQuadrant } from "@/lib/types"

// ── Config maps ───────────────────────────────────────────────

const OVERALL_CFG = {
  INVEST:    { label: "Fully Invest",  emoji: "🟢", color: "var(--green)",  bg: "rgba(0,196,154,0.10)",  border: "rgba(0,196,154,0.35)" },
  SELECTIVE: { label: "Be Selective",  emoji: "🟡", color: "#f59e0b",       bg: "rgba(251,191,36,0.10)", border: "rgba(251,191,36,0.35)" },
  CASH:      { label: "Stay in Cash",  emoji: "🔴", color: "var(--red)",    bg: "rgba(255,77,77,0.08)",  border: "rgba(255,77,77,0.25)"  },
}

const BIAS_CFG = {
  BULL: { label: "Bull", color: "var(--green)", desc: ">50% stocks above 200-SMA" },
  BEAR: { label: "Bear", color: "var(--red)",   desc: "<50% stocks above 200-SMA" },
}
const TREND_CFG = {
  UP:   { label: "Uptrend",   color: "var(--green)", desc: ">50% stocks above 50-SMA"  },
  DOWN: { label: "Downtrend", color: "var(--red)",   desc: "<50% stocks above 50-SMA"  },
}
const SWING_CFG = {
  HOT:  { label: "HOT",  color: "var(--green)", bg: "rgba(0,196,154,0.10)",  desc: ">70% stocks above 10-SMA — strong breadth"   },
  WARM: { label: "WARM", color: "#f59e0b",       bg: "rgba(251,191,36,0.10)", desc: "50–70% stocks above 10-SMA — moderate breadth" },
  COOL: { label: "COOL", color: "var(--blue)",   bg: "rgba(77,159,255,0.08)", desc: "30–50% stocks above 10-SMA — weak breadth"    },
  COLD: { label: "COLD", color: "var(--red)",    bg: "rgba(255,77,77,0.08)",  desc: "<30% stocks above 10-SMA — very weak breadth"  },
}
const MOM_CFG = {
  RISING:  { label: "Rising",  color: "var(--green)", icon: ArrowUp   },
  FALLING: { label: "Falling", color: "var(--red)",   icon: ArrowDown },
}

// ── Sub-components ────────────────────────────────────────────

function BreadthBar({ label, pct, color }: { label: string; pct: number; color: string }) {
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs" style={{ color: "var(--text-muted)" }}>
        <span>{label}</span>
        <span style={{ color, fontWeight: 600 }}>{pct.toFixed(1)}%</span>
      </div>
      <div className="h-2 rounded-full overflow-hidden" style={{ backgroundColor: "rgba(48,54,61,0.6)" }}>
        <div className="h-full rounded-full transition-all duration-700"
             style={{ width: `${pct}%`, backgroundColor: color }} />
      </div>
    </div>
  )
}

function QuadCard({
  title, subtitle, reading, readingColor, value, maxValue, barColor, desc,
}: {
  title: string; subtitle: string; reading: string; readingColor: string
  value: number; maxValue: number; barColor: string; desc: string
}) {
  const pct = Math.min(value / maxValue * 100, 100)
  return (
    <div className="rounded-xl p-4 space-y-3"
         style={{ backgroundColor: "var(--bg-card)", border: "1px solid var(--border)" }}>
      <div>
        <div className="text-xs font-semibold uppercase tracking-widest mb-0.5"
             style={{ color: "var(--text-muted)" }}>{title}</div>
        <div className="text-xs" style={{ color: "var(--text-muted)" }}>{subtitle}</div>
      </div>
      <div className="text-2xl font-bold" style={{ color: readingColor }}>{reading}</div>
      <div className="space-y-1">
        <div className="h-1.5 rounded-full overflow-hidden" style={{ backgroundColor: "rgba(48,54,61,0.6)" }}>
          <div className="h-full rounded-full transition-all duration-700"
               style={{ width: `${pct}%`, backgroundColor: barColor }} />
        </div>
        <div className="text-xs" style={{ color: "var(--text-muted)" }}>{desc}</div>
      </div>
    </div>
  )
}

// ── Main Page ─────────────────────────────────────────────────

export default function QuadrantPage() {
  const { data: q, isLoading, mutate } = useSWR<MarketQuadrant>(
    "market-quadrant",
    fetchMarketQuadrant,
    { refreshInterval: 3_600_000 },
  )

  const overall = q ? OVERALL_CFG[q.overall] : null
  const swing   = q ? SWING_CFG[q.swing]     : null
  const mom     = q ? MOM_CFG[q.momentum]    : null
  const MomIcon = mom?.icon ?? ArrowUp

  return (
    <div className="max-w-4xl mx-auto space-y-6">

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold" style={{ color: "var(--text-primary)" }}>Market Quadrant</h1>
          <p className="text-xs mt-0.5" style={{ color: "var(--text-muted)" }}>
            Nifty 500 breadth analysis · Bias / Trend / Swing / Momentum · refreshes every 1 h
          </p>
        </div>
        <button onClick={() => mutate()}
                className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs"
                style={{ backgroundColor: "rgba(48,54,61,0.6)", color: "var(--text-muted)", border: "1px solid var(--border)" }}>
          <RefreshCw size={12} className={isLoading ? "animate-spin" : ""} />
          Refresh
        </button>
      </div>

      {/* Loading */}
      {isLoading && !q && (
        <div className="space-y-3">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="h-24 rounded-xl animate-pulse"
                 style={{ backgroundColor: "var(--bg-card)", border: "1px solid var(--border)" }} />
          ))}
          <p className="text-xs text-center" style={{ color: "var(--text-muted)" }}>
            Computing breadth for 500 stocks — this takes ~30s on first load…
          </p>
        </div>
      )}

      {q && overall && swing && mom && (
        <>
          {/* Overall signal banner */}
          <div className="rounded-xl p-5 flex items-center justify-between"
               style={{ backgroundColor: overall.bg, border: `1px solid ${overall.border}` }}>
            <div>
              <div className="text-xs font-semibold uppercase tracking-widest mb-1"
                   style={{ color: overall.color }}>Overall Signal</div>
              <div className="text-3xl font-bold" style={{ color: overall.color }}>
                {overall.emoji} {overall.label}
              </div>
              <div className="text-xs mt-1" style={{ color: "var(--text-muted)" }}>
                {q.overall === "INVEST"    && "3–4 of 4 quadrants bullish — deploy full capital"}
                {q.overall === "SELECTIVE" && "2 of 4 quadrants bullish — only A-grade setups"}
                {q.overall === "CASH"      && "0–1 of 4 quadrants bullish — preserve capital"}
              </div>
            </div>
            <div className="text-right space-y-1">
              <div className="text-xs" style={{ color: "var(--text-muted)" }}>52-week</div>
              <div className="flex gap-3 text-sm font-semibold">
                <span style={{ color: "var(--green)" }}>▲ {q.new_highs} highs</span>
                <span style={{ color: "var(--red)" }}>▼ {q.new_lows} lows</span>
              </div>
              <div className="text-xs" style={{ color: "var(--text-muted)" }}>
                of {q.total} stocks
              </div>
            </div>
          </div>

          {/* 4 Quadrant cards */}
          <div className="grid grid-cols-2 gap-4">

            {/* Bias */}
            <QuadCard
              title="Bias"
              subtitle="Long-term · 200-day SMA"
              reading={BIAS_CFG[q.bias].label}
              readingColor={BIAS_CFG[q.bias].color}
              value={q.pct_above_200}
              maxValue={100}
              barColor={BIAS_CFG[q.bias].color}
              desc={`${q.above_200} of ${q.total} stocks above 200-SMA (${q.pct_above_200}%)`}
            />

            {/* Trend */}
            <QuadCard
              title="Trend"
              subtitle="Medium-term · 50-day SMA"
              reading={TREND_CFG[q.trend].label}
              readingColor={TREND_CFG[q.trend].color}
              value={q.pct_above_50}
              maxValue={100}
              barColor={TREND_CFG[q.trend].color}
              desc={`${q.above_50} of ${q.total} stocks above 50-SMA (${q.pct_above_50}%)`}
            />

            {/* Swing */}
            <div className="rounded-xl p-4 space-y-3"
                 style={{ backgroundColor: "var(--bg-card)", border: "1px solid var(--border)" }}>
              <div>
                <div className="text-xs font-semibold uppercase tracking-widest mb-0.5"
                     style={{ color: "var(--text-muted)" }}>Swing</div>
                <div className="text-xs" style={{ color: "var(--text-muted)" }}>Short-term · 10-day SMA</div>
              </div>
              <div className="flex items-end gap-3">
                <div className="text-2xl font-bold" style={{ color: swing.color }}>{swing.label}</div>
                <div className="text-sm font-semibold mb-0.5" style={{ color: "var(--text-muted)" }}>
                  {q.swing_confidence} confidence
                </div>
              </div>
              {/* Confidence gauge */}
              <div className="space-y-1">
                <div className="h-1.5 rounded-full overflow-hidden" style={{ backgroundColor: "rgba(48,54,61,0.6)" }}>
                  <div className="h-full rounded-full transition-all duration-700"
                       style={{ width: `${q.pct_above_10}%`, backgroundColor: swing.color }} />
                </div>
                <div className="text-xs" style={{ color: "var(--text-muted)" }}>{swing.desc}</div>
              </div>
            </div>

            {/* Momentum */}
            <div className="rounded-xl p-4 space-y-3"
                 style={{ backgroundColor: "var(--bg-card)", border: "1px solid var(--border)" }}>
              <div>
                <div className="text-xs font-semibold uppercase tracking-widest mb-0.5"
                     style={{ color: "var(--text-muted)" }}>Momentum</div>
                <div className="text-xs" style={{ color: "var(--text-muted)" }}>Rate of change · 50-SMA breadth vs 20 sessions ago</div>
              </div>
              <div className="flex items-center gap-2">
                <MomIcon size={20} style={{ color: mom.color }} />
                <div className="text-2xl font-bold" style={{ color: mom.color }}>{mom.label}</div>
              </div>
              <div className="text-xs" style={{ color: "var(--text-muted)" }}>
                50-SMA breadth changed&nbsp;
                <strong style={{ color: mom.color }}>
                  {q.momentum_change > 0 ? "+" : ""}{q.momentum_change}%
                </strong>
                &nbsp;over the last 4 weeks
              </div>
            </div>
          </div>

          {/* Breadth waterfall */}
          <div className="rounded-xl p-5 space-y-4"
               style={{ backgroundColor: "var(--bg-card)", border: "1px solid var(--border)" }}>
            <div className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
              Breadth Waterfall — % of Nifty 500 stocks above SMA
            </div>
            <BreadthBar label="Above 200-SMA  (Bias)"  pct={q.pct_above_200} color={BIAS_CFG[q.bias].color}  />
            <BreadthBar label="Above 50-SMA   (Trend)" pct={q.pct_above_50}  color={TREND_CFG[q.trend].color} />
            <BreadthBar label="Above 10-SMA   (Swing)" pct={q.pct_above_10}  color={swing.color}              />
            <div className="flex items-center gap-6 pt-1 text-xs" style={{ color: "var(--text-muted)" }}>
              <span><span className="font-semibold" style={{ color: "var(--green)" }}>&gt;50%</span> = healthy</span>
              <span><span className="font-semibold" style={{ color: "#f59e0b" }}>30–50%</span> = caution</span>
              <span><span className="font-semibold" style={{ color: "var(--red)" }}>&lt;30%</span> = avoid</span>
            </div>
          </div>

          {/* Trading rules */}
          <div className="rounded-xl overflow-hidden" style={{ border: "1px solid var(--border)" }}>
            <div className="px-4 py-3 text-xs font-semibold uppercase tracking-widest"
                 style={{ backgroundColor: "var(--bg-card)", color: "var(--text-muted)", borderBottom: "1px solid var(--border)" }}>
              Position Sizing Rules by Signal
            </div>
            {[
              { signal: "🟢 Fully Invest",  rule: "Full position size · trade all A-grade setups · sectors HOT or WARM" },
              { signal: "🟡 Be Selective",  rule: "Half position size · only highest RS setups · skip if sector COLD" },
              { signal: "🔴 Stay in Cash",  rule: "No new positions · hold only if stop not hit · preserve capital" },
            ].map(({ signal, rule }) => (
              <div key={signal} className="flex items-center gap-4 px-4 py-3 border-t text-sm"
                   style={{ borderColor: "var(--border)" }}>
                <span className="w-36 text-xs font-semibold shrink-0" style={{ color: "var(--text-primary)" }}>{signal}</span>
                <span className="text-xs" style={{ color: "var(--text-muted)" }}>{rule}</span>
              </div>
            ))}
          </div>

          {/* Updated at */}
          <p className="text-xs text-center" style={{ color: "var(--text-muted)" }}>
            Last computed: {new Date(q.updated_at).toLocaleString("en-IN", { timeZone: "Asia/Kolkata" })} IST
          </p>
        </>
      )}
    </div>
  )
}

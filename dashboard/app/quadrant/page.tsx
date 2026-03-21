"use client"
import useSWR from "swr"
import { RefreshCw, ArrowUp, ArrowDown, Zap } from "lucide-react"
import { fetchMarketQuadrant } from "@/lib/api"
import type { MarketQuadrant } from "@/lib/types"

// ── Config ────────────────────────────────────────────────────

const OVERALL = {
  INVEST:    { label: "Fully Invest",  emoji: "🟢", color: "var(--green)",  bg: "rgba(0,196,154,0.10)",  border: "rgba(0,196,154,0.35)", desc: "3–4 quadrants bullish — deploy full capital" },
  SELECTIVE: { label: "Be Selective",  emoji: "🟡", color: "#f59e0b",       bg: "rgba(251,191,36,0.10)", border: "rgba(251,191,36,0.35)", desc: "2 quadrants bullish — only highest-RS setups, half size" },
  CASH:      { label: "Stay in Cash",  emoji: "🔴", color: "var(--red)",    bg: "rgba(255,77,77,0.08)",  border: "rgba(255,77,77,0.25)",  desc: "0–1 quadrants bullish — preserve capital, no new entries" },
}

const SWING_COLOR: Record<string, string> = {
  HOT: "var(--green)", WARM: "#f59e0b", COOL: "var(--blue)", COLD: "var(--red)",
}

// ── Helpers ───────────────────────────────────────────────────

function nnnLabel(v: number) {
  if (v > 0) return { text: `+${v}`, color: "var(--green)" }
  if (v < 0) return { text: `${v}`,  color: "var(--red)"   }
  return { text: "0", color: "var(--text-muted)" }
}

function BreadthBar({ label, pct, color, sub }: { label: string; pct: number; color: string; sub?: string }) {
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs">
        <span style={{ color: "var(--text-muted)" }}>{label}</span>
        <span style={{ color, fontWeight: 700 }}>{pct.toFixed(1)}%</span>
      </div>
      <div className="h-2 rounded-full overflow-hidden" style={{ backgroundColor: "rgba(48,54,61,0.6)" }}>
        <div className="h-full rounded-full transition-all duration-700" style={{ width: `${pct}%`, backgroundColor: color }} />
      </div>
      {sub && <div className="text-xs" style={{ color: "var(--text-muted)" }}>{sub}</div>}
    </div>
  )
}

function ConfidenceGauge({ score }: { score: number }) {
  const color = score >= 60 ? "var(--green)" : score >= 40 ? "#f59e0b" : score >= 20 ? "var(--blue)" : "var(--red)"
  const label = score >= 60 ? "HIGH" : score >= 40 ? "MEDIUM" : score >= 20 ? "LOW" : "ZERO"
  return (
    <div className="space-y-2">
      <div className="flex items-end gap-3">
        <div className="text-4xl font-bold tabular-nums" style={{ color }}>{score}</div>
        <div className="text-sm font-semibold mb-1" style={{ color }}>{label}</div>
      </div>
      <div className="relative h-3 rounded-full overflow-hidden" style={{ backgroundColor: "rgba(48,54,61,0.6)" }}>
        {/* Zone markers */}
        <div className="absolute inset-y-0 w-px" style={{ left: "20%", backgroundColor: "rgba(255,255,255,0.1)" }} />
        <div className="absolute inset-y-0 w-px" style={{ left: "40%", backgroundColor: "rgba(255,255,255,0.1)" }} />
        <div className="absolute inset-y-0 w-px" style={{ left: "60%", backgroundColor: "rgba(255,255,255,0.1)" }} />
        <div className="absolute inset-y-0 w-px" style={{ left: "80%", backgroundColor: "rgba(255,255,255,0.1)" }} />
        <div className="h-full rounded-full transition-all duration-700" style={{ width: `${score}%`, backgroundColor: color }} />
      </div>
      <div className="flex justify-between text-xs" style={{ color: "var(--text-muted)" }}>
        <span>0 — No positions</span>
        <span>100 — Full risk</span>
      </div>
    </div>
  )
}

function QuadChip({
  title, value, valueColor, sub,
}: { title: string; value: string; valueColor: string; sub: string }) {
  return (
    <div className="rounded-xl p-4 space-y-2"
         style={{ backgroundColor: "var(--bg-card)", border: "1px solid var(--border)" }}>
      <div className="text-xs font-semibold uppercase tracking-widest" style={{ color: "var(--text-muted)" }}>{title}</div>
      <div className="text-xl font-bold" style={{ color: valueColor }}>{value}</div>
      <div className="text-xs" style={{ color: "var(--text-muted)" }}>{sub}</div>
    </div>
  )
}

// ── Page ──────────────────────────────────────────────────────

export default function QuadrantPage() {
  const { data: q, isLoading, mutate } = useSWR<MarketQuadrant>(
    "market-quadrant",
    fetchMarketQuadrant,
    { refreshInterval: 3_600_000 },
  )

  const cfg     = q ? OVERALL[q.overall] : null
  const swColor = q ? SWING_COLOR[q.swing] : "var(--text-muted)"
  const MomIcon = q?.momentum === "RISING" ? ArrowUp : ArrowDown
  const momColor = q?.momentum === "RISING" ? "var(--green)" : "var(--red)"

  return (
    <div className="max-w-4xl mx-auto space-y-5">

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold" style={{ color: "var(--text-primary)" }}>Market Quadrant</h1>
          <p className="text-xs mt-0.5" style={{ color: "var(--text-muted)" }}>
            Nifty 500 breadth · Bias / Trend / Swing / Momentum · inspired by Nitin's framework · refreshes every 1 h
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
          {[...Array(4)].map((_, i) => (
            <div key={i} className="h-20 rounded-xl animate-pulse"
                 style={{ backgroundColor: "var(--bg-card)", border: "1px solid var(--border)" }} />
          ))}
          <p className="text-xs text-center" style={{ color: "var(--text-muted)" }}>
            Computing breadth across 500 stocks — first load takes ~30 s…
          </p>
        </div>
      )}

      {q && cfg && (
        <>
          {/* ── Breadth Thrust Alert ── */}
          {q.thrust_detected && (
            <div className="flex items-center gap-3 rounded-xl px-4 py-3"
                 style={{ backgroundColor: "rgba(251,191,36,0.12)", border: "1px solid rgba(251,191,36,0.4)" }}>
              <Zap size={16} style={{ color: "#f59e0b" }} />
              <div>
                <span className="text-sm font-bold" style={{ color: "#f59e0b" }}>Breadth Thrust Detected</span>
                <span className="text-xs ml-2" style={{ color: "var(--text-muted)" }}>
                  Swing breadth surged from &lt;25% to &gt;40% in 10 sessions — historically precedes strong bull runs
                </span>
              </div>
            </div>
          )}

          {/* ── Overall Signal ── */}
          <div className="rounded-xl p-5 flex items-center justify-between"
               style={{ backgroundColor: cfg.bg, border: `1px solid ${cfg.border}` }}>
            <div>
              <div className="text-xs font-semibold uppercase tracking-widest mb-1" style={{ color: cfg.color }}>
                Overall Signal
              </div>
              <div className="text-3xl font-bold" style={{ color: cfg.color }}>
                {cfg.emoji} {cfg.label}
              </div>
              <div className="text-xs mt-1" style={{ color: "var(--text-muted)" }}>{cfg.desc}</div>
            </div>
            <div className="text-right space-y-1.5">
              <div className="text-xs font-semibold" style={{ color: "var(--text-muted)" }}>
                Phase duration
              </div>
              <div className="text-2xl font-bold" style={{ color: cfg.color }}>
                {q.phase_weeks}w
              </div>
              <div className="text-xs" style={{ color: "var(--text-muted)" }}>
                {q.new_highs} highs · {q.new_lows} lows (52w)
              </div>
            </div>
          </div>

          {/* ── 4 Quadrant chips ── */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <QuadChip
              title="Bias"
              value={q.bias === "BULL" ? "Bull" : "Bear"}
              valueColor={q.bias === "BULL" ? "var(--green)" : "var(--red)"}
              sub={`${q.pct_above_200}% above 200-SMA`}
            />
            <QuadChip
              title="Trend"
              value={q.trend === "UP" ? "Uptrend" : "Downtrend"}
              valueColor={q.trend === "UP" ? "var(--green)" : "var(--red)"}
              sub={`${q.pct_above_50}% above 50-SMA · 52w NNH ${q.nnh_52w > 0 ? "+" : ""}${q.nnh_52w}`}
            />
            <QuadChip
              title="Swing"
              value={q.swing}
              valueColor={swColor}
              sub={`${q.pct_above_10}% above 10-SMA`}
            />
            <QuadChip
              title="Momentum"
              value={q.momentum === "RISING" ? "Rising" : "Falling"}
              valueColor={momColor}
              sub={`50-SMA breadth ${q.momentum_change > 0 ? "+" : ""}${q.momentum_change}% vs MA`}
            />
          </div>

          {/* ── Swing Confidence gauge + NNH ── */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="rounded-xl p-5 space-y-3"
                 style={{ backgroundColor: "var(--bg-card)", border: "1px solid var(--border)" }}>
              <div className="text-xs font-semibold uppercase tracking-widest" style={{ color: "var(--text-muted)" }}>
                Swing Confidence
              </div>
              <ConfidenceGauge score={q.swing_confidence} />
              <div className="text-xs space-y-0.5 pt-1" style={{ color: "var(--text-muted)" }}>
                <div className="flex justify-between">
                  <span>Short-term breadth (10-SMA)</span>
                  <span style={{ color: swColor }}>{Math.min(Math.round(q.pct_above_10 * 0.40), 40)}/40</span>
                </div>
                <div className="flex justify-between">
                  <span>20-day NNH</span>
                  <span style={{ color: q.nnh_20 > 0 ? "var(--green)" : "var(--red)" }}>{q.nnh_20 > 0 ? "+20" : "0"}/20</span>
                </div>
                <div className="flex justify-between">
                  <span>65-day NNH</span>
                  <span style={{ color: q.nnh_65 > 0 ? "var(--green)" : "var(--red)" }}>{q.nnh_65 > 0 ? "+20" : "0"}/20</span>
                </div>
                <div className="flex justify-between">
                  <span>Momentum</span>
                  <span style={{ color: momColor }}>{q.momentum === "RISING" ? "+20" : "0"}/20</span>
                </div>
              </div>
            </div>

            <div className="rounded-xl p-5 space-y-3"
                 style={{ backgroundColor: "var(--bg-card)", border: "1px solid var(--border)" }}>
              <div className="text-xs font-semibold uppercase tracking-widest" style={{ color: "var(--text-muted)" }}>
                Net New Highs (NNH)
              </div>
              <div className="text-xs" style={{ color: "var(--text-muted)" }}>
                Highs minus lows at each lookback. Positive = more stocks making highs than lows.
              </div>
              {([
                ["20-day NNH",    q.nnh_20  ],
                ["65-day NNH",    q.nnh_65  ],
                ["52-week NNH",   q.nnh_52w ],
              ] as [string, number][]).map(([label, val]) => {
                const l = nnnLabel(val)
                return (
                  <div key={label} className="flex items-center justify-between py-2 border-t"
                       style={{ borderColor: "var(--border)" }}>
                    <span className="text-sm" style={{ color: "var(--text-primary)" }}>{label}</span>
                    <span className="text-sm font-bold tabular-nums" style={{ color: l.color }}>{l.text}</span>
                  </div>
                )
              })}
              <div className="text-xs pt-1" style={{ color: "var(--text-muted)" }}>
                52-week NNH must be positive for Trend to be classified as Uptrend (Nitin's rule)
              </div>
            </div>
          </div>

          {/* ── Breadth Waterfall ── */}
          <div className="rounded-xl p-5 space-y-4"
               style={{ backgroundColor: "var(--bg-card)", border: "1px solid var(--border)" }}>
            <div className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
              Breadth Waterfall — % of Nifty 500 above SMA
            </div>
            <BreadthBar
              label="200-SMA — Bias"
              pct={q.pct_above_200}
              color={q.bias === "BULL" ? "var(--green)" : "var(--red)"}
              sub={`${q.above_200} of ${q.total} stocks · threshold: 50%`}
            />
            <BreadthBar
              label="50-SMA — Trend"
              pct={q.pct_above_50}
              color={q.trend === "UP" ? "var(--green)" : "var(--red)"}
              sub={`${q.above_50} of ${q.total} stocks · needs 50% + positive 52w NNH`}
            />
            <BreadthBar
              label="10-SMA — Swing"
              pct={q.pct_above_10}
              color={swColor}
              sub={`${q.above_10} of ${q.total} stocks · HOT≥70 · WARM≥50 · COOL≥30 · COLD<30`}
            />
            <div className="flex gap-5 text-xs pt-1" style={{ color: "var(--text-muted)" }}>
              <span><strong style={{ color: "var(--green)" }}>&gt;50%</strong> — healthy</span>
              <span><strong style={{ color: "#f59e0b" }}>30–50%</strong> — caution</span>
              <span><strong style={{ color: "var(--red)" }}>&lt;30%</strong> — weak</span>
            </div>
          </div>

          {/* ── What Would Change This ── */}
          {q.to_upgrade.length > 0 && (
            <div className="rounded-xl overflow-hidden"
                 style={{ border: "1px solid var(--border)" }}>
              <div className="px-4 py-3 text-xs font-semibold uppercase tracking-widest"
                   style={{ backgroundColor: "var(--bg-card)", color: "var(--text-muted)", borderBottom: "1px solid var(--border)" }}>
                What Would Change This Signal
              </div>
              {q.to_upgrade.map((block) => (
                <div key={block.to}>
                  <div className="px-4 py-2 text-xs font-semibold"
                       style={{ backgroundColor: "rgba(48,54,61,0.3)", color: OVERALL[block.to as keyof typeof OVERALL]?.color ?? "var(--text-primary)" }}>
                    To reach → {OVERALL[block.to as keyof typeof OVERALL]?.emoji} {block.to}
                  </div>
                  {block.conditions.map((c) => (
                    <div key={c.metric} className="flex items-center gap-4 px-4 py-3 border-t text-xs"
                         style={{ borderColor: "var(--border)" }}>
                      <span className="w-52 shrink-0" style={{ color: "var(--text-primary)" }}>{c.metric}</span>
                      <div className="flex-1 space-y-1">
                        <div className="flex justify-between" style={{ color: "var(--text-muted)" }}>
                          <span>Now: <strong style={{ color: "var(--red)" }}>{c.current.toFixed(1)}</strong></span>
                          <span>Needs: <strong style={{ color: "var(--green)" }}>{c.needs.toFixed(1)}</strong></span>
                          <span>Gap: <strong style={{ color: "#f59e0b" }}>+{c.gap.toFixed(1)}</strong></span>
                        </div>
                        <div className="h-1.5 rounded-full overflow-hidden" style={{ backgroundColor: "rgba(48,54,61,0.6)" }}>
                          <div className="h-full rounded-full"
                               style={{ width: `${Math.min(c.current / c.needs * 100, 100)}%`, backgroundColor: "var(--blue)" }} />
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              ))}
            </div>
          )}

          {/* ── Position sizing rules ── */}
          <div className="rounded-xl overflow-hidden" style={{ border: "1px solid var(--border)" }}>
            <div className="px-4 py-3 text-xs font-semibold uppercase tracking-widest"
                 style={{ backgroundColor: "var(--bg-card)", color: "var(--text-muted)", borderBottom: "1px solid var(--border)" }}>
              Position Sizing by Signal
            </div>
            {([
              ["INVEST",    "🟢 Fully Invest",  "Full size · trade all A-grade setups · sectors HOT or WARM"],
              ["SELECTIVE", "🟡 Be Selective",  "Half size · only highest RS score · skip if sector COLD or WEAK"],
              ["CASH",      "🔴 Stay in Cash",  "No new entries · hold only if stop not hit · capital preservation"],
            ] as [string, string, string][]).map(([key, signal, rule]) => (
              <div key={key} className="flex items-center gap-4 px-4 py-3 border-t text-xs"
                   style={{ borderColor: "var(--border)", backgroundColor: key === q.overall ? OVERALL[key as keyof typeof OVERALL].bg : "transparent" }}>
                <span className="w-36 font-semibold shrink-0"
                      style={{ color: OVERALL[key as keyof typeof OVERALL].color }}>{signal}</span>
                <span style={{ color: "var(--text-muted)" }}>{rule}</span>
                {key === q.overall && (
                  <span className="ml-auto text-xs font-bold px-2 py-0.5 rounded-full"
                        style={{ backgroundColor: OVERALL[key as keyof typeof OVERALL].border, color: OVERALL[key as keyof typeof OVERALL].color }}>
                    ACTIVE
                  </span>
                )}
              </div>
            ))}
          </div>

          <p className="text-xs text-center" style={{ color: "var(--text-muted)" }}>
            Last computed: {new Date(q.updated_at).toLocaleString("en-IN", { timeZone: "Asia/Kolkata" })} IST
            · cached 1 h · {q.total} stocks analysed
          </p>
        </>
      )}
    </div>
  )
}

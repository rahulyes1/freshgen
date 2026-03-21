"use client"
import { TrendingUp, Zap, ChevronUp, AlertTriangle, BarChart } from "lucide-react"
import type { Setup } from "@/lib/types"
import { cn, formatINR, patternColor } from "@/lib/utils"

interface Props {
  setup: Setup
  onAddPosition?: (s: Setup) => void
}

export default function SetupCard({ setup, onAddPosition }: Props) {
  const isEP    = setup.pattern === "EP"
  const isVCP   = setup.pattern === "VCP"
  const riskPct = setup.risk_pct.toFixed(1)
  const volRatio = setup.volume_ratio.toFixed(1)
  const ticker  = setup.ticker.replace(".NS", "")
  const rsRank  = setup.rs_rank ?? 0

  return (
    <div
      className="rounded-xl border p-4 flex flex-col gap-3 transition-all hover:scale-[1.01]"
      style={{ backgroundColor: "var(--bg-card)", borderColor: "var(--border)" }}
    >
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <div className="text-lg font-bold tracking-wide" style={{ color: "var(--text-primary)" }}>
            {ticker}
          </div>
          <div className="text-xs mt-0.5" style={{ color: "var(--text-muted)" }}>
            {setup.date}
          </div>
        </div>
        <div className="flex flex-col items-end gap-1">
          <span className={cn("text-xs font-semibold px-2.5 py-1 rounded-full border", patternColor(setup.pattern))}>
            {isEP ? <Zap size={10} className="inline mr-1" /> : isVCP ? <BarChart size={10} className="inline mr-1" /> : <TrendingUp size={10} className="inline mr-1" />}
            {setup.pattern}
          </span>
          {rsRank > 0 && (
            <span className="text-xs px-1.5 py-0.5 rounded"
                  style={{
                    backgroundColor: rsRank >= 80 ? "rgba(0,196,154,0.15)" : rsRank >= 60 ? "rgba(77,159,255,0.15)" : "rgba(48,54,61,0.5)",
                    color: rsRank >= 80 ? "var(--green)" : rsRank >= 60 ? "var(--blue)" : "var(--text-muted)",
                  }}>
              RS {rsRank}
            </span>
          )}
        </div>
      </div>

      {/* Entry / Stop / Risk row */}
      <div className="grid grid-cols-3 gap-2">
        <Stat label="Entry" value={`₹${setup.entry_price.toFixed(2)}`} color="var(--green)" />
        <Stat label="Stop"  value={`₹${setup.stop_price.toFixed(2)}`}  color="var(--red)" />
        <Stat label="Risk"  value={`${riskPct}%`}                       color="var(--text-primary)" />
      </div>

      {/* Volume bar */}
      <div>
        <div className="flex justify-between text-xs mb-1" style={{ color: "var(--text-muted)" }}>
          <span>Volume surge</span>
          <span className="font-semibold" style={{ color: "var(--blue)" }}>{volRatio}×</span>
        </div>
        <div className="h-1.5 rounded-full overflow-hidden" style={{ backgroundColor: "var(--border)" }}>
          <div
            className="h-full rounded-full transition-all"
            style={{
              width: `${Math.min((setup.volume_ratio / 5) * 100, 100)}%`,
              backgroundColor: setup.volume_ratio >= 2 ? "var(--green)" : "var(--blue)",
            }}
          />
        </div>
      </div>

      {/* Meta tags */}
      <div className="flex flex-wrap gap-1.5 text-xs" style={{ color: "var(--text-muted)" }}>
        <Tag label={`52W dist ${setup.distance_52w_pct.toFixed(1)}%`} />
        {isEP && setup.gap_pct > 0 && <Tag label={`Gap +${setup.gap_pct.toFixed(1)}%`} highlight />}
        {!isEP && setup.base_weeks !== "-" && <Tag label={`Base ${setup.base_weeks}w`} />}
        {setup.near_earnings && (
          <span className="flex items-center gap-1 px-2 py-0.5 rounded-full text-xs"
                style={{ backgroundColor: "rgba(255,180,0,0.12)", color: "rgb(255,180,0)", border: "1px solid rgba(255,180,0,0.3)" }}>
            <AlertTriangle size={9} />Earnings soon
          </span>
        )}
        {setup.has_announcement && (
          <span className="flex items-center gap-1 px-2 py-0.5 rounded-full text-xs"
                style={{ backgroundColor: "rgba(255,140,0,0.12)", color: "rgb(255,140,0)", border: "1px solid rgba(255,140,0,0.3)" }}>
            📢 Result/Concall
          </span>
        )}
        {setup.eps_yoy > 20 && (
          <span className="px-2 py-0.5 rounded-full text-xs"
                style={{ backgroundColor: "rgba(0,196,154,0.12)", color: "var(--green)", border: "1px solid rgba(0,196,154,0.3)" }}>
            EPS +{setup.eps_yoy.toFixed(0)}%YoY
          </span>
        )}
        {setup.strong_catalyst && (
          <span className="px-2 py-0.5 rounded-full text-xs font-semibold"
                style={{ backgroundColor: "rgba(255,200,0,0.12)", color: "rgb(255,200,0)", border: "1px solid rgba(255,200,0,0.4)" }}>
            ⭐ Strong catalyst
          </span>
        )}
      </div>

      {/* Sizing */}
      <div className="rounded-lg px-3 py-2 flex justify-between text-xs"
           style={{ backgroundColor: "rgba(0,196,154,0.06)", border: "1px solid rgba(0,196,154,0.15)" }}>
        <div>
          <div style={{ color: "var(--text-muted)" }}>Shares (1% risk)</div>
          <div className="font-semibold" style={{ color: "var(--green)" }}>
            {setup.position_size_shares.toLocaleString("en-IN")}
          </div>
        </div>
        <div className="text-right">
          <div style={{ color: "var(--text-muted)" }}>Position value</div>
          <div className="font-semibold" style={{ color: "var(--text-primary)" }}>
            {formatINR(setup.position_value)}
          </div>
        </div>
      </div>

      {/* Add position button */}
      {onAddPosition && (
        <button
          onClick={() => onAddPosition(setup)}
          className="w-full text-xs font-semibold py-2 rounded-lg transition-colors"
          style={{ backgroundColor: "rgba(0,196,154,0.15)", color: "var(--green)", border: "1px solid rgba(0,196,154,0.3)" }}
        >
          + Add to Positions
        </button>
      )}
    </div>
  )
}

function Stat({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div className="rounded-lg px-2.5 py-2 text-center" style={{ backgroundColor: "rgba(48,54,61,0.5)" }}>
      <div className="text-xs mb-0.5" style={{ color: "var(--text-muted)" }}>{label}</div>
      <div className="text-sm font-bold" style={{ color }}>{value}</div>
    </div>
  )
}

function Tag({ label, highlight = false }: { label: string; highlight?: boolean }) {
  return (
    <span className="px-2 py-0.5 rounded-full text-xs"
          style={{
            backgroundColor: highlight ? "rgba(77,159,255,0.1)" : "rgba(48,54,61,0.6)",
            color: highlight ? "var(--blue)" : "var(--text-muted)",
            border: `1px solid ${highlight ? "rgba(77,159,255,0.3)" : "var(--border)"}`,
          }}>
      {label}
    </span>
  )
}

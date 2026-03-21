"use client"
import {
  ComposedChart, Area, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine,
} from "recharts"
import type { EquityPoint } from "@/lib/types"
import { formatINR } from "@/lib/utils"

interface Props {
  data: EquityPoint[]
  initialCapital?: number
}

interface DrawdownPoint {
  date: string
  value: number
  drawdown: number
}

function buildDrawdown(data: EquityPoint[], initial: number): DrawdownPoint[] {
  let peak = initial
  return data.map(p => {
    if (p.value > peak) peak = p.value
    const dd = peak > 0 ? ((p.value - peak) / peak) * 100 : 0
    return { date: p.date, value: p.value, drawdown: dd }
  })
}

const CustomTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null
  const val = payload[0]?.value
  const dd  = payload[1]?.value
  return (
    <div className="rounded-lg px-3 py-2 text-xs"
         style={{ backgroundColor: "var(--bg-card)", border: "1px solid var(--border)" }}>
      <div style={{ color: "var(--text-muted)" }}>{label}</div>
      {val !== undefined && (
        <div className="font-bold" style={{ color: "var(--green)" }}>{formatINR(val)}</div>
      )}
      {dd !== undefined && (
        <div style={{ color: "var(--red)" }}>{dd.toFixed(1)}% drawdown</div>
      )}
    </div>
  )
}

export default function EquityCurveChart({ data, initialCapital = 1_000_000 }: Props) {
  if (!data || data.length === 0) {
    return (
      <div className="flex items-center justify-center h-64 text-sm" style={{ color: "var(--text-muted)" }}>
        No equity data yet. Run a backtest first.
      </div>
    )
  }

  const chartData = buildDrawdown(data, initialCapital)

  // Sample to ~300 points for performance
  const step = Math.max(1, Math.floor(chartData.length / 300))
  const sampled = chartData.filter((_, i) => i % step === 0 || i === chartData.length - 1)

  const maxVal = Math.max(...sampled.map(d => d.value))
  const minVal = Math.min(...sampled.map(d => d.value))

  return (
    <div className="w-full">
      {/* Equity curve */}
      <div className="h-56">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={sampled} margin={{ top: 4, right: 16, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id="eqGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%"  stopColor="#00c49a" stopOpacity={0.25} />
                <stop offset="95%" stopColor="#00c49a" stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#30363d" strokeOpacity={0.5} />
            <XAxis dataKey="date" tick={{ fontSize: 10, fill: "#8b949e" }}
                   tickFormatter={v => v.slice(2, 7)} interval="preserveStartEnd" />
            <YAxis tick={{ fontSize: 10, fill: "#8b949e" }}
                   tickFormatter={v => formatINR(v)} width={72}
                   domain={[minVal * 0.97, maxVal * 1.02]} />
            <Tooltip content={<CustomTooltip />} />
            <ReferenceLine y={initialCapital} stroke="#484f58" strokeDasharray="4 4" />
            <Area type="monotone" dataKey="value" stroke="#00c49a" strokeWidth={1.8}
                  fill="url(#eqGradient)" dot={false} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      {/* Drawdown */}
      <div className="h-24 mt-1">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={sampled} margin={{ top: 0, right: 16, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id="ddGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%"  stopColor="#ff4d4d" stopOpacity={0.4} />
                <stop offset="95%" stopColor="#ff4d4d" stopOpacity={0.05} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#30363d" strokeOpacity={0.5} />
            <XAxis dataKey="date" hide />
            <YAxis tick={{ fontSize: 9, fill: "#8b949e" }} width={72}
                   tickFormatter={v => `${v.toFixed(0)}%`} />
            <Tooltip content={<CustomTooltip />} />
            <Area type="monotone" dataKey="drawdown" stroke="#ff4d4d" strokeWidth={1}
                  fill="url(#ddGradient)" dot={false} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}

"use client"
import { useEffect, useState } from "react"
import { X, TrendingUp, TrendingDown } from "lucide-react"
import {
  ComposedChart, Bar, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine,
} from "recharts"
import { fetchChart } from "@/lib/api"
import type { ChartBar } from "@/lib/types"

interface Props {
  ticker: string
  entryPrice?: number
  stopPrice?: number
  onClose: () => void
}

const CustomBar = (props: any) => {
  const { x, y, width, height, open, close } = props
  const bullish = close >= open
  const color   = bullish ? "#00c49a" : "#ff4d4d"
  const barY    = bullish ? y : y + height
  const barH    = Math.abs(height) || 1
  return <rect x={x} y={barY} width={Math.max(width - 1, 1)} height={barH} fill={color} opacity={0.85} />
}

const CustomTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null
  const d = payload[0]?.payload as ChartBar
  if (!d) return null
  const bullish = d.close >= d.open
  return (
    <div className="rounded-lg px-3 py-2 text-xs space-y-0.5"
         style={{ backgroundColor: "var(--bg-card)", border: "1px solid var(--border)" }}>
      <div style={{ color: "var(--text-muted)" }}>{d.date}</div>
      <div className="grid grid-cols-2 gap-x-3">
        <span style={{ color: "var(--text-muted)" }}>O</span>
        <span style={{ color: "var(--text-primary)" }}>₹{d.open}</span>
        <span style={{ color: "var(--text-muted)" }}>H</span>
        <span style={{ color: "var(--green)" }}>₹{d.high}</span>
        <span style={{ color: "var(--text-muted)" }}>L</span>
        <span style={{ color: "var(--red)" }}>₹{d.low}</span>
        <span style={{ color: "var(--text-muted)" }}>C</span>
        <span className="font-bold" style={{ color: bullish ? "var(--green)" : "var(--red)" }}>₹{d.close}</span>
      </div>
      {d.ema10 && <div style={{ color: "#a78bfa" }}>EMA10: ₹{d.ema10}</div>}
      {d.sma50  && <div style={{ color: "#60a5fa" }}>SMA50: ₹{d.sma50}</div>}
      <div style={{ color: "var(--text-muted)" }}>Vol: {(d.volume / 1_000_000).toFixed(2)}M</div>
    </div>
  )
}

export default function StockChartModal({ ticker, entryPrice, stopPrice, onClose }: Props) {
  const [bars,    setBars]    = useState<ChartBar[]>([])
  const [loading, setLoading] = useState(true)
  const [error,   setError]   = useState<string | null>(null)
  const [days,    setDays]    = useState(120)

  const symbol = ticker.replace(".NS", "")
  const last   = bars[bars.length - 1]
  const bullish = last && last.close >= bars[0]?.close

  useEffect(() => {
    setLoading(true)
    setError(null)
    fetchChart(ticker, days)
      .then(r => setBars(r.bars))
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [ticker, days])

  // Build chart data — use close for OHLC bar height calculation
  const chartData = bars.map(b => ({
    ...b,
    // For ComposedBar: use high as the bar top, low as base
    barBase:   b.low,
    barHeight: b.high - b.low,
    bodyBase:  Math.min(b.open, b.close),
    bodyHeight: Math.abs(b.close - b.open),
  }))

  const prices = bars.map(b => b.close)
  const minP = Math.min(...prices) * 0.98
  const maxP = Math.max(...prices) * 1.02

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4"
         style={{ backgroundColor: "rgba(0,0,0,0.7)" }}
         onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="w-full max-w-4xl rounded-2xl shadow-2xl flex flex-col"
           style={{ backgroundColor: "var(--bg-card)", border: "1px solid var(--border)", maxHeight: "90vh" }}>

        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b"
             style={{ borderColor: "var(--border)" }}>
          <div className="flex items-center gap-3">
            <div>
              <div className="text-lg font-bold" style={{ color: "var(--text-primary)" }}>{symbol}</div>
              {last && (
                <div className="flex items-center gap-2 text-xs mt-0.5">
                  <span className="font-semibold text-sm"
                        style={{ color: bullish ? "var(--green)" : "var(--red)" }}>
                    ₹{last.close}
                  </span>
                  {bullish
                    ? <TrendingUp size={12} color="var(--green)" />
                    : <TrendingDown size={12} color="var(--red)" />}
                  {last.ema10 && (
                    <span style={{ color: "var(--text-muted)" }}>
                      EMA10: ₹{last.ema10}
                      {last.close > last.ema10
                        ? <span style={{ color: "var(--green)" }}> ↑</span>
                        : <span style={{ color: "var(--red)" }}> ↓</span>}
                    </span>
                  )}
                </div>
              )}
            </div>
          </div>
          <div className="flex items-center gap-3">
            {/* Period selector */}
            <div className="flex gap-1">
              {[60, 120, 200].map(d => (
                <button key={d} onClick={() => setDays(d)}
                        className="px-2.5 py-1 rounded-lg text-xs transition-all"
                        style={{
                          backgroundColor: days === d ? "rgba(0,196,154,0.2)" : "rgba(48,54,61,0.5)",
                          color:           days === d ? "var(--green)" : "var(--text-muted)",
                          border:          days === d ? "1px solid rgba(0,196,154,0.4)" : "1px solid var(--border)",
                        }}>
                  {d}d
                </button>
              ))}
            </div>
            <button onClick={onClose} className="p-1 rounded hover:opacity-70"
                    style={{ color: "var(--text-muted)" }}>
              <X size={16} />
            </button>
          </div>
        </div>

        {/* Chart */}
        <div className="flex-1 p-4 overflow-auto">
          {loading && (
            <div className="flex items-center justify-center h-64 text-sm"
                 style={{ color: "var(--text-muted)" }}>
              Loading chart…
            </div>
          )}
          {error && (
            <div className="flex items-center justify-center h-64 text-sm"
                 style={{ color: "var(--red)" }}>
              {error}
            </div>
          )}
          {!loading && !error && bars.length > 0 && (
            <>
              {/* Price chart */}
              <div className="h-72">
                <ResponsiveContainer width="100%" height="100%">
                  <ComposedChart data={chartData} margin={{ top: 4, right: 12, left: 0, bottom: 0 }}>
                    <defs>
                      <linearGradient id="chartGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%"  stopColor="#00c49a" stopOpacity={0.1} />
                        <stop offset="95%" stopColor="#00c49a" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#30363d" strokeOpacity={0.5} />
                    <XAxis dataKey="date" tick={{ fontSize: 9, fill: "#8b949e" }}
                           tickFormatter={v => v.slice(5)} interval="preserveStartEnd" />
                    <YAxis tick={{ fontSize: 9, fill: "#8b949e" }} width={65}
                           tickFormatter={v => `₹${v.toLocaleString("en-IN")}`}
                           domain={[minP, maxP]} />
                    <Tooltip content={<CustomTooltip />} />

                    {/* Entry price line */}
                    {entryPrice && (
                      <ReferenceLine y={entryPrice} stroke="#00c49a" strokeDasharray="4 3"
                                     label={{ value: `Entry ₹${entryPrice}`, fill: "#00c49a", fontSize: 9, position: "insideTopRight" }} />
                    )}
                    {/* Stop price line */}
                    {stopPrice && (
                      <ReferenceLine y={stopPrice} stroke="#ff4d4d" strokeDasharray="4 3"
                                     label={{ value: `Stop ₹${stopPrice}`, fill: "#ff4d4d", fontSize: 9, position: "insideBottomRight" }} />
                    )}

                    {/* OHLC candle body (bodyBase + bodyHeight) */}
                    <Bar dataKey="bodyHeight" stackId="candle" fill="transparent"
                         shape={(props: any) => <CustomBar {...props} open={props.payload.open} close={props.payload.close} />} />

                    {/* Moving averages */}
                    <Line type="monotone" dataKey="ema10" stroke="#a78bfa" dot={false} strokeWidth={1.2} connectNulls />
                    <Line type="monotone" dataKey="sma50"  stroke="#60a5fa" dot={false} strokeWidth={1}   connectNulls />
                  </ComposedChart>
                </ResponsiveContainer>
              </div>

              {/* Volume chart */}
              <div className="h-20 mt-1">
                <ResponsiveContainer width="100%" height="100%">
                  <ComposedChart data={chartData} margin={{ top: 0, right: 12, left: 0, bottom: 0 }}>
                    <XAxis dataKey="date" hide />
                    <YAxis tick={{ fontSize: 8, fill: "#8b949e" }} width={65}
                           tickFormatter={v => `${(v / 1_000_000).toFixed(0)}M`} />
                    <CartesianGrid strokeDasharray="3 3" stroke="#30363d" strokeOpacity={0.3} />
                    <Bar dataKey="volume" fill="#4d9fff" opacity={0.5} />
                  </ComposedChart>
                </ResponsiveContainer>
              </div>

              {/* Legend */}
              <div className="flex gap-4 mt-2 text-xs" style={{ color: "var(--text-muted)" }}>
                <span className="flex items-center gap-1.5">
                  <span className="w-4 h-0.5 inline-block" style={{ backgroundColor: "#a78bfa" }} />EMA 10
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="w-4 h-0.5 inline-block" style={{ backgroundColor: "#60a5fa" }} />SMA 50
                </span>
                {entryPrice && (
                  <span className="flex items-center gap-1.5">
                    <span className="w-4 h-0 border-t border-dashed inline-block" style={{ borderColor: "#00c49a" }} />Entry
                  </span>
                )}
                {stopPrice && (
                  <span className="flex items-center gap-1.5">
                    <span className="w-4 h-0 border-t border-dashed inline-block" style={{ borderColor: "#ff4d4d" }} />Stop
                  </span>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}

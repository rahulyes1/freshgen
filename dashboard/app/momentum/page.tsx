"use client"
import { useState } from "react"
import { Rocket, RefreshCw, TrendingUp, TrendingDown, Copy, Check, BarChart2 } from "lucide-react"
import useSWR from "swr"
import { fetchMomentum } from "@/lib/api"
import type { MomentumLeader } from "@/lib/types"
import StockChartModal from "@/components/setups/StockChartModal"

export default function MomentumPage() {
  const { data, error, isLoading, mutate } = useSWR("momentum", fetchMomentum, { refreshInterval: 120_000 })
  const [copied, setCopied] = useState(false)
  const [chartTicker, setChartTicker] = useState<string | null>(null)
  const [sortKey, setSortKey] = useState<"rs_rank" | "distance_52w_pct" | "volume_ratio">("rs_rank")
  const [sortAsc, setSortAsc] = useState(false)

  const leaders = data?.leaders ?? []

  const sorted = [...leaders].sort((a, b) => {
    const diff = (a[sortKey] ?? 0) - (b[sortKey] ?? 0)
    return sortAsc ? diff : -diff
  })

  const handleSort = (key: typeof sortKey) => {
    if (sortKey === key) setSortAsc(!sortAsc)
    else { setSortKey(key); setSortAsc(false) }
  }

  const copyForTV = () => {
    const tickers = [...new Set(sorted.map(s => "NSE:" + s.ticker.replace(".NS", "")))]
    navigator.clipboard.writeText(tickers.join(","))
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const SortIcon = ({ col }: { col: typeof sortKey }) => {
    if (sortKey !== col) return null
    return sortAsc
      ? <TrendingUp size={10} className="inline ml-0.5" />
      : <TrendingDown size={10} className="inline ml-0.5" />
  }

  return (
    <div className="max-w-7xl mx-auto space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold flex items-center gap-2" style={{ color: "var(--text-primary)" }}>
            <Rocket size={20} color="var(--green)" />
            Momentum Leaders
          </h1>
          <p className="text-xs mt-0.5" style={{ color: "var(--text-muted)" }}>
            Top RS stocks above 50-SMA &middot; {leaders.length} stocks
            {data?.cached && <span className="ml-1" style={{ color: "var(--blue)" }}>&middot; cached</span>}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {sorted.length > 0 && (
            <button onClick={copyForTV}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs transition-colors"
                    style={{ backgroundColor: copied ? "rgba(0,196,154,0.2)" : "rgba(48,54,61,0.6)", color: copied ? "var(--green)" : "var(--text-muted)", border: `1px solid ${copied ? "rgba(0,196,154,0.4)" : "var(--border)"}` }}>
              {copied ? <Check size={12} /> : <Copy size={12} />}
              {copied ? "Copied!" : "TradingView"}
            </button>
          )}
          <button onClick={() => mutate()}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs transition-colors"
                  style={{ backgroundColor: "rgba(48,54,61,0.6)", color: "var(--text-muted)", border: "1px solid var(--border)" }}>
            <RefreshCw size={12} className={isLoading ? "animate-spin" : ""} />
            {isLoading ? "Loading..." : "Refresh"}
          </button>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="flex items-center gap-2 px-4 py-3 rounded-xl text-sm"
             style={{ backgroundColor: "rgba(255,77,77,0.08)", border: "1px solid rgba(255,77,77,0.2)", color: "var(--red)" }}>
          API offline — run a scan first to populate momentum leaders.
        </div>
      )}

      {/* Loading skeleton */}
      {isLoading && leaders.length === 0 && (
        <div className="space-y-2">
          {Array.from({ length: 10 }).map((_, i) => (
            <div key={i} className="rounded-lg h-12 animate-pulse"
                 style={{ backgroundColor: "var(--bg-card)", border: "1px solid var(--border)" }} />
          ))}
        </div>
      )}

      {/* Empty state */}
      {!isLoading && leaders.length === 0 && !error && (
        <div className="flex items-center justify-center h-64 text-sm rounded-xl"
             style={{ backgroundColor: "var(--bg-card)", border: "1px solid var(--border)", color: "var(--text-muted)" }}>
          No momentum data yet. Run a scan to compute momentum leaders.
        </div>
      )}

      {/* Table */}
      {sorted.length > 0 && (
        <div className="rounded-xl overflow-hidden" style={{ border: "1px solid var(--border)" }}>
          <table className="w-full text-xs">
            <thead>
              <tr style={{ backgroundColor: "rgba(48,54,61,0.5)" }}>
                <th className="text-left px-4 py-2.5 font-medium" style={{ color: "var(--text-muted)" }}>#</th>
                <th className="text-left px-4 py-2.5 font-medium" style={{ color: "var(--text-muted)" }}>Ticker</th>
                <th className="text-right px-4 py-2.5 font-medium" style={{ color: "var(--text-muted)" }}>Price</th>
                <th className="text-right px-4 py-2.5 font-medium cursor-pointer select-none" style={{ color: "var(--text-muted)" }}
                    onClick={() => handleSort("rs_rank")}>
                  RS Rank <SortIcon col="rs_rank" />
                </th>
                <th className="text-right px-4 py-2.5 font-medium cursor-pointer select-none" style={{ color: "var(--text-muted)" }}
                    onClick={() => handleSort("distance_52w_pct")}>
                  52W Dist <SortIcon col="distance_52w_pct" />
                </th>
                <th className="text-right px-4 py-2.5 font-medium cursor-pointer select-none" style={{ color: "var(--text-muted)" }}
                    onClick={() => handleSort("volume_ratio")}>
                  Vol Ratio <SortIcon col="volume_ratio" />
                </th>
                <th className="text-center px-4 py-2.5 font-medium" style={{ color: "var(--text-muted)" }}>50-SMA</th>
                <th className="text-center px-4 py-2.5 font-medium" style={{ color: "var(--text-muted)" }}>200-SMA</th>
                <th className="text-left px-4 py-2.5 font-medium" style={{ color: "var(--text-muted)" }}>Sector</th>
                <th className="px-4 py-2.5 font-medium" style={{ color: "var(--text-muted)" }}></th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((s, i) => {
                const symbol = s.ticker.replace(".NS", "")
                return (
                  <tr key={s.ticker}
                      className="transition-colors hover:bg-white/[0.02]"
                      style={{ borderTop: "1px solid var(--border)" }}>
                    <td className="px-4 py-2.5 font-mono" style={{ color: "var(--text-muted)" }}>{i + 1}</td>
                    <td className="px-4 py-2.5">
                      <span className="font-bold" style={{ color: "var(--text-primary)" }}>{symbol}</span>
                    </td>
                    <td className="px-4 py-2.5 text-right font-mono" style={{ color: "var(--text-primary)" }}>
                      {s.close.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                    </td>
                    <td className="px-4 py-2.5 text-right">
                      <span className="px-2 py-0.5 rounded-full text-xs font-bold"
                            style={{
                              backgroundColor: s.rs_rank >= 90 ? "rgba(0,196,154,0.15)" : s.rs_rank >= 75 ? "rgba(77,159,255,0.15)" : "rgba(48,54,61,0.5)",
                              color: s.rs_rank >= 90 ? "var(--green)" : s.rs_rank >= 75 ? "var(--blue)" : "var(--text-muted)",
                            }}>
                        {s.rs_rank}
                      </span>
                    </td>
                    <td className="px-4 py-2.5 text-right font-mono" style={{ color: s.distance_52w_pct <= 10 ? "var(--green)" : "var(--text-muted)" }}>
                      {s.distance_52w_pct.toFixed(1)}%
                    </td>
                    <td className="px-4 py-2.5 text-right font-mono" style={{ color: s.volume_ratio >= 1.5 ? "var(--green)" : "var(--text-muted)" }}>
                      {s.volume_ratio.toFixed(1)}x
                    </td>
                    <td className="px-4 py-2.5 text-center">
                      <span className="inline-block w-2 h-2 rounded-full" style={{ backgroundColor: s.above_sma50 ? "var(--green)" : "var(--red)" }} />
                    </td>
                    <td className="px-4 py-2.5 text-center">
                      <span className="inline-block w-2 h-2 rounded-full" style={{ backgroundColor: s.above_sma200 ? "var(--green)" : "var(--red)" }} />
                    </td>
                    <td className="px-4 py-2.5 text-xs" style={{ color: "var(--text-muted)" }}>
                      {s.sector || "—"}
                    </td>
                    <td className="px-4 py-2.5">
                      <button onClick={() => setChartTicker(s.ticker)}
                              className="p-1.5 rounded-lg transition-opacity opacity-70 hover:opacity-100"
                              style={{ backgroundColor: "rgba(77,159,255,0.15)", color: "var(--blue)", border: "1px solid rgba(77,159,255,0.3)" }}
                              title="View chart">
                        <BarChart2 size={12} />
                      </button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      {chartTicker && (
        <StockChartModal
          ticker={chartTicker}
          onClose={() => setChartTicker(null)}
        />
      )}
    </div>
  )
}

"use client"
import { useState } from "react"
import { RefreshCw, AlertCircle, Zap, TrendingUp, BarChart2, Database, TrendingDown, BarChart, Clock, Activity, Copy, Check } from "lucide-react"
import { useSetups } from "@/hooks/useSetups"
import { usePositions } from "@/hooks/usePositions"
import SetupCard from "@/components/setups/SetupCard"
import StockChartModal from "@/components/setups/StockChartModal"
import AddPositionModal from "@/components/positions/AddPositionModal"
import type { Setup } from "@/lib/types"
import useSWR from "swr"
import { fetchHealth } from "@/lib/api"

export default function SetupsPage() {
  const { setups, meta, error, isLoading, refresh } = useSetups("nifty500")
  const { add } = usePositions()
  const [addSetup,   setAddSetup]   = useState<Setup | null>(null)
  const [chartSetup, setChartSetup] = useState<Setup | null>(null)
  const [filter,     setFilter]     = useState<"ALL" | "BREAKOUT" | "EP" | "VCP" | "SA" | "EMERGING" | "S2HIGH">("ALL")
  const [copied,     setCopied]     = useState(false)

  const { data: health } = useSWR("health", fetchHealth, { refreshInterval: 60_000 })

  const filtered = setups.filter(s => filter === "ALL" || (s.patterns || s.pattern).includes(filter))

  const copyForTV = () => {
    const tickers = [...new Set(filtered.map(s => "NSE:" + s.ticker.replace(".NS", "")))]
    navigator.clipboard.writeText(tickers.join(","))
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="max-w-7xl mx-auto space-y-4">

      {/* Market regime banner */}
      {health && (
        <div className="flex items-center justify-between px-4 py-2.5 rounded-xl text-xs"
             style={{
               backgroundColor: health.market_bullish ? "rgba(0,196,154,0.06)" : "rgba(255,77,77,0.06)",
               border: `1px solid ${health.market_bullish ? "rgba(0,196,154,0.2)" : "rgba(255,77,77,0.2)"}`,
             }}>
          <div className="flex items-center gap-2">
            {health.market_bullish
              ? <TrendingUp size={13} color="var(--green)" />
              : <TrendingDown size={13} color="var(--red)" />}
            <span style={{ color: health.market_bullish ? "var(--green)" : "var(--red)" }}>
              {health.regime_note}
            </span>
          </div>
          {health.nifty500_price && (
            <span style={{ color: "var(--text-muted)" }}>
              Nifty 500: {health.nifty500_price.toLocaleString("en-IN")}
              {health.nifty500_sma200 && ` · 200-SMA: ${health.nifty500_sma200.toLocaleString("en-IN")}`}
            </span>
          )}
        </div>
      )}

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold" style={{ color: "var(--text-primary)" }}>Live Setups</h1>
          {meta && (
            <p className="text-xs mt-0.5 flex items-center gap-2" style={{ color: "var(--text-muted)" }}>
              {meta.scan_date} · {meta.total_found} setups from {meta.universe_size} stocks
              {meta.stale
                ? <span className="flex items-center gap-1" style={{ color: "rgb(255,180,0)" }}>
                    <Clock size={9} /> {meta.scan_date} · today's scan running in background
                  </span>
                : meta.cached
                  ? <span className="flex items-center gap-1" style={{ color: "var(--blue)" }}>
                      <Database size={9} /> cached
                    </span>
                  : <span>· {meta.scan_duration_seconds.toFixed(1)}s</span>
              }
            </p>
          )}
        </div>
        <div className="flex items-center gap-3">
          <div className="flex gap-1.5">
            {(["ALL","BREAKOUT","EP","VCP","SA","EMERGING","S2HIGH"] as const).map(f => (
              <button key={f} onClick={() => setFilter(f)}
                      className="px-3 py-1 rounded-full text-xs font-medium transition-all"
                      style={{
                        backgroundColor: filter === f ? "rgba(0,196,154,0.2)" : "rgba(48,54,61,0.5)",
                        color:           filter === f ? "var(--green)" : "var(--text-muted)",
                        border:          filter === f ? "1px solid rgba(0,196,154,0.4)" : "1px solid var(--border)",
                      }}>
                {f === "ALL" ? "All"
                  : f === "EP" ? <><Zap size={9} className="inline mr-0.5" />EP</>
                  : f === "VCP" ? <><BarChart size={9} className="inline mr-0.5" />VCP</>
                  : f === "SA" ? <><Activity size={9} className="inline mr-0.5" />SA</>
                  : f === "EMERGING" ? <><Clock size={9} className="inline mr-0.5" />Watch</>
                  : f === "S2HIGH" ? <><TrendingUp size={9} className="inline mr-0.5" />S2High</>
                  : <><TrendingUp size={9} className="inline mr-0.5" />Breakout</>}
              </button>
            ))}
          </div>
          {filtered.length > 0 && (
            <button onClick={copyForTV}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs transition-colors"
                    style={{ backgroundColor: copied ? "rgba(0,196,154,0.2)" : "rgba(48,54,61,0.6)", color: copied ? "var(--green)" : "var(--text-muted)", border: `1px solid ${copied ? "rgba(0,196,154,0.4)" : "var(--border)"}` }}>
              {copied ? <Check size={12} /> : <Copy size={12} />}
              {copied ? "Copied!" : "TradingView"}
            </button>
          )}
          <button onClick={() => refresh()}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs transition-colors"
                  style={{ backgroundColor: "rgba(48,54,61,0.6)", color: "var(--text-muted)", border: "1px solid var(--border)" }}>
            <RefreshCw size={12} className={isLoading ? "animate-spin" : ""} />
            {isLoading ? "Scanning…" : "Refresh"}
          </button>
        </div>
      </div>

      {error && (
        <div className="flex items-center gap-2 px-4 py-3 rounded-xl text-sm"
             style={{ backgroundColor: "rgba(255,77,77,0.08)", border: "1px solid rgba(255,77,77,0.2)", color: "var(--red)" }}>
          <AlertCircle size={14} />
          API offline — start the FastAPI server on port 8000.
        </div>
      )}

      {isLoading && setups.length === 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="rounded-xl h-64 animate-pulse"
                 style={{ backgroundColor: "var(--bg-card)", border: "1px solid var(--border)" }} />
          ))}
        </div>
      )}

      {!isLoading && filtered.length === 0 && (
        <div className="flex items-center justify-center h-64 text-sm rounded-xl"
             style={{ backgroundColor: "var(--bg-card)", border: "1px solid var(--border)", color: "var(--text-muted)" }}>
          {error ? "Could not reach API." : "No setups found for today's scan."}
        </div>
      )}

      {filtered.length > 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {filtered.map((s, i) => (
            <div key={`${s.ticker}-${i}`} className="relative group">
              <SetupCard setup={s} onAddPosition={setAddSetup} />
              {/* Chart button overlay */}
              <button
                onClick={() => setChartSetup(s)}
                className="absolute top-3 right-14 opacity-70 hover:opacity-100 transition-opacity p-1.5 rounded-lg"
                style={{ backgroundColor: "rgba(77,159,255,0.15)", color: "var(--blue)", border: "1px solid rgba(77,159,255,0.3)" }}
                title="View chart">
                <BarChart2 size={12} />
              </button>
            </div>
          ))}
        </div>
      )}

      {addSetup && (
        <AddPositionModal prefill={addSetup} onSave={add} onClose={() => setAddSetup(null)} />
      )}

      {chartSetup && (
        <StockChartModal
          ticker={chartSetup.ticker}
          entryPrice={chartSetup.entry_price}
          stopPrice={chartSetup.stop_price}
          onClose={() => setChartSetup(null)}
        />
      )}
    </div>
  )
}

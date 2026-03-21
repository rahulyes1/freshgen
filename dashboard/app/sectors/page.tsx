"use client"
import { useState } from "react"
import useSWR from "swr"
import { RefreshCw, TrendingUp, TrendingDown, Minus } from "lucide-react"
import { fetchSectorPerformance } from "@/lib/api"
import { useSetups } from "@/hooks/useSetups"
import type { SectorPerf } from "@/lib/types"

// ── Sector setup counts from scan ────────────────────────────
const SECTOR_MEMBERS: Record<string, string[]> = {
  "IT & Tech":    ["TCS","INFY","HCLTECH","WIPRO","TECHM","LTIM","PERSISTENT","COFORGE","MPHASIS","OFSS"],
  "Banking":      ["HDFCBANK","ICICIBANK","KOTAKBANK","AXISBANK","SBIN","INDUSINDBK","BANDHANBNK","FEDERALBNK","IDFCFIRSTB","RBLBANK"],
  "Fin Services": [],
  "Pharma":       ["SUNPHARMA","DRREDDY","CIPLA","DIVISLAB","BIOCON","AUROPHARMA","LUPIN","TORNTPHARM","ALKEM","IPCALAB"],
  "Auto":         ["MARUTI","TATAMOTORS","M&M","BAJAJ-AUTO","HEROMOTOCO","EICHERMOT","TVSMOTOR","MOTHERSON","BALKRISIND","BHARATFORG"],
  "Metals":       ["TATASTEEL","JSWSTEEL","HINDALCO","VEDL","SAIL","NMDC","NATIONALUM","HINDZINC"],
  "Energy":       ["RELIANCE","ONGC","BPCL","IOC","HINDPETRO","GAIL","IGL","MGL","PETRONET","ATGL"],
  "FMCG":         ["HINDUNILVR","ITC","NESTLEIND","BRITANNIA","DABUR","MARICO","COLPAL","GODREJCP"],
  "Infra":        ["LT","SIEMENS","ABB","BHEL","HAVELLS","CUMMINSIND","THERMAX","VOLTAS"],
  "Realty":       ["DLF","GODREJPROP","OBEROIRLTY","PRESTIGE","BRIGADE","SOBHA"],
  "Media":        ["ZEEL","SUNTV","PVRINOX","NETWORK18","NAUKRI"],
  "PSU Bank":     ["SBIN","PNB","BANKBARODA","CANBK","UNIONBANK","INDIANB"],
  "Midcap":       [],
  "Smallcap":     [],
}

const STATUS_CONFIG = {
  HOT:  { emoji: "🔥", label: "HOT",  bg: "rgba(0,196,154,0.12)",  color: "var(--green)",  border: "rgba(0,196,154,0.3)"  },
  WARM: { emoji: "🌤", label: "WARM", bg: "rgba(251,191,36,0.10)", color: "#f59e0b",        border: "rgba(251,191,36,0.3)" },
  COLD: { emoji: "❄️", label: "COLD", bg: "rgba(77,159,255,0.08)", color: "var(--blue)",    border: "rgba(77,159,255,0.2)" },
  WEAK: { emoji: "🔴", label: "WEAK", bg: "rgba(255,77,77,0.08)",  color: "var(--red)",     border: "rgba(255,77,77,0.2)"  },
}

type SortKey = "return_1d" | "return_1w" | "return_1m" | "return_3m"

function ReturnCell({ value }: { value: number | null }) {
  if (value == null) return <span style={{ color: "var(--text-muted)" }}>—</span>
  const color = value > 0 ? "var(--green)" : value < 0 ? "var(--red)" : "var(--text-muted)"
  const Icon  = value > 0 ? TrendingUp : value < 0 ? TrendingDown : Minus
  return (
    <span className="flex items-center gap-1 justify-end tabular-nums" style={{ color }}>
      <Icon size={11} />
      {value > 0 ? "+" : ""}{value.toFixed(1)}%
    </span>
  )
}

export default function SectorsPage() {
  const [sortBy, setSortBy] = useState<SortKey>("return_1m")

  const { data, isLoading: loadingPerf, mutate } = useSWR(
    "sectors/performance",
    fetchSectorPerformance,
    { refreshInterval: 1800_000 },
  )
  const { setups } = useSetups("nifty500")
  const scanTickers = setups.map(s => s.ticker.replace(".NS", ""))

  const sectors: SectorPerf[] = [...(data?.sectors ?? [])].sort((a, b) => {
    const av = a[sortBy] ?? -999
    const bv = b[sortBy] ?? -999
    return bv - av
  })

  const setupCount = (sector: string): number =>
    (SECTOR_MEMBERS[sector] ?? []).filter(t => scanTickers.includes(t)).length

  const setupDots = (sector: string): number => Math.min(setupCount(sector), 4)

  const cols: { key: SortKey; label: string }[] = [
    { key: "return_1d", label: "1D" },
    { key: "return_1w", label: "1W" },
    { key: "return_1m", label: "1M" },
    { key: "return_3m", label: "3M" },
  ]

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold" style={{ color: "var(--text-primary)" }}>Sector Rotation</h1>
          <p className="text-xs mt-0.5" style={{ color: "var(--text-muted)" }}>
            NSE sector indices · 1D / 1W / 1M / 3M returns · sorted by {sortBy.replace("return_","")} · refreshes every 30 min
          </p>
        </div>
        <button onClick={() => mutate()}
                className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs"
                style={{ backgroundColor: "rgba(48,54,61,0.6)", color: "var(--text-muted)", border: "1px solid var(--border)" }}>
          <RefreshCw size={12} className={loadingPerf ? "animate-spin" : ""} />
          Refresh
        </button>
      </div>

      {/* Status legend */}
      <div className="flex gap-3 flex-wrap">
        {Object.entries(STATUS_CONFIG).map(([k, v]) => (
          <span key={k} className="flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs"
                style={{ backgroundColor: v.bg, color: v.color, border: `1px solid ${v.border}` }}>
            {v.emoji} {v.label}
          </span>
        ))}
        <span className="text-xs flex items-center" style={{ color: "var(--text-muted)" }}>
          · ● = setups in sector from today's scan
        </span>
      </div>

      {/* Loading skeleton */}
      {loadingPerf && sectors.length === 0 && (
        <div className="space-y-2">
          {[...Array(8)].map((_, i) => (
            <div key={i} className="h-11 rounded-xl animate-pulse"
                 style={{ backgroundColor: "var(--bg-card)", border: "1px solid var(--border)" }} />
          ))}
        </div>
      )}

      {/* Rotation table */}
      {sectors.length > 0 && (
        <div className="rounded-xl overflow-hidden" style={{ border: "1px solid var(--border)" }}>
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr style={{ backgroundColor: "var(--bg-card)", color: "var(--text-muted)" }}>
                <th className="px-4 py-3 text-left text-xs font-medium">Sector</th>
                <th className="px-3 py-3 text-center text-xs font-medium">Status</th>
                {cols.map(c => (
                  <th key={c.key}
                      className="px-3 py-3 text-right text-xs font-medium cursor-pointer select-none"
                      onClick={() => setSortBy(c.key)}
                      style={{ color: sortBy === c.key ? "var(--green)" : "var(--text-muted)" }}>
                    {c.label} {sortBy === c.key ? "▼" : ""}
                  </th>
                ))}
                <th className="px-4 py-3 text-center text-xs font-medium">Setups</th>
                <th className="px-4 py-3 text-right text-xs font-medium">vs 50-SMA</th>
              </tr>
            </thead>
            <tbody>
              {sectors.map((s, i) => {
                const cfg   = STATUS_CONFIG[s.status]
                const dots  = setupDots(s.sector)
                const count = setupCount(s.sector)
                return (
                  <tr key={s.sector}
                      className="border-t transition-colors hover:bg-white/[0.02]"
                      style={{
                        backgroundColor: i % 2 === 0 ? "transparent" : "rgba(48,54,61,0.15)",
                        borderColor: "var(--border)",
                      }}>
                    {/* Sector name */}
                    <td className="px-4 py-3">
                      <span className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
                        {s.sector}
                      </span>
                    </td>

                    {/* Status badge */}
                    <td className="px-3 py-3 text-center">
                      <span className="px-2 py-0.5 rounded-full text-xs font-semibold"
                            style={{ backgroundColor: cfg.bg, color: cfg.color, border: `1px solid ${cfg.border}` }}>
                        {cfg.emoji} {cfg.label}
                      </span>
                    </td>

                    {/* Returns */}
                    {cols.map(c => (
                      <td key={c.key} className="px-3 py-3 text-right text-xs">
                        <ReturnCell value={s[c.key]} />
                      </td>
                    ))}

                    {/* Setups dots */}
                    <td className="px-4 py-3 text-center">
                      {count > 0 ? (
                        <span className="text-xs font-semibold" style={{ color: "var(--green)" }}>
                          {"●".repeat(dots)}{count > 4 ? `+${count-4}` : ""}
                        </span>
                      ) : (
                        <span style={{ color: "var(--text-muted)" }}>—</span>
                      )}
                    </td>

                    {/* Above 50-SMA */}
                    <td className="px-4 py-3 text-right text-xs">
                      {s.sma50 != null ? (
                        <span style={{ color: s.above_sma50 ? "var(--green)" : "var(--red)" }}>
                          {s.above_sma50 ? "▲ Above" : "▼ Below"}
                        </span>
                      ) : (
                        <span style={{ color: "var(--text-muted)" }}>—</span>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Qullamaggie rule reminder */}
      <div className="flex items-center gap-2 px-4 py-3 rounded-xl text-xs"
           style={{ backgroundColor: "rgba(77,159,255,0.06)", border: "1px solid rgba(77,159,255,0.2)", color: "var(--text-muted)" }}>
        <span style={{ color: "var(--blue)" }}>💡</span>
        Qullamaggie rule: <strong style={{ color: "var(--text-primary)" }}>Only trade stocks in HOT or WARM sectors.</strong>
        &nbsp;When a setup appears, check if its sector is green here first.
      </div>

      {/* Setup heatmap — existing card grid kept below */}
      {scanTickers.length > 0 && (
        <>
          <h2 className="text-sm font-semibold" style={{ color: "var(--text-muted)" }}>
            Today's setups by sector
          </h2>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
            {Object.entries(SECTOR_MEMBERS).filter(([, m]) => m.length > 0).map(([sector, members]) => {
              const hits = members.filter(t => scanTickers.includes(t))
              return (
                <div key={sector}
                     className="rounded-xl p-3.5 flex flex-col gap-1.5"
                     style={{
                       backgroundColor: hits.length > 0 ? "rgba(0,196,154,0.10)" : "rgba(48,54,61,0.3)",
                       border: `1px solid ${hits.length > 0 ? "rgba(0,196,154,0.3)" : "var(--border)"}`,
                     }}>
                  <div className="text-xs font-semibold" style={{ color: hits.length > 0 ? "var(--green)" : "var(--text-muted)" }}>
                    {sector}
                  </div>
                  <div className="text-2xl font-bold" style={{ color: hits.length > 0 ? "var(--text-primary)" : "var(--text-muted)" }}>
                    {hits.length}
                  </div>
                  {hits.length > 0 && (
                    <div className="flex flex-wrap gap-1 mt-0.5">
                      {hits.map(t => (
                        <span key={t} className="text-xs px-1.5 py-0.5 rounded"
                              style={{ backgroundColor: "rgba(0,196,154,0.15)", color: "var(--green)" }}>
                          {t}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </>
      )}
    </div>
  )
}

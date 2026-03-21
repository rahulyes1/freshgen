"use client"
import { useState, useEffect } from "react"
import { Plus, AlertCircle, RefreshCw, Settings } from "lucide-react"
import { usePositions } from "@/hooks/usePositions"
import PositionsTable from "@/components/positions/PositionsTable"
import AddPositionModal from "@/components/positions/AddPositionModal"
import { formatINR, pnlColor } from "@/lib/utils"
import { refreshPrices } from "@/lib/api"

const LS_ACCOUNT = "fg_account_size"
const LS_MAX_POS = "fg_max_positions"

export default function PositionsPage() {
  const { positions, error, isLoading, add, update, remove, refresh } = usePositions()
  const [showModal,    setShowModal]    = useState(false)
  const [refreshing,   setRefreshing]   = useState(false)
  const [stopAlerts,   setStopAlerts]   = useState<any[]>([])
  const [showSettings, setShowSettings] = useState(false)
  const [accountSize,  setAccountSize]  = useState(1_000_000)
  const [maxPositions, setMaxPositions] = useState(8)

  useEffect(() => {
    const a = localStorage.getItem(LS_ACCOUNT)
    const m = localStorage.getItem(LS_MAX_POS)
    if (a) setAccountSize(parseInt(a))
    if (m) setMaxPositions(parseInt(m))
  }, [])

  const open   = positions.filter(p => p.status === "open")
  const totalUnr = open.reduce((s, p) => s + (p.unrealized_pnl ?? 0), 0)
  const totalVal  = open.reduce((s, p) => s + p.entry_price * p.shares, 0)

  const handleRefresh = async () => {
    setRefreshing(true)
    try {
      const res = await refreshPrices()
      setStopAlerts(res.stop_alerts)
      await refresh()
    } finally {
      setRefreshing(false)
    }
  }

  return (
    <div className="max-w-7xl mx-auto space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold" style={{ color: "var(--text-primary)" }}>Positions</h1>
          <p className="text-xs mt-0.5" style={{ color: "var(--text-muted)" }}>
            {open.length} open · {positions.filter(p => p.status === "closed").length} closed
          </p>
        </div>
        <div className="flex gap-2">
          <button onClick={() => setShowSettings(s => !s)}
                  className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-colors"
                  style={{ backgroundColor: showSettings ? "rgba(77,159,255,0.15)" : "rgba(48,54,61,0.6)", color: showSettings ? "var(--blue)" : "var(--text-muted)", border: "1px solid var(--border)" }}>
            <Settings size={13} />
          </button>
          {open.length > 0 && (
            <button onClick={handleRefresh} disabled={refreshing}
                    className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm transition-colors disabled:opacity-50"
                    style={{ backgroundColor: "rgba(77,159,255,0.12)", color: "var(--blue)", border: "1px solid rgba(77,159,255,0.3)" }}>
              <RefreshCw size={13} className={refreshing ? "animate-spin" : ""} />
              {refreshing ? "Refreshing…" : "Refresh Prices"}
            </button>
          )}
          <button onClick={() => setShowModal(true)}
                  className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold transition-colors"
                  style={{ backgroundColor: "rgba(0,196,154,0.15)", color: "var(--green)", border: "1px solid rgba(0,196,154,0.3)" }}>
            <Plus size={14} />
            Add Position
          </button>
        </div>
      </div>

      {/* Settings panel */}
      {showSettings && (
        <div className="rounded-xl px-4 py-3 flex flex-wrap gap-4 items-end"
             style={{ backgroundColor: "var(--bg-card)", border: "1px solid var(--border)" }}>
          <div>
            <label className="block text-xs mb-1" style={{ color: "var(--text-muted)" }}>Account Size (₹)</label>
            <select value={accountSize}
                    onChange={e => { const v = parseInt(e.target.value); setAccountSize(v); localStorage.setItem(LS_ACCOUNT, String(v)) }}
                    className="rounded-lg px-2.5 py-1.5 text-xs"
                    style={{ backgroundColor: "var(--bg-primary)", border: "1px solid var(--border)", color: "var(--text-primary)" }}>
              {[500_000, 1_000_000, 2_000_000, 5_000_000, 10_000_000].map(v => (
                <option key={v} value={v}>₹{(v / 100_000).toFixed(0)}L</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs mb-1" style={{ color: "var(--text-muted)" }}>Max Positions</label>
            <select value={maxPositions}
                    onChange={e => { const v = parseInt(e.target.value); setMaxPositions(v); localStorage.setItem(LS_MAX_POS, String(v)) }}
                    className="rounded-lg px-2.5 py-1.5 text-xs"
                    style={{ backgroundColor: "var(--bg-primary)", border: "1px solid var(--border)", color: "var(--text-primary)" }}>
              {[5, 6, 8, 10, 12, 15, 20, 30].map(v => (
                <option key={v} value={v}>{v} positions</option>
              ))}
            </select>
          </div>
          <p className="text-xs" style={{ color: "var(--text-muted)" }}>Saved locally — affects risk meter only.</p>
        </div>
      )}

      {/* Summary + risk meter */}
      {open.length > 0 && (
        <>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <StatCard label="Open Positions" value={String(open.length)} />
            <StatCard label="Invested Value" value={formatINR(totalVal)} />
            <StatCard label="Unrealized P&L"
                      value={`${totalUnr >= 0 ? "+" : ""}${formatINR(totalUnr)}`}
                      color={pnlColor(totalUnr)} />
            <RiskMeter positions={open} accountSize={accountSize} maxPositions={maxPositions} />
          </div>
        </>
      )}

      {/* Stop loss alerts */}
      {stopAlerts.length > 0 && (
        <div className="px-4 py-3 rounded-xl text-sm space-y-1"
             style={{ backgroundColor: "rgba(255,77,77,0.1)", border: "1px solid rgba(255,77,77,0.3)" }}>
          <div className="font-semibold" style={{ color: "var(--red)" }}>
            🚨 Stop Loss Breached ({stopAlerts.length})
          </div>
          {stopAlerts.map((a, i) => (
            <div key={i} className="text-xs" style={{ color: "var(--text-primary)" }}>
              <strong>{a.ticker.replace(".NS","")}</strong>: current ₹{a.current} ≤ stop ₹{a.stop} — Close immediately
            </div>
          ))}
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="flex items-center gap-2 px-4 py-3 rounded-xl text-sm"
             style={{ backgroundColor: "rgba(255,77,77,0.08)", border: "1px solid rgba(255,77,77,0.2)", color: "var(--red)" }}>
          <AlertCircle size={14} />
          API offline — positions may be stale.
        </div>
      )}

      {/* Loading */}
      {isLoading && positions.length === 0 && (
        <div className="h-40 rounded-xl animate-pulse"
             style={{ backgroundColor: "var(--bg-card)", border: "1px solid var(--border)" }} />
      )}

      {/* Table */}
      {!isLoading && (
        <PositionsTable positions={positions}
                        onUpdate={(id, data) => update(id, data)}
                        onDelete={remove} />
      )}

      {showModal && (
        <AddPositionModal onSave={add} onClose={() => setShowModal(false)} />
      )}
    </div>
  )
}

function StatCard({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div className="rounded-xl px-4 py-3"
         style={{ backgroundColor: "var(--bg-card)", border: "1px solid var(--border)" }}>
      <div className="text-xs mb-1" style={{ color: "var(--text-muted)" }}>{label}</div>
      <div className="text-lg font-bold" style={{ color: color ?? "var(--text-primary)" }}>{value}</div>
    </div>
  )
}

function RiskMeter({ positions, accountSize, maxPositions }: {
  positions: any[]; accountSize: number; maxPositions: number
}) {
  const totalRisk = positions.reduce((s, p) => s + ((p.entry_price - p.stop_price) * p.shares), 0)
  const riskPct   = (totalRisk / accountSize) * 100
  const slotsFull = positions.length / maxPositions
  const riskColor = riskPct > 8 ? "var(--red)" : riskPct > 5 ? "#f59e0b" : "var(--green)"

  return (
    <div className="rounded-xl px-4 py-3" style={{ backgroundColor: "var(--bg-card)", border: "1px solid var(--border)" }}>
      <div className="text-xs mb-1" style={{ color: "var(--text-muted)" }}>Portfolio Risk</div>
      <div className="text-lg font-bold" style={{ color: riskColor }}>{riskPct.toFixed(1)}% at risk</div>
      <div className="mt-1.5 space-y-1">
        <div className="flex justify-between text-xs" style={{ color: "var(--text-muted)" }}>
          <span>Positions</span>
          <span>{positions.length}/{maxPositions}</span>
        </div>
        <div className="h-1.5 rounded-full overflow-hidden" style={{ backgroundColor: "var(--border)" }}>
          <div className="h-full rounded-full transition-all"
               style={{ width: `${Math.min(slotsFull * 100, 100)}%`, backgroundColor: riskColor }} />
        </div>
      </div>
    </div>
  )
}

"use client"
import { useState, useEffect } from "react"
import { RefreshCw, Plus, X, TrendingUp, TrendingDown, AlertCircle } from "lucide-react"
import {
  fetchPaperTrades, fetchPaperStats, createPaperTrade,
  updatePaperTrade, deletePaperTrade, refreshPaperPrices,
} from "@/lib/api"
import type { PaperTrade, PaperStats } from "@/lib/types"
import { formatINR, pnlColor } from "@/lib/utils"

export default function PaperPage() {
  const [trades, setTrades]       = useState<PaperTrade[]>([])
  const [stats, setStats]         = useState<PaperStats | null>(null)
  const [loading, setLoading]     = useState(true)
  const [error, setError]         = useState<string | null>(null)
  const [refreshing, setRefreshing] = useState(false)
  const [showAdd, setShowAdd]     = useState(false)
  const [filter, setFilter]       = useState<"all" | "open" | "closed">("all")

  async function load() {
    try {
      const [t, s] = await Promise.all([
        fetchPaperTrades(filter === "all" ? undefined : filter),
        fetchPaperStats(),
      ])
      setTrades(t)
      setStats(s)
    } catch (e: any) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [filter])

  async function handleRefresh() {
    setRefreshing(true)
    try {
      await refreshPaperPrices()
      await load()
    } catch (e: any) {
      setError(e.message)
    } finally {
      setRefreshing(false)
    }
  }

  async function handleClose(id: number, exitPrice: number) {
    const today = new Date().toISOString().slice(0, 10)
    await updatePaperTrade(id, { exit_price: exitPrice, exit_date: today, exit_reason: "Manual close" })
    await load()
  }

  async function handleDelete(id: number) {
    await deletePaperTrade(id)
    await load()
  }

  const openTrades   = trades.filter(t => t.status === "open")
  const closedTrades = trades.filter(t => t.status === "closed")

  return (
    <div className="max-w-6xl mx-auto space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold" style={{ color: "var(--text-primary)" }}>Paper Trading</h1>
          <p className="text-xs mt-0.5" style={{ color: "var(--text-muted)" }}>
            System tracker — auto-logged from scanner · no real money
          </p>
        </div>
        <div className="flex gap-2">
          <button onClick={handleRefresh} disabled={refreshing}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors disabled:opacity-50"
                  style={{ backgroundColor: "var(--bg-card)", border: "1px solid var(--border)", color: "var(--text-muted)" }}>
            <RefreshCw size={12} className={refreshing ? "animate-spin" : ""} />
            Refresh Prices
          </button>
          <button onClick={() => setShowAdd(true)}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold"
                  style={{ backgroundColor: "rgba(0,196,154,0.2)", color: "var(--green)", border: "1px solid rgba(0,196,154,0.3)" }}>
            <Plus size={12} />
            Add Trade
          </button>
        </div>
      </div>

      {error && (
        <div className="flex items-center gap-2 px-4 py-3 rounded-xl text-sm"
             style={{ backgroundColor: "rgba(255,77,77,0.08)", border: "1px solid rgba(255,77,77,0.2)", color: "var(--red)" }}>
          <AlertCircle size={14} />{error}
        </div>
      )}

      {/* Stats */}
      {stats && stats.closed > 0 && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <StatCard label="Win Rate"      value={`${stats.win_rate.toFixed(1)}%`}    green={stats.win_rate >= 50} />
          <StatCard label="Profit Factor" value={stats.profit_factor.toFixed(2)}      green={stats.profit_factor >= 1} />
          <StatCard label="Expectancy"    value={`${stats.expectancy_r.toFixed(2)}R`} green={stats.expectancy_r > 0} />
          <StatCard label="Total P&L"     value={formatINR(stats.total_pnl)}          green={stats.total_pnl > 0} red={stats.total_pnl < 0} />
        </div>
      )}

      {stats && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <StatCard label="Total Trades" value={String(stats.total)} />
          <StatCard label="Open"         value={String(stats.open)} />
          <StatCard label="Closed"       value={String(stats.closed)} />
          <StatCard label="Best R"       value={stats.best_r ? `${stats.best_r.toFixed(1)}R` : "—"} green />
        </div>
      )}

      {/* By pattern breakdown */}
      {stats && Object.keys(stats.by_pattern).length > 0 && (
        <div className="rounded-xl p-4 grid grid-cols-3 gap-3"
             style={{ backgroundColor: "var(--bg-card)", border: "1px solid var(--border)" }}>
          {Object.entries(stats.by_pattern).map(([pat, s]) => (
            <div key={pat} className="text-center">
              <div className="text-xs mb-1" style={{ color: "var(--text-muted)" }}>{pat}</div>
              <div className="text-sm font-bold" style={{ color: "var(--blue)" }}>{s.trades} trades</div>
              <div className="text-xs" style={{ color: s.wins / s.trades >= 0.5 ? "var(--green)" : "var(--red)" }}>
                {((s.wins / s.trades) * 100).toFixed(0)}% win
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Filter pills */}
      <div className="flex gap-2">
        {(["all", "open", "closed"] as const).map(f => (
          <button key={f} onClick={() => setFilter(f)}
                  className="px-3 py-1 rounded-full text-xs font-medium transition-colors capitalize"
                  style={{
                    backgroundColor: filter === f ? "rgba(0,196,154,0.15)" : "transparent",
                    color: filter === f ? "var(--green)" : "var(--text-muted)",
                    border: filter === f ? "1px solid rgba(0,196,154,0.3)" : "1px solid transparent",
                  }}>
            {f} {f === "all" ? `(${trades.length})` : f === "open" ? `(${openTrades.length})` : `(${closedTrades.length})`}
          </button>
        ))}
      </div>

      {/* Trade Table */}
      {loading ? (
        <div className="flex items-center justify-center h-40 rounded-xl text-sm"
             style={{ backgroundColor: "var(--bg-card)", border: "1px solid var(--border)", color: "var(--text-muted)" }}>
          Loading paper trades…
        </div>
      ) : trades.length === 0 ? (
        <div className="flex items-center justify-center h-40 rounded-xl text-sm"
             style={{ backgroundColor: "var(--bg-card)", border: "1px solid var(--border)", color: "var(--text-muted)" }}>
          No paper trades yet. They auto-log from the intraday scanner, or add manually.
        </div>
      ) : (
        <div className="rounded-xl overflow-hidden" style={{ border: "1px solid var(--border)" }}>
          <div className="overflow-x-auto max-h-[600px]">
            <table className="w-full text-xs border-collapse">
              <thead className="sticky top-0" style={{ backgroundColor: "var(--bg-card)" }}>
                <tr style={{ color: "var(--text-muted)" }}>
                  {["Ticker","Pat","Entry Date","Entry ₹","Stop ₹","Current ₹","Shares","P&L","R","Days","Status",""].map(h => (
                    <th key={h} className="px-3 py-2 text-left font-medium whitespace-nowrap">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {trades.map((t, i) => (
                  <TradeRow key={t.id} trade={t} i={i} onClose={handleClose} onDelete={handleDelete} />
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {showAdd && <AddPaperModal onClose={() => setShowAdd(false)} onSaved={load} />}
    </div>
  )
}

function TradeRow({ trade: t, i, onClose, onDelete }: {
  trade: PaperTrade; i: number
  onClose: (id: number, price: number) => void
  onDelete: (id: number) => void
}) {
  const [exitInput, setExitInput] = useState("")
  const isOpen = t.status === "open"
  const pnl = isOpen ? t.unrealized_pnl : t.pnl
  const r   = isOpen ? null : t.r_multiple

  return (
    <tr className="border-t"
        style={{ backgroundColor: i % 2 === 0 ? "transparent" : "rgba(48,54,61,0.3)", borderColor: "var(--border)" }}>
      <td className="px-3 py-2 font-semibold" style={{ color: "var(--text-primary)" }}>
        {t.ticker.replace(".NS", "")}
      </td>
      <td className="px-3 py-2" style={{ color: "var(--blue)" }}>{t.pattern}</td>
      <td className="px-3 py-2" style={{ color: "var(--text-muted)" }}>{t.entry_date}</td>
      <td className="px-3 py-2" style={{ color: "var(--text-primary)" }}>₹{t.entry_price.toFixed(2)}</td>
      <td className="px-3 py-2" style={{ color: "var(--red)" }}>₹{t.stop_price.toFixed(2)}</td>
      <td className="px-3 py-2" style={{ color: isOpen ? "var(--text-primary)" : "var(--text-muted)" }}>
        {isOpen
          ? t.current_price ? `₹${t.current_price.toFixed(2)}` : "—"
          : t.exit_price ? `₹${t.exit_price.toFixed(2)}` : "—"}
      </td>
      <td className="px-3 py-2" style={{ color: "var(--text-muted)" }}>{t.shares}</td>
      <td className="px-3 py-2 font-semibold" style={{ color: pnlColor(pnl ?? 0) }}>
        {pnl !== null && pnl !== undefined
          ? `${pnl >= 0 ? "+" : ""}${formatINR(pnl)}`
          : "—"}
      </td>
      <td className="px-3 py-2" style={{ color: r !== null && r !== undefined ? pnlColor(r) : "var(--text-muted)" }}>
        {r !== null && r !== undefined ? `${r >= 0 ? "+" : ""}${r.toFixed(2)}R` : "—"}
      </td>
      <td className="px-3 py-2" style={{ color: "var(--text-muted)" }}>
        {t.hold_days !== null && t.hold_days !== undefined ? `${t.hold_days}d` : "—"}
      </td>
      <td className="px-3 py-2">
        <span className="px-1.5 py-0.5 rounded text-xs"
              style={{
                backgroundColor: isOpen ? "rgba(0,196,154,0.1)" : "rgba(150,150,150,0.1)",
                color: isOpen ? "var(--green)" : "var(--text-muted)",
              }}>
          {t.status}
        </span>
      </td>
      <td className="px-3 py-2">
        {isOpen ? (
          <div className="flex items-center gap-1">
            <input
              type="number"
              placeholder="exit ₹"
              value={exitInput}
              onChange={e => setExitInput(e.target.value)}
              className="w-20 px-1.5 py-0.5 rounded text-xs"
              style={{ backgroundColor: "var(--bg-primary)", border: "1px solid var(--border)", color: "var(--text-primary)" }}
            />
            <button
              onClick={() => exitInput && onClose(t.id, parseFloat(exitInput))}
              disabled={!exitInput}
              className="px-2 py-0.5 rounded text-xs font-medium disabled:opacity-30"
              style={{ backgroundColor: "rgba(0,196,154,0.15)", color: "var(--green)" }}>
              Close
            </button>
            <button onClick={() => onDelete(t.id)}
                    className="p-0.5 rounded hover:opacity-70">
              <X size={11} style={{ color: "var(--text-muted)" }} />
            </button>
          </div>
        ) : (
          <button onClick={() => onDelete(t.id)} className="p-0.5 rounded hover:opacity-70">
            <X size={11} style={{ color: "var(--text-muted)" }} />
          </button>
        )}
      </td>
    </tr>
  )
}

function AddPaperModal({ onClose, onSaved }: { onClose: () => void; onSaved: () => void }) {
  const [form, setForm] = useState({
    ticker: "", pattern: "BREAKOUT", entry_price: "", stop_price: "",
    shares: "1", entry_date: new Date().toISOString().slice(0, 10), notes: "",
  })
  const [saving, setSaving] = useState(false)

  async function handleSubmit() {
    if (!form.ticker || !form.entry_price || !form.stop_price) return
    setSaving(true)
    try {
      await createPaperTrade({
        ticker:      form.ticker.toUpperCase().endsWith(".NS") ? form.ticker.toUpperCase() : form.ticker.toUpperCase() + ".NS",
        pattern:     form.pattern,
        entry_price: parseFloat(form.entry_price),
        stop_price:  parseFloat(form.stop_price),
        shares:      parseInt(form.shares) || 1,
        entry_date:  form.entry_date,
        signal_date: form.entry_date,
        notes:       form.notes,
      })
      await onSaved()
      onClose()
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4"
         style={{ backgroundColor: "rgba(0,0,0,0.7)" }}>
      <div className="w-full max-w-sm rounded-2xl p-6 space-y-4"
           style={{ backgroundColor: "var(--bg-card)", border: "1px solid var(--border)" }}>
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-bold" style={{ color: "var(--text-primary)" }}>Add Paper Trade</h2>
          <button onClick={onClose}><X size={16} style={{ color: "var(--text-muted)" }} /></button>
        </div>
        {[
          { label: "Ticker",       key: "ticker",       type: "text",   placeholder: "RELIANCE" },
          { label: "Entry ₹",      key: "entry_price",  type: "number", placeholder: "0.00" },
          { label: "Stop ₹",       key: "stop_price",   type: "number", placeholder: "0.00" },
          { label: "Shares",       key: "shares",       type: "number", placeholder: "1" },
          { label: "Entry Date",   key: "entry_date",   type: "date",   placeholder: "" },
        ].map(f => (
          <div key={f.key} className="flex flex-col gap-1">
            <label className="text-xs" style={{ color: "var(--text-muted)" }}>{f.label}</label>
            <input type={f.type} placeholder={f.placeholder}
                   value={(form as any)[f.key]}
                   onChange={e => setForm(p => ({ ...p, [f.key]: e.target.value }))}
                   className="px-3 py-2 rounded-lg text-sm"
                   style={{ backgroundColor: "var(--bg-primary)", border: "1px solid var(--border)", color: "var(--text-primary)" }} />
          </div>
        ))}
        <div className="flex flex-col gap-1">
          <label className="text-xs" style={{ color: "var(--text-muted)" }}>Pattern</label>
          <select value={form.pattern} onChange={e => setForm(p => ({ ...p, pattern: e.target.value }))}
                  className="px-3 py-2 rounded-lg text-sm"
                  style={{ backgroundColor: "var(--bg-primary)", border: "1px solid var(--border)", color: "var(--text-primary)" }}>
            <option value="BREAKOUT">BREAKOUT</option>
            <option value="EP">EP</option>
            <option value="VCP">VCP</option>
          </select>
        </div>
        <button onClick={handleSubmit} disabled={saving}
                className="w-full py-2 rounded-lg text-sm font-semibold disabled:opacity-50"
                style={{ backgroundColor: "rgba(0,196,154,0.2)", color: "var(--green)", border: "1px solid rgba(0,196,154,0.3)" }}>
          {saving ? "Adding…" : "Add Trade"}
        </button>
      </div>
    </div>
  )
}

function StatCard({ label, value, green, red }: { label: string; value: string; green?: boolean; red?: boolean }) {
  const color = green ? "var(--green)" : red ? "var(--red)" : "var(--text-primary)"
  return (
    <div className="rounded-xl px-4 py-3"
         style={{ backgroundColor: "var(--bg-card)", border: "1px solid var(--border)" }}>
      <div className="text-xs mb-1" style={{ color: "var(--text-muted)" }}>{label}</div>
      <div className="text-sm font-semibold" style={{ color }}>{value}</div>
    </div>
  )
}

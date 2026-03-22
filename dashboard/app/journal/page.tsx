"use client"
import { useState } from "react"
import useSWR from "swr"
import { Plus, Download, Trash2, Edit2, Check, X, TrendingUp, BookOpen } from "lucide-react"
import { fetchJournal, fetchJournalAnalytics, createJournalEntry, updateJournalEntry, deleteJournalEntry, exportJournalUrl } from "@/lib/api"
import type { JournalEntry, JournalAnalytics } from "@/lib/types"
import { formatINR, pnlColor } from "@/lib/utils"
import {
  BarChart, Bar, LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine,
} from "recharts"

export default function JournalPage() {
  const { data: entries = [], mutate } = useSWR("journal", fetchJournal)
  const { data: analytics }            = useSWR<JournalAnalytics>("journal/analytics", fetchJournalAnalytics)
  const [showAdd,  setShowAdd]  = useState(false)
  const [editing,  setEditing]  = useState<number | null>(null)
  const [editVals, setEditVals] = useState<any>({})

  const closed = entries.filter(e => e.status === "closed")
  const open   = entries.filter(e => e.status === "open")

  const monthlyData = analytics?.monthly != null && typeof analytics.monthly === "object"
    ? Object.entries(analytics.monthly as Record<string, any>).map(([month, v]) => ({ month: month.slice(5), ...(v ?? {}) }))
    : []

  const startEdit = (e: JournalEntry) => {
    setEditing(e.id)
    setEditVals({ exit_price: e.exit_price ?? "", exit_date: e.exit_date ?? new Date().toISOString().slice(0,10), notes: e.notes })
  }

  const saveEdit = async (id: number) => {
    await updateJournalEntry(id, {
      exit_price: editVals.exit_price ? parseFloat(editVals.exit_price) : undefined,
      exit_date:  editVals.exit_date  || undefined,
      notes:      editVals.notes      || undefined,
    })
    await mutate()
    setEditing(null)
  }

  return (
    <div className="max-w-7xl mx-auto space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold" style={{ color: "var(--text-primary)" }}>Trade Journal</h1>
          <p className="text-xs mt-0.5" style={{ color: "var(--text-muted)" }}>
            {entries.length} trades · {open.length} open · {closed.length} closed
          </p>
        </div>
        <div className="flex gap-2">
          <a href={exportJournalUrl()} download="trade_journal.csv"
             className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm transition-colors"
             style={{ backgroundColor: "rgba(48,54,61,0.6)", color: "var(--text-muted)", border: "1px solid var(--border)" }}>
            <Download size={13} /> Export CSV
          </a>
          <button onClick={() => setShowAdd(true)}
                  className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold"
                  style={{ backgroundColor: "rgba(0,196,154,0.15)", color: "var(--green)", border: "1px solid rgba(0,196,154,0.3)" }}>
            <Plus size={13} /> Log Trade
          </button>
        </div>
      </div>

      {/* Analytics cards */}
      {analytics && analytics.closed > 0 && (
        <>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <StatCard label="Win Rate"       value={`${analytics.win_rate.toFixed(1)}%`}     green={analytics.win_rate >= 50} />
            <StatCard label="Profit Factor"  value={analytics.profit_factor.toFixed(2)}       green={analytics.profit_factor >= 1.5} />
            <StatCard label="Expectancy"     value={`${analytics.expectancy_r.toFixed(2)}R`}  green={analytics.expectancy_r > 0} />
            <StatCard label="Total P&L"      value={formatINR(analytics.total_pnl)}            green={analytics.total_pnl > 0} red={analytics.total_pnl <= 0} />
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <StatCard label="Avg Win"        value={formatINR(analytics.avg_win)}   green />
            <StatCard label="Avg Loss"       value={formatINR(analytics.avg_loss)}  red />
            <StatCard label="Best R"         value={`${analytics.best_r.toFixed(1)}R`}   green />
            <StatCard label="Avg Hold"       value={`${analytics.avg_hold_days.toFixed(0)}d`} />
          </div>

          {/* Monthly P&L chart */}
          {monthlyData.length > 1 && (
            <div className="rounded-xl p-4" style={{ backgroundColor: "var(--bg-card)", border: "1px solid var(--border)" }}>
              <h3 className="text-sm font-semibold mb-3" style={{ color: "var(--text-primary)" }}>Monthly P&L</h3>
              <div className="h-40">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={monthlyData} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#30363d" strokeOpacity={0.5} />
                    <XAxis dataKey="month" tick={{ fontSize: 10, fill: "#8b949e" }} />
                    <YAxis tick={{ fontSize: 10, fill: "#8b949e" }} width={60}
                           tickFormatter={v => `₹${(v/1000).toFixed(0)}k`} />
                    <Tooltip formatter={(v: any) => formatINR(Number(v))} labelStyle={{ color: "#8b949e" }}
                             contentStyle={{ backgroundColor: "var(--bg-card)", border: "1px solid var(--border)" }} />
                    <ReferenceLine y={0} stroke="#484f58" />
                    <Bar dataKey="pnl" fill="#00c49a"
                         label={false}
                         shape={(props: any) => (
                           <rect {...props} fill={props.pnl >= 0 ? "#00c49a" : "#ff4d4d"} opacity={0.8} radius={[3,3,0,0]} />
                         )} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}

          {/* By pattern breakdown */}
          {analytics.by_pattern != null && Object.keys(analytics.by_pattern ?? {}).length > 0 && (
            <div className="grid grid-cols-2 gap-3">
              {(Object.entries(analytics.by_pattern ?? {}) as [string, any][]).map(([pat, d]) => (
                <div key={pat} className="rounded-xl px-4 py-3" style={{ backgroundColor: "var(--bg-card)", border: "1px solid var(--border)" }}>
                  <div className="text-xs mb-2" style={{ color: "var(--text-muted)" }}>{pat}</div>
                  <div className="flex justify-between text-sm">
                    <span style={{ color: "var(--text-primary)" }}>{d.trades} trades · {d.trades > 0 ? ((d.wins/d.trades)*100).toFixed(0) : 0}% WR</span>
                    <span style={{ color: pnlColor(d.total_pnl) }}>{formatINR(d.total_pnl)}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      )}

      {/* Add trade form */}
      {showAdd && (
        <AddTradeForm
          onSave={async (data) => { await createJournalEntry(data); await mutate(); setShowAdd(false) }}
          onClose={() => setShowAdd(false)}
        />
      )}

      {/* Trade table */}
      {entries.length === 0 ? (
        <div className="flex flex-col items-center justify-center h-48 rounded-xl gap-2"
             style={{ backgroundColor: "var(--bg-card)", border: "1px solid var(--border)" }}>
          <BookOpen size={24} style={{ color: "var(--text-muted)" }} />
          <p className="text-sm" style={{ color: "var(--text-muted)" }}>No trades logged yet. Click "Log Trade" to start.</p>
        </div>
      ) : (
        <div className="rounded-xl overflow-hidden" style={{ border: "1px solid var(--border)" }}>
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="text-xs" style={{ backgroundColor: "var(--bg-card)", color: "var(--text-muted)" }}>
                {["Ticker","Pat","Entry Date","Exit Date","Entry ₹","Exit ₹","Shares","P&L","R","Hold","Notes",""].map(h => (
                  <th key={h} className="px-3 py-2.5 text-left font-medium whitespace-nowrap">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {entries.map((e, i) => (
                <tr key={e.id} className="border-t"
                    style={{ backgroundColor: i % 2 === 0 ? "transparent" : "rgba(48,54,61,0.2)", borderColor: "var(--border)" }}>
                  <td className="px-3 py-2 font-semibold" style={{ color: "var(--text-primary)" }}>
                    {e.ticker.replace(".NS","")}
                  </td>
                  <td className="px-3 py-2 text-xs" style={{ color: "var(--blue)" }}>{e.pattern}</td>
                  <td className="px-3 py-2 text-xs" style={{ color: "var(--text-muted)" }}>{e.entry_date}</td>
                  <td className="px-3 py-2 text-xs" style={{ color: "var(--text-muted)" }}>
                    {editing === e.id
                      ? <input type="date" value={editVals.exit_date}
                               onChange={ev => setEditVals((v: any) => ({ ...v, exit_date: ev.target.value }))}
                               className="w-28 px-1 py-0.5 rounded text-xs"
                               style={{ backgroundColor: "var(--bg-primary)", border: "1px solid var(--border)", color: "var(--text-primary)" }} />
                      : (e.exit_date ?? "—")}
                  </td>
                  <td className="px-3 py-2" style={{ color: "var(--text-primary)" }}>₹{e.entry_price.toFixed(2)}</td>
                  <td className="px-3 py-2">
                    {editing === e.id
                      ? <input type="number" step="0.01" value={editVals.exit_price}
                               onChange={ev => setEditVals((v: any) => ({ ...v, exit_price: ev.target.value }))}
                               className="w-20 px-1 py-0.5 rounded text-xs"
                               style={{ backgroundColor: "var(--bg-primary)", border: "1px solid var(--border)", color: "var(--text-primary)" }} />
                      : <span style={{ color: "var(--text-primary)" }}>{e.exit_price ? `₹${e.exit_price.toFixed(2)}` : "—"}</span>
                    }
                  </td>
                  <td className="px-3 py-2" style={{ color: "var(--text-muted)" }}>{e.shares.toLocaleString("en-IN")}</td>
                  <td className="px-3 py-2 font-semibold"
                      style={{ color: e.pnl != null ? pnlColor(e.pnl) : "var(--text-muted)" }}>
                    {e.pnl != null ? `${e.pnl >= 0 ? "+" : ""}${formatINR(e.pnl)}` : "—"}
                  </td>
                  <td className="px-3 py-2" style={{ color: e.r_multiple != null ? pnlColor(e.r_multiple) : "var(--text-muted)" }}>
                    {e.r_multiple != null ? `${e.r_multiple >= 0 ? "+" : ""}${e.r_multiple.toFixed(2)}R` : "—"}
                  </td>
                  <td className="px-3 py-2 text-xs" style={{ color: "var(--text-muted)" }}>
                    {e.hold_days != null ? `${e.hold_days}d` : "—"}
                  </td>
                  <td className="px-3 py-2 text-xs max-w-xs truncate" style={{ color: "var(--text-muted)" }}>
                    {editing === e.id
                      ? <input type="text" value={editVals.notes}
                               onChange={ev => setEditVals((v: any) => ({ ...v, notes: ev.target.value }))}
                               className="w-32 px-1 py-0.5 rounded text-xs"
                               style={{ backgroundColor: "var(--bg-primary)", border: "1px solid var(--border)", color: "var(--text-primary)" }} />
                      : e.notes}
                  </td>
                  <td className="px-3 py-2">
                    <div className="flex items-center gap-1">
                      {editing === e.id ? (
                        <>
                          <button onClick={() => saveEdit(e.id)} style={{ color: "var(--green)" }}><Check size={13} /></button>
                          <button onClick={() => setEditing(null)} style={{ color: "var(--text-muted)" }}><X size={13} /></button>
                        </>
                      ) : (
                        <>
                          <button onClick={() => startEdit(e)} style={{ color: "var(--text-muted)" }}><Edit2 size={12} /></button>
                          <button onClick={async () => { await deleteJournalEntry(e.id); await mutate() }}
                                  style={{ color: "var(--red)" }}><Trash2 size={12} /></button>
                        </>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

function StatCard({ label, value, green, red }: { label: string; value: string; green?: boolean; red?: boolean }) {
  const color = green ? "var(--green)" : red ? "var(--red)" : "var(--text-primary)"
  return (
    <div className="rounded-xl px-4 py-3" style={{ backgroundColor: "var(--bg-card)", border: "1px solid var(--border)" }}>
      <div className="text-xs mb-1" style={{ color: "var(--text-muted)" }}>{label}</div>
      <div className="text-lg font-bold" style={{ color }}>{value}</div>
    </div>
  )
}

function AddTradeForm({ onSave, onClose }: { onSave: (d: any) => Promise<void>; onClose: () => void }) {
  const [f, setF] = useState({
    ticker: "", pattern: "BREAKOUT", entry_date: new Date().toISOString().slice(0,10),
    entry_price: "", shares: "", stop_price: "", exit_date: "", exit_price: "", notes: "", tags: "",
  })
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    await onSave({
      ticker:      f.ticker.toUpperCase().endsWith(".NS") ? f.ticker.toUpperCase() : f.ticker.toUpperCase() + ".NS",
      pattern:     f.pattern,
      entry_date:  f.entry_date,
      entry_price: parseFloat(f.entry_price),
      shares:      parseInt(f.shares),
      stop_price:  f.stop_price ? parseFloat(f.stop_price) : null,
      exit_date:   f.exit_date  || null,
      exit_price:  f.exit_price ? parseFloat(f.exit_price) : null,
      notes:       f.notes,
      tags:        f.tags,
    })
    setLoading(false)
  }

  return (
    <div className="rounded-xl p-5 space-y-4" style={{ backgroundColor: "var(--bg-card)", border: "1px solid var(--border)" }}>
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Log Trade</h3>
        <button onClick={onClose} style={{ color: "var(--text-muted)" }}><X size={15} /></button>
      </div>
      <form onSubmit={handleSubmit} className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[
          { label: "Ticker *", key: "ticker",       type: "text",   placeholder: "RELIANCE" },
          { label: "Pattern",  key: "pattern",       type: "select" },
          { label: "Entry Date *", key: "entry_date", type: "date" },
          { label: "Entry Price *", key: "entry_price", type: "number", placeholder: "0.00" },
          { label: "Shares *",  key: "shares",       type: "number", placeholder: "0" },
          { label: "Stop Price", key: "stop_price",  type: "number", placeholder: "0.00" },
          { label: "Exit Date",  key: "exit_date",   type: "date" },
          { label: "Exit Price", key: "exit_price",  type: "number", placeholder: "0.00" },
        ].map(({ label, key, type, placeholder }) => (
          <div key={key}>
            <label className="block text-xs mb-1" style={{ color: "var(--text-muted)" }}>{label}</label>
            {type === "select"
              ? <select value={(f as any)[key]} onChange={e => setF(v => ({ ...v, [key]: e.target.value }))} className="w-full rounded-lg px-2.5 py-1.5 text-xs" style={{ backgroundColor: "var(--bg-primary)", border: "1px solid var(--border)", color: "var(--text-primary)" }}>
                  <option>BREAKOUT</option><option>EP</option><option>VCP</option><option>SA</option><option>EMERGING</option><option>S2HIGH</option>
                </select>
              : <input type={type} step={type === "number" ? "0.01" : undefined} placeholder={placeholder}
                       value={(f as any)[key]} onChange={e => setF(v => ({ ...v, [key]: e.target.value }))}
                       className="w-full rounded-lg px-2.5 py-1.5 text-xs"
                       style={{ backgroundColor: "var(--bg-primary)", border: "1px solid var(--border)", color: "var(--text-primary)" }} />}
          </div>
        ))}
        <div className="col-span-2">
          <label className="block text-xs mb-1" style={{ color: "var(--text-muted)" }}>Notes</label>
          <input type="text" placeholder="Optional" value={f.notes} onChange={e => setF(v => ({ ...v, notes: e.target.value }))}
                 className="w-full rounded-lg px-2.5 py-1.5 text-xs"
                 style={{ backgroundColor: "var(--bg-primary)", border: "1px solid var(--border)", color: "var(--text-primary)" }} />
        </div>
        <div className="col-span-2 flex gap-3 items-end">
          <button type="submit" disabled={loading}
                  className="flex-1 py-2 rounded-lg text-sm font-semibold disabled:opacity-50"
                  style={{ backgroundColor: "rgba(0,196,154,0.2)", color: "var(--green)", border: "1px solid rgba(0,196,154,0.3)" }}>
            {loading ? "Saving…" : "Save Trade"}
          </button>
          <button type="button" onClick={onClose}
                  className="flex-1 py-2 rounded-lg text-sm"
                  style={{ border: "1px solid var(--border)", color: "var(--text-muted)" }}>
            Cancel
          </button>
        </div>
      </form>
    </div>
  )
}

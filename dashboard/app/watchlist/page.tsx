"use client"
import { useState } from "react"
import useSWR from "swr"
import { Plus, Trash2, Bell, BellOff, Zap, TrendingUp, Eye } from "lucide-react"
import { fetchWatchlist, addToWatchlist, removeFromWatchlist } from "@/lib/api"
import type { WatchlistItem } from "@/lib/types"

export default function WatchlistPage() {
  const { data: items = [], mutate } = useSWR("watchlist", fetchWatchlist, { refreshInterval: 60_000 })
  const [ticker, setTicker] = useState("")
  const [notes,  setNotes]  = useState("")
  const [alert,  setAlert]  = useState(true)
  const [adding, setAdding] = useState(false)

  const inScan  = items.filter(i => i.in_todays_scan)
  const notScan = items.filter(i => !i.in_todays_scan)

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!ticker.trim()) return
    setAdding(true)
    await addToWatchlist({ ticker: ticker.trim(), notes, alert_on_scan: alert })
    await mutate()
    setTicker("")
    setNotes("")
    setAdding(false)
  }

  return (
    <div className="max-w-3xl mx-auto space-y-5">
      {/* Header */}
      <div>
        <h1 className="text-xl font-bold" style={{ color: "var(--text-primary)" }}>Watchlist</h1>
        <p className="text-xs mt-0.5" style={{ color: "var(--text-muted)" }}>
          {items.length} stocks · {inScan.length} appearing in today's scan
        </p>
      </div>

      {/* Alert hits */}
      {inScan.length > 0 && (
        <div className="rounded-xl p-4 space-y-2"
             style={{ backgroundColor: "rgba(0,196,154,0.06)", border: "1px solid rgba(0,196,154,0.25)" }}>
          <div className="text-sm font-semibold flex items-center gap-2" style={{ color: "var(--green)" }}>
            <Zap size={14} /> In today's scan ({inScan.length})
          </div>
          <div className="flex flex-wrap gap-2">
            {inScan.map(i => (
              <span key={i.id} className="px-2.5 py-1 rounded-lg text-xs font-semibold"
                    style={{ backgroundColor: "rgba(0,196,154,0.15)", color: "var(--green)", border: "1px solid rgba(0,196,154,0.3)" }}>
                {i.ticker.replace(".NS","")}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Add form */}
      <form onSubmit={handleAdd}
            className="rounded-xl p-4 flex flex-wrap gap-3 items-end"
            style={{ backgroundColor: "var(--bg-card)", border: "1px solid var(--border)" }}>
        <div>
          <label className="block text-xs mb-1" style={{ color: "var(--text-muted)" }}>Ticker *</label>
          <input type="text" placeholder="RELIANCE" value={ticker}
                 onChange={e => setTicker(e.target.value.toUpperCase())}
                 className="w-32 rounded-lg px-2.5 py-1.5 text-sm"
                 style={{ backgroundColor: "var(--bg-primary)", border: "1px solid var(--border)", color: "var(--text-primary)" }} />
        </div>
        <div className="flex-1 min-w-40">
          <label className="block text-xs mb-1" style={{ color: "var(--text-muted)" }}>Notes</label>
          <input type="text" placeholder="Watching for breakout..." value={notes}
                 onChange={e => setNotes(e.target.value)}
                 className="w-full rounded-lg px-2.5 py-1.5 text-sm"
                 style={{ backgroundColor: "var(--bg-primary)", border: "1px solid var(--border)", color: "var(--text-primary)" }} />
        </div>
        <div className="flex items-center gap-2">
          <label className="text-xs" style={{ color: "var(--text-muted)" }}>
            <input type="checkbox" checked={alert} onChange={e => setAlert(e.target.checked)} className="mr-1.5" />
            Alert on scan
          </label>
        </div>
        <button type="submit" disabled={adding || !ticker.trim()}
                className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold disabled:opacity-50 whitespace-nowrap"
                style={{ backgroundColor: "rgba(0,196,154,0.15)", color: "var(--green)", border: "1px solid rgba(0,196,154,0.3)" }}>
          <Plus size={13} /> Add to Watchlist
        </button>
      </form>

      {/* Watchlist table */}
      {items.length === 0 ? (
        <div className="flex flex-col items-center justify-center h-40 rounded-xl gap-2"
             style={{ backgroundColor: "var(--bg-card)", border: "1px solid var(--border)" }}>
          <Eye size={24} style={{ color: "var(--text-muted)" }} />
          <p className="text-sm" style={{ color: "var(--text-muted)" }}>No stocks on your watchlist yet.</p>
        </div>
      ) : (
        <div className="rounded-xl overflow-hidden" style={{ border: "1px solid var(--border)" }}>
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="text-xs" style={{ backgroundColor: "var(--bg-card)", color: "var(--text-muted)" }}>
                <th className="px-4 py-2.5 text-left font-medium">Ticker</th>
                <th className="px-4 py-2.5 text-left font-medium">Notes</th>
                <th className="px-4 py-2.5 text-left font-medium">Alert</th>
                <th className="px-4 py-2.5 text-left font-medium">In Scan</th>
                <th className="px-4 py-2.5 text-left font-medium">Added</th>
                <th className="px-4 py-2.5 text-left font-medium"></th>
              </tr>
            </thead>
            <tbody>
              {items.map((item, i) => (
                <tr key={item.id} className="border-t"
                    style={{ backgroundColor: i % 2 === 0 ? "transparent" : "rgba(48,54,61,0.2)", borderColor: "var(--border)" }}>
                  <td className="px-4 py-2.5 font-semibold" style={{ color: "var(--text-primary)" }}>
                    {item.ticker.replace(".NS","")}
                  </td>
                  <td className="px-4 py-2.5 text-xs max-w-xs truncate" style={{ color: "var(--text-muted)" }}>
                    {item.notes || "—"}
                  </td>
                  <td className="px-4 py-2.5">
                    {item.alert_on_scan
                      ? <Bell size={13} style={{ color: "var(--green)" }} />
                      : <BellOff size={13} style={{ color: "var(--text-muted)" }} />}
                  </td>
                  <td className="px-4 py-2.5">
                    {item.in_todays_scan
                      ? <span className="px-2 py-0.5 rounded-full text-xs font-semibold"
                               style={{ backgroundColor: "rgba(0,196,154,0.15)", color: "var(--green)" }}>
                          Yes ⚡
                        </span>
                      : <span className="text-xs" style={{ color: "var(--text-muted)" }}>No</span>}
                  </td>
                  <td className="px-4 py-2.5 text-xs" style={{ color: "var(--text-muted)" }}>
                    {item.created_at.slice(0,10)}
                  </td>
                  <td className="px-4 py-2.5">
                    <button onClick={async () => { await removeFromWatchlist(item.ticker); await mutate() }}
                            style={{ color: "var(--red)" }}>
                      <Trash2 size={13} />
                    </button>
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

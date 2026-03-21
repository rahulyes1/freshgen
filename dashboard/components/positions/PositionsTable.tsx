"use client"
import { useState } from "react"
import { Trash2, Edit2, Check, X } from "lucide-react"
import type { Position } from "@/lib/types"
import { formatINR, pnlColor } from "@/lib/utils"

interface Props {
  positions: Position[]
  onUpdate: (id: number, data: Partial<Position>) => Promise<void>
  onDelete: (id: number) => Promise<void>
}

export default function PositionsTable({ positions, onUpdate, onDelete }: Props) {
  const [editing, setEditing] = useState<number | null>(null)
  const [editVals, setEditVals] = useState<{ stop_price: string; current_price: string; notes: string }>({
    stop_price: "", current_price: "", notes: "",
  })

  const open   = positions.filter(p => p.status === "open")
  const closed = positions.filter(p => p.status === "closed")

  const startEdit = (p: Position) => {
    setEditing(p.id)
    setEditVals({
      stop_price:    String(p.stop_price),
      current_price: String(p.current_price ?? p.entry_price),
      notes:         p.notes ?? "",
    })
  }

  const saveEdit = async (id: number) => {
    await onUpdate(id, {
      stop_price:    parseFloat(editVals.stop_price),
      current_price: parseFloat(editVals.current_price),
      notes:         editVals.notes || undefined,
    })
    setEditing(null)
  }

  const closePosition = async (p: Position) => {
    const price = parseFloat(editVals.current_price) || p.current_price || p.entry_price
    await onUpdate(p.id, {
      exit_price: price,
      exit_date:  new Date().toISOString().slice(0, 10),
      status:     "closed",
    })
    setEditing(null)
  }

  if (positions.length === 0) {
    return (
      <div className="flex items-center justify-center h-40 text-sm"
           style={{ color: "var(--text-muted)" }}>
        No positions yet. Add one from Live Setups.
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {open.length > 0 && (
        <section>
          <h3 className="text-xs font-semibold uppercase tracking-wider mb-3"
              style={{ color: "var(--text-muted)" }}>
            Open ({open.length})
          </h3>
          <div className="overflow-x-auto rounded-xl border" style={{ borderColor: "var(--border)" }}>
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="text-xs" style={{ backgroundColor: "var(--bg-card)", color: "var(--text-muted)" }}>
                  {["Ticker","Pattern","Entry","Stop","Current","Shares","Unr. P&L","Entry Date","Actions"].map(h => (
                    <th key={h} className="px-3 py-2.5 text-left font-medium whitespace-nowrap">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {open.map((p, i) => (
                  <tr key={p.id}
                      style={{ backgroundColor: i % 2 === 0 ? "transparent" : "rgba(48,54,61,0.3)" }}
                      className="border-t"
                  >
                    <td className="px-3 py-2.5 font-semibold" style={{ color: "var(--text-primary)", borderColor: "var(--border)" }}>
                      {p.ticker.replace(".NS", "")}
                    </td>
                    <td className="px-3 py-2.5 text-xs" style={{ color: "var(--blue)", borderColor: "var(--border)" }}>
                      {p.pattern}
                    </td>
                    <td className="px-3 py-2.5" style={{ color: "var(--text-primary)", borderColor: "var(--border)" }}>
                      ₹{p.entry_price.toFixed(2)}
                    </td>
                    {/* Stop — editable */}
                    <td className="px-3 py-2.5" style={{ borderColor: "var(--border)" }}>
                      {editing === p.id
                        ? <input type="number" step="0.01" value={editVals.stop_price}
                                 onChange={e => setEditVals(v => ({ ...v, stop_price: e.target.value }))}
                                 className="w-20 px-1.5 py-0.5 rounded text-xs"
                                 style={{ backgroundColor: "var(--bg-primary)", border: "1px solid var(--border)", color: "var(--text-primary)" }} />
                        : <span style={{ color: "var(--red)" }}>₹{p.stop_price.toFixed(2)}</span>
                      }
                    </td>
                    {/* Current — editable */}
                    <td className="px-3 py-2.5" style={{ borderColor: "var(--border)" }}>
                      {editing === p.id
                        ? <input type="number" step="0.01" value={editVals.current_price}
                                 onChange={e => setEditVals(v => ({ ...v, current_price: e.target.value }))}
                                 className="w-20 px-1.5 py-0.5 rounded text-xs"
                                 style={{ backgroundColor: "var(--bg-primary)", border: "1px solid var(--border)", color: "var(--text-primary)" }} />
                        : <span style={{ color: "var(--text-primary)" }}>
                            {p.current_price ? `₹${p.current_price.toFixed(2)}` : "—"}
                          </span>
                      }
                    </td>
                    <td className="px-3 py-2.5" style={{ color: "var(--text-muted)", borderColor: "var(--border)" }}>
                      {p.shares.toLocaleString("en-IN")}
                    </td>
                    <td className="px-3 py-2.5 font-semibold" style={{ borderColor: "var(--border)" }}>
                      {p.unrealized_pnl !== undefined ? (
                        <span style={{ color: pnlColor(p.unrealized_pnl) }}>
                          {p.unrealized_pnl >= 0 ? "+" : ""}{formatINR(p.unrealized_pnl)}
                          {p.unrealized_pnl_pct !== undefined && (
                            <span className="ml-1 text-xs font-normal">
                              ({p.unrealized_pnl_pct >= 0 ? "+" : ""}{p.unrealized_pnl_pct.toFixed(1)}%)
                            </span>
                          )}
                        </span>
                      ) : "—"}
                    </td>
                    <td className="px-3 py-2.5 text-xs" style={{ color: "var(--text-muted)", borderColor: "var(--border)" }}>
                      {p.entry_date}
                    </td>
                    <td className="px-3 py-2.5" style={{ borderColor: "var(--border)" }}>
                      <div className="flex items-center gap-1.5">
                        {editing === p.id ? (
                          <>
                            <button onClick={() => saveEdit(p.id)} title="Save"
                                    className="p-1 rounded hover:opacity-80"
                                    style={{ color: "var(--green)" }}>
                              <Check size={13} />
                            </button>
                            <button onClick={() => closePosition(p)} title="Close position"
                                    className="p-1 rounded hover:opacity-80 text-xs font-semibold px-2"
                                    style={{ color: "var(--red)", border: "1px solid rgba(255,77,77,0.3)", borderRadius: 4 }}>
                              Exit
                            </button>
                            <button onClick={() => setEditing(null)} title="Cancel"
                                    className="p-1 rounded hover:opacity-80"
                                    style={{ color: "var(--text-muted)" }}>
                              <X size={13} />
                            </button>
                          </>
                        ) : (
                          <>
                            <button onClick={() => startEdit(p)} title="Edit"
                                    className="p-1 rounded hover:opacity-80"
                                    style={{ color: "var(--text-muted)" }}>
                              <Edit2 size={13} />
                            </button>
                            <button onClick={() => onDelete(p.id)} title="Delete"
                                    className="p-1 rounded hover:opacity-80"
                                    style={{ color: "var(--red)" }}>
                              <Trash2 size={13} />
                            </button>
                          </>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {closed.length > 0 && (
        <section>
          <h3 className="text-xs font-semibold uppercase tracking-wider mb-3"
              style={{ color: "var(--text-muted)" }}>
            Closed ({closed.length})
          </h3>
          <div className="overflow-x-auto rounded-xl border" style={{ borderColor: "var(--border)" }}>
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="text-xs" style={{ backgroundColor: "var(--bg-card)", color: "var(--text-muted)" }}>
                  {["Ticker","Pattern","Entry","Exit","Shares","P&L","Entry Date","Exit Date",""].map(h => (
                    <th key={h} className="px-3 py-2.5 text-left font-medium whitespace-nowrap">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {closed.map((p, i) => {
                  const pnl = p.exit_price ? (p.exit_price - p.entry_price) * p.shares : 0
                  return (
                    <tr key={p.id}
                        style={{ backgroundColor: i % 2 === 0 ? "transparent" : "rgba(48,54,61,0.3)", opacity: 0.7 }}
                        className="border-t">
                      <td className="px-3 py-2 font-semibold" style={{ color: "var(--text-primary)", borderColor: "var(--border)" }}>
                        {p.ticker.replace(".NS", "")}
                      </td>
                      <td className="px-3 py-2 text-xs" style={{ color: "var(--blue)", borderColor: "var(--border)" }}>{p.pattern}</td>
                      <td className="px-3 py-2" style={{ color: "var(--text-primary)", borderColor: "var(--border)" }}>₹{p.entry_price.toFixed(2)}</td>
                      <td className="px-3 py-2" style={{ color: "var(--text-primary)", borderColor: "var(--border)" }}>
                        {p.exit_price ? `₹${p.exit_price.toFixed(2)}` : "—"}
                      </td>
                      <td className="px-3 py-2" style={{ color: "var(--text-muted)", borderColor: "var(--border)" }}>
                        {p.shares.toLocaleString("en-IN")}
                      </td>
                      <td className="px-3 py-2 font-semibold" style={{ color: pnlColor(pnl), borderColor: "var(--border)" }}>
                        {pnl >= 0 ? "+" : ""}{formatINR(pnl)}
                      </td>
                      <td className="px-3 py-2 text-xs" style={{ color: "var(--text-muted)", borderColor: "var(--border)" }}>{p.entry_date}</td>
                      <td className="px-3 py-2 text-xs" style={{ color: "var(--text-muted)", borderColor: "var(--border)" }}>{p.exit_date ?? "—"}</td>
                      <td className="px-3 py-2" style={{ borderColor: "var(--border)" }}>
                        <button onClick={() => onDelete(p.id)} title="Remove"
                                className="p-1 rounded hover:opacity-80"
                                style={{ color: "var(--text-muted)" }}>
                          <Trash2 size={13} />
                        </button>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  )
}

"use client"
import { useState } from "react"
import { X } from "lucide-react"
import type { PositionCreate, Setup } from "@/lib/types"

interface Props {
  prefill?: Setup
  onSave:  (data: PositionCreate) => Promise<void>
  onClose: () => void
}

export default function AddPositionModal({ prefill, onSave, onClose }: Props) {
  const [form, setForm] = useState<PositionCreate>({
    ticker:      prefill?.ticker      ?? "",
    pattern:     prefill?.pattern     ?? "BREAKOUT",
    entry_price: prefill?.entry_price ?? 0,
    stop_price:  prefill?.stop_price  ?? 0,
    shares:      prefill?.position_size_shares ?? 1,
    entry_date:  prefill?.date ?? new Date().toISOString().slice(0, 10),
    notes:       "",
  })
  const [loading, setLoading] = useState(false)
  const [error, setError]     = useState<string | null>(null)

  const set = (k: keyof PositionCreate, v: string | number) =>
    setForm(f => ({ ...f, [k]: v }))

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!form.ticker || form.entry_price <= 0 || form.stop_price <= 0 || form.shares <= 0) {
      setError("Please fill all required fields with valid values.")
      return
    }
    setLoading(true)
    setError(null)
    try {
      await onSave(form)
      onClose()
    } catch (err: any) {
      setError(err.message ?? "Failed to save position.")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center"
         style={{ backgroundColor: "rgba(0,0,0,0.6)" }}
         onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="w-full max-w-md rounded-2xl p-6 shadow-2xl"
           style={{ backgroundColor: "var(--bg-card)", border: "1px solid var(--border)" }}>

        {/* Header */}
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-base font-semibold" style={{ color: "var(--text-primary)" }}>
            Add Position
          </h2>
          <button onClick={onClose} className="p-1 rounded hover:opacity-70"
                  style={{ color: "var(--text-muted)" }}>
            <X size={16} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-3.5">
          {/* Ticker + Pattern */}
          <div className="grid grid-cols-2 gap-3">
            <Field label="Ticker *">
              <input type="text" placeholder="RELIANCE.NS" value={form.ticker}
                     onChange={e => set("ticker", e.target.value.toUpperCase())}
                     className="field-input" />
            </Field>
            <Field label="Pattern *">
              <select value={form.pattern} onChange={e => set("pattern", e.target.value)}
                      className="field-input">
                <option value="BREAKOUT">BREAKOUT</option>
                <option value="EP">EP</option>
              </select>
            </Field>
          </div>

          {/* Entry + Stop */}
          <div className="grid grid-cols-2 gap-3">
            <Field label="Entry Price (₹) *">
              <input type="number" step="0.01" min="0" value={form.entry_price || ""}
                     onChange={e => set("entry_price", parseFloat(e.target.value) || 0)}
                     className="field-input" />
            </Field>
            <Field label="Stop Price (₹) *">
              <input type="number" step="0.01" min="0" value={form.stop_price || ""}
                     onChange={e => set("stop_price", parseFloat(e.target.value) || 0)}
                     className="field-input" />
            </Field>
          </div>

          {/* Shares + Date */}
          <div className="grid grid-cols-2 gap-3">
            <Field label="Shares *">
              <input type="number" min="1" value={form.shares || ""}
                     onChange={e => set("shares", parseInt(e.target.value) || 1)}
                     className="field-input" />
            </Field>
            <Field label="Entry Date *">
              <input type="date" value={form.entry_date}
                     onChange={e => set("entry_date", e.target.value)}
                     className="field-input" />
            </Field>
          </div>

          {/* Notes */}
          <Field label="Notes">
            <input type="text" placeholder="Optional" value={form.notes ?? ""}
                   onChange={e => set("notes", e.target.value)}
                   className="field-input" />
          </Field>

          {/* Risk preview */}
          {form.entry_price > 0 && form.stop_price > 0 && form.shares > 0 && (
            <div className="rounded-lg px-3 py-2 text-xs flex justify-between"
                 style={{ backgroundColor: "rgba(0,196,154,0.06)", border: "1px solid rgba(0,196,154,0.15)" }}>
              <span style={{ color: "var(--text-muted)" }}>Risk per share</span>
              <span style={{ color: "var(--red)" }}>
                ₹{(form.entry_price - form.stop_price).toFixed(2)} × {form.shares} = ₹{((form.entry_price - form.stop_price) * form.shares).toFixed(0)}
              </span>
            </div>
          )}

          {error && (
            <p className="text-xs" style={{ color: "var(--red)" }}>{error}</p>
          )}

          <div className="flex gap-3 pt-1">
            <button type="button" onClick={onClose}
                    className="flex-1 py-2 rounded-lg text-sm transition-colors"
                    style={{ border: "1px solid var(--border)", color: "var(--text-muted)" }}>
              Cancel
            </button>
            <button type="submit" disabled={loading}
                    className="flex-1 py-2 rounded-lg text-sm font-semibold transition-colors disabled:opacity-50"
                    style={{ backgroundColor: "rgba(0,196,154,0.2)", color: "var(--green)", border: "1px solid rgba(0,196,154,0.3)" }}>
              {loading ? "Saving…" : "Add Position"}
            </button>
          </div>
        </form>
      </div>

      <style jsx>{`
        .field-input {
          width: 100%;
          padding: 6px 10px;
          border-radius: 8px;
          font-size: 13px;
          background-color: var(--bg-primary);
          border: 1px solid var(--border);
          color: var(--text-primary);
          outline: none;
        }
        .field-input:focus {
          border-color: var(--green);
        }
      `}</style>
    </div>
  )
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="block text-xs mb-1" style={{ color: "var(--text-muted)" }}>{label}</label>
      {children}
    </div>
  )
}

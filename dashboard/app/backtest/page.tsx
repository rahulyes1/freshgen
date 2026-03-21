"use client"
import { useState } from "react"
import { Play, AlertCircle, Clock } from "lucide-react"
import { runBacktest } from "@/lib/api"
import type { BacktestResponse, BacktestStats } from "@/lib/types"
import EquityCurveChart from "@/components/backtest/EquityCurveChart"
import { formatINR } from "@/lib/utils"

const DEFAULT_PARAMS = {
  start: "2020-01-01",
  end:   "2024-12-31",
  universe: "nifty500" as const,
  account_size: 1_000_000,
}

export default function BacktestPage() {
  const [params, setParams]   = useState(DEFAULT_PARAMS)
  const [result, setResult]   = useState<BacktestResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError]     = useState<string | null>(null)

  const handleRun = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await runBacktest(params)
      setResult(res)
    } catch (e: any) {
      setError(e.message ?? "Backtest failed.")
    } finally {
      setLoading(false)
    }
  }

  const s = result?.stats

  return (
    <div className="max-w-6xl mx-auto space-y-5">
      {/* Header */}
      <div>
        <h1 className="text-xl font-bold" style={{ color: "var(--text-primary)" }}>Backtest</h1>
        <p className="text-xs mt-0.5" style={{ color: "var(--text-muted)" }}>
          Qullamaggie Breakout + EP strategy · Nifty 500 universe
        </p>
      </div>

      {/* Controls */}
      <div className="rounded-xl p-4 flex flex-wrap gap-4 items-end"
           style={{ backgroundColor: "var(--bg-card)", border: "1px solid var(--border)" }}>
        <ParamField label="Start Date">
          <input type="date" value={params.start}
                 onChange={e => setParams(p => ({ ...p, start: e.target.value }))}
                 className="ctrl-input" />
        </ParamField>
        <ParamField label="End Date">
          <input type="date" value={params.end}
                 onChange={e => setParams(p => ({ ...p, end: e.target.value }))}
                 className="ctrl-input" />
        </ParamField>
        <ParamField label="Universe">
          <select value={params.universe}
                  onChange={e => setParams(p => ({ ...p, universe: e.target.value as any }))}
                  className="ctrl-input">
            <option value="nifty500">Nifty 500 (~500 stocks)</option>
            <option value="momentum">Momentum (~140 stocks)</option>
            <option value="nifty50">Nifty 50 (50 stocks)</option>
          </select>
        </ParamField>
        <ParamField label="Account Size (₹)">
          <select value={params.account_size}
                  onChange={e => setParams(p => ({ ...p, account_size: parseInt(e.target.value) }))}
                  className="ctrl-input">
            {[500_000, 1_000_000, 2_000_000, 5_000_000].map(v => (
              <option key={v} value={v}>₹{(v / 100_000).toFixed(1)}L</option>
            ))}
          </select>
        </ParamField>

        <button onClick={handleRun} disabled={loading}
                className="flex items-center gap-2 px-5 py-2 rounded-lg text-sm font-semibold transition-colors disabled:opacity-50"
                style={{ backgroundColor: "rgba(0,196,154,0.2)", color: "var(--green)", border: "1px solid rgba(0,196,154,0.3)" }}>
          {loading
            ? <><Clock size={13} className="animate-spin" />Running…</>
            : <><Play size={13} />Run Backtest</>}
        </button>

        {result && (
          <span className="text-xs" style={{ color: "var(--text-muted)" }}>
            Completed in {result.run_duration_seconds.toFixed(1)}s
          </span>
        )}
      </div>

      {/* Error */}
      {error && (
        <div className="flex items-center gap-2 px-4 py-3 rounded-xl text-sm"
             style={{ backgroundColor: "rgba(255,77,77,0.08)", border: "1px solid rgba(255,77,77,0.2)", color: "var(--red)" }}>
          <AlertCircle size={14} />
          {error}
        </div>
      )}

      {/* Loading hint */}
      {loading && (
        <div className="flex items-center justify-center h-40 rounded-xl text-sm"
             style={{ backgroundColor: "var(--bg-card)", border: "1px solid var(--border)", color: "var(--text-muted)" }}>
          Running backtest — this may take 30–60 seconds…
        </div>
      )}

      {/* Results */}
      {s && result && (
        <>
          {/* Stats grid */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <StatCard label="Total Return"   value={`${s.total_return_pct.toFixed(1)}%`}  big green />
            <StatCard label="CAGR"           value={`${s.cagr_pct.toFixed(1)}%`}           big green />
            <StatCard label="Max Drawdown"   value={`${s.max_drawdown_pct.toFixed(1)}%`}   big red />
            <StatCard label="Profit Factor"  value={s.profit_factor.toFixed(2)}             big />
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <StatCard label="Total Trades"  value={String(s.total_trades)} />
            <StatCard label="Win Rate"      value={`${s.win_rate_pct.toFixed(1)}%`} />
            <StatCard label="Avg Win"       value={`${s.avg_win_pct.toFixed(1)}%`}  green />
            <StatCard label="Avg Loss"      value={`${s.avg_loss_pct.toFixed(1)}%`} red />
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <StatCard label="Expectancy"    value={`${s.expectancy_r.toFixed(2)}R`} />
            <StatCard label="Best Trade"    value={`${s.best_trade_r.toFixed(1)}R`}  green />
            <StatCard label="Worst Trade"   value={`${s.worst_trade_r.toFixed(1)}R`} red />
            <StatCard label="Avg Hold Days" value={`${s.avg_hold_days.toFixed(0)}d`} />
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            <StatCard label="Breakout Trades" value={`${s.breakout_trades} · ${s.breakout_win_rate.toFixed(1)}% WR`} />
            <StatCard label="EP Trades"       value={`${s.ep_trades} · ${s.ep_win_rate.toFixed(1)}% WR`} />
            {(s as any).vcp_trades != null && (
              <StatCard label="VCP Trades" value={`${(s as any).vcp_trades} · ${((s as any).vcp_win_rate ?? 0).toFixed(1)}% WR`} />
            )}
          </div>

          <div className="grid grid-cols-2 gap-3">
            <StatCard label="Final Capital"  value={formatINR(params.account_size + s.total_pnl_dollars)} big />
            <StatCard label="Net P&L"        value={formatINR(s.total_pnl_dollars)} big green={s.total_pnl_dollars > 0} red={s.total_pnl_dollars <= 0} />
          </div>

          {/* Chart */}
          <div className="rounded-xl p-4"
               style={{ backgroundColor: "var(--bg-card)", border: "1px solid var(--border)" }}>
            <h3 className="text-sm font-semibold mb-3" style={{ color: "var(--text-primary)" }}>
              Equity Curve &amp; Drawdown
            </h3>
            <EquityCurveChart data={result.equity_curve} initialCapital={params.account_size} />
          </div>

          {/* Trade log */}
          {result.trades.length > 0 && (
            <div className="rounded-xl overflow-hidden"
                 style={{ border: "1px solid var(--border)" }}>
              <div className="px-4 py-3 flex items-center justify-between"
                   style={{ backgroundColor: "var(--bg-card)", borderBottom: "1px solid var(--border)" }}>
                <h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
                  Trade Log ({result.trades.length})
                </h3>
              </div>
              <div className="overflow-x-auto max-h-96">
                <table className="w-full text-xs border-collapse">
                  <thead className="sticky top-0" style={{ backgroundColor: "var(--bg-card)" }}>
                    <tr style={{ color: "var(--text-muted)" }}>
                      {["Ticker","Pat","Entry","Exit","Entry ₹","Exit ₹","P&L","R","Days","Reason"].map(h => (
                        <th key={h} className="px-3 py-2 text-left font-medium whitespace-nowrap">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {result.trades.map((t, i) => (
                      <tr key={i} className="border-t"
                          style={{ backgroundColor: i % 2 === 0 ? "transparent" : "rgba(48,54,61,0.3)", borderColor: "var(--border)" }}>
                        <td className="px-3 py-1.5 font-semibold" style={{ color: "var(--text-primary)" }}>
                          {t.ticker.replace(".NS", "")}
                        </td>
                        <td className="px-3 py-1.5" style={{ color: "var(--blue)" }}>{t.pattern}</td>
                        <td className="px-3 py-1.5" style={{ color: "var(--text-muted)" }}>{t.entry_date}</td>
                        <td className="px-3 py-1.5" style={{ color: "var(--text-muted)" }}>{t.exit_date}</td>
                        <td className="px-3 py-1.5" style={{ color: "var(--text-primary)" }}>₹{t.entry_price.toFixed(2)}</td>
                        <td className="px-3 py-1.5" style={{ color: "var(--text-primary)" }}>₹{t.exit_price.toFixed(2)}</td>
                        <td className="px-3 py-1.5 font-semibold"
                            style={{ color: t.pnl >= 0 ? "var(--green)" : "var(--red)" }}>
                          {t.pnl >= 0 ? "+" : ""}{formatINR(t.pnl)}
                        </td>
                        <td className="px-3 py-1.5"
                            style={{ color: t.r_multiple >= 0 ? "var(--green)" : "var(--red)" }}>
                          {t.r_multiple >= 0 ? "+" : ""}{t.r_multiple.toFixed(2)}R
                        </td>
                        <td className="px-3 py-1.5" style={{ color: "var(--text-muted)" }}>{t.hold_days}d</td>
                        <td className="px-3 py-1.5" style={{ color: "var(--text-muted)" }}>{t.exit_reason}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </>
      )}

      <style jsx>{`
        .ctrl-input {
          padding: 6px 10px;
          border-radius: 8px;
          font-size: 12px;
          background-color: var(--bg-primary);
          border: 1px solid var(--border);
          color: var(--text-primary);
          outline: none;
          min-width: 140px;
        }
        .ctrl-input:focus { border-color: var(--green); }
      `}</style>
    </div>
  )
}

function ParamField({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1">
      <label className="text-xs" style={{ color: "var(--text-muted)" }}>{label}</label>
      {children}
    </div>
  )
}

function StatCard({ label, value, big, green, red }: {
  label: string; value: string
  big?: boolean; green?: boolean; red?: boolean
}) {
  const color = green ? "var(--green)" : red ? "var(--red)" : "var(--text-primary)"
  return (
    <div className="rounded-xl px-4 py-3"
         style={{ backgroundColor: "var(--bg-card)", border: "1px solid var(--border)" }}>
      <div className="text-xs mb-1" style={{ color: "var(--text-muted)" }}>{label}</div>
      <div className={big ? "text-xl font-bold" : "text-sm font-semibold"} style={{ color }}>{value}</div>
    </div>
  )
}

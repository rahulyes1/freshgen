"use client"
import { useState, useEffect } from "react"
import { RefreshCw, Wifi, WifiOff, TrendingUp, TrendingDown } from "lucide-react"
import { fetchHealth } from "@/lib/api"
import type { HealthResponse } from "@/lib/types"

export default function TopBar() {
  const [health,    setHealth]    = useState<HealthResponse | null>(null)
  const [online,    setOnline]    = useState<boolean | null>(null)
  const [time,      setTime]      = useState("")

  useEffect(() => {
    const check = async () => {
      try {
        const h = await fetchHealth()
        setHealth(h)
        setOnline(h.status === "ok")
      } catch {
        setOnline(false)
      }
    }
    check()
    const iv = setInterval(check, 60_000)
    return () => clearInterval(iv)
  }, [])

  useEffect(() => {
    const tick = () => {
      const now = new Date()
      setTime(now.toLocaleTimeString("en-IN", { timeZone: "Asia/Kolkata", hour12: false }) + " IST")
    }
    tick()
    const iv = setInterval(tick, 1000)
    return () => clearInterval(iv)
  }, [])

  return (
    <header className="h-11 flex items-center justify-between px-6 border-b text-xs"
            style={{ backgroundColor: "var(--bg-card)", borderColor: "var(--border)", color: "var(--text-muted)" }}>
      <span className="font-mono">{time}</span>
      <div className="flex items-center gap-4">

        {/* Market regime */}
        {health && (
          <span className="flex items-center gap-1.5">
            {health.market_bullish
              ? <TrendingUp size={11} style={{ color: "var(--green)" }} />
              : <TrendingDown size={11} style={{ color: "var(--red)" }} />}
            <span style={{ color: health.market_bullish ? "var(--green)" : "var(--red)" }}>
              {health.market_bullish ? "Bull market" : "Bear market"}
            </span>
            {health.nifty500_price && (
              <span style={{ color: "var(--text-muted)" }}>
                · N500: {health.nifty500_price.toLocaleString("en-IN")}
              </span>
            )}
          </span>
        )}

        {/* Scheduler */}
        {health?.scheduler_running && (
          <span className="flex items-center gap-1.5">
            <RefreshCw size={11} className="text-green-400" />
            <span>Scheduler active — daily 9:00 AM IST</span>
          </span>
        )}

        {/* Kite data source */}
        {health && (
          <span className="flex items-center gap-1.5 px-2 py-0.5 rounded"
                style={{
                  backgroundColor: health.kite_connected ? "rgba(0,196,154,0.08)" : "rgba(255,180,0,0.08)",
                  border: `1px solid ${health.kite_connected ? "rgba(0,196,154,0.25)" : "rgba(255,180,0,0.25)"}`,
                }}>
            <span style={{
              width: 6, height: 6, borderRadius: "50%",
              backgroundColor: health.kite_connected ? "var(--green)" : "rgb(255,180,0)",
              display: "inline-block",
            }} />
            <span style={{ color: health.kite_connected ? "var(--green)" : "rgb(255,180,0)" }}>
              {health.kite_connected ? `Kite · ${health.kite_user}` : "yfinance"}
            </span>
          </span>
        )}

        {/* API status */}
        <span className="flex items-center gap-1.5">
          {online === true  && <><Wifi size={12} className="text-green-400" /><span className="text-green-400">API connected</span></>}
          {online === false && <><WifiOff size={12} className="text-red-400" /><span className="text-red-400">API offline</span></>}
          {online === null  && <span>Checking...</span>}
        </span>
      </div>
    </header>
  )
}

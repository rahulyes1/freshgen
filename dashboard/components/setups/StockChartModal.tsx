"use client"
import { useEffect, useRef, useState } from "react"
import { X, TrendingUp, TrendingDown } from "lucide-react"
import { fetchChart } from "@/lib/api"
import type { ChartBar } from "@/lib/types"
import {
  createChart,
  CandlestickSeries,
  HistogramSeries,
  LineSeries,
  CrosshairMode,
  type IChartApi,
  type Time,
} from "lightweight-charts"

interface Props {
  ticker: string
  entryPrice?: number
  stopPrice?: number
  onClose: () => void
}

const PERIODS = [
  { label: "3M", days: 90 },
  { label: "6M", days: 180 },
  { label: "1Y", days: 365 },
]

export default function StockChartModal({ ticker, entryPrice, stopPrice, onClose }: Props) {
  const [bars, setBars] = useState<ChartBar[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [days, setDays] = useState(180)
  const [ohlc, setOhlc] = useState<ChartBar | null>(null)

  const chartContainerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)

  const symbol = ticker.replace(".NS", "")
  const last = bars[bars.length - 1]
  const prev = bars.length > 1 ? bars[bars.length - 2] : null
  const change = last && prev ? last.close - prev.close : 0
  const changePct = prev ? (change / prev.close) * 100 : 0
  const bullish = change >= 0

  // The bar to show in the OHLC overlay — hovered bar or last bar
  const displayBar = ohlc || last

  // Fetch data
  useEffect(() => {
    setLoading(true)
    setError(null)
    fetchChart(ticker, days)
      .then((r) => setBars(r.bars))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [ticker, days])

  // Build chart
  useEffect(() => {
    if (!bars.length || !chartContainerRef.current) return

    // Cleanup previous
    chartRef.current?.remove()

    const container = chartContainerRef.current
    const chartHeight = Math.min(window.innerHeight * 0.72, 520)

    const chart = createChart(container, {
      width: container.clientWidth,
      height: chartHeight,
      layout: {
        background: { color: "#0d1117" },
        textColor: "#8b949e",
        fontFamily: "'Inter', -apple-system, sans-serif",
        fontSize: 11,
        attributionLogo: false,
      },
      grid: {
        vertLines: { color: "rgba(48,54,61,0.4)" },
        horzLines: { color: "rgba(48,54,61,0.4)" },
      },
      crosshair: {
        mode: CrosshairMode.Normal,
        vertLine: {
          color: "rgba(139,148,158,0.5)",
          width: 1 as any,
          style: 2 as any,
          labelBackgroundColor: "#30363d",
        },
        horzLine: {
          color: "rgba(139,148,158,0.5)",
          width: 1 as any,
          style: 2 as any,
          labelBackgroundColor: "#30363d",
        },
      },
      timeScale: {
        borderColor: "#30363d",
        timeVisible: false,
        rightOffset: 8,
        barSpacing: bars.length <= 90 ? 8 : bars.length <= 180 ? 6 : 4,
        minBarSpacing: 3,
      },
      rightPriceScale: {
        borderColor: "#30363d",
        scaleMargins: { top: 0.05, bottom: 0.2 },
      },
      handleScale: { axisPressedMouseMove: { time: true, price: true } },
      handleScroll: { vertTouchDrag: false },
    })
    chartRef.current = chart

    // ── Candlestick series ──────────────────────────────────
    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: "#26a69a",
      downColor: "#ef5350",
      borderUpColor: "#26a69a",
      borderDownColor: "#ef5350",
      wickUpColor: "#26a69a",
      wickDownColor: "#ef5350",
    })
    candleSeries.setData(
      bars.map((b) => ({
        time: b.date as Time,
        open: b.open,
        high: b.high,
        low: b.low,
        close: b.close,
      }))
    )

    // ── Volume as overlay histogram (bottom 18% of chart) ───
    const volSeries = chart.addSeries(HistogramSeries, {
      priceFormat: { type: "volume" },
      priceLineVisible: false,
      lastValueVisible: false,
      priceScaleId: "volume",
    })
    chart.priceScale("volume").applyOptions({
      scaleMargins: { top: 0.75, bottom: 0 },
    })
    volSeries.setData(
      bars.map((b) => ({
        time: b.date as Time,
        value: b.volume,
        color:
          b.close >= b.open
            ? "rgba(38,166,154,0.5)"
            : "rgba(239,83,80,0.5)",
      }))
    )

    // ── EMA 10 (purple) ─────────────────────────────────────
    const ema10Bars = bars.filter((b) => b.ema10 != null)
    if (ema10Bars.length) {
      const s = chart.addSeries(LineSeries, {
        color: "#a78bfa",
        lineWidth: 1,
        priceLineVisible: false,
        lastValueVisible: false,
        crosshairMarkerVisible: false,
      })
      s.setData(ema10Bars.map((b) => ({ time: b.date as Time, value: b.ema10! })))
    }

    // ── SMA 50 (blue) ───────────────────────────────────────
    const sma50Bars = bars.filter((b) => b.sma50 != null)
    if (sma50Bars.length) {
      const s = chart.addSeries(LineSeries, {
        color: "#60a5fa",
        lineWidth: 1,
        priceLineVisible: false,
        lastValueVisible: false,
        crosshairMarkerVisible: false,
      })
      s.setData(sma50Bars.map((b) => ({ time: b.date as Time, value: b.sma50! })))
    }

    // ── SMA 200 (amber) ─────────────────────────────────────
    const sma200Bars = bars.filter((b) => b.sma200 != null)
    if (sma200Bars.length) {
      const s = chart.addSeries(LineSeries, {
        color: "#f59e0b",
        lineWidth: 1,
        lineStyle: 2,
        priceLineVisible: false,
        lastValueVisible: false,
        crosshairMarkerVisible: false,
      })
      s.setData(sma200Bars.map((b) => ({ time: b.date as Time, value: b.sma200! })))
    }

    // ── Entry / Stop price lines ────────────────────────────
    if (entryPrice) {
      candleSeries.createPriceLine({
        price: entryPrice,
        color: "#26a69a",
        lineWidth: 1,
        lineStyle: 2,
        axisLabelVisible: true,
        title: `Entry ₹${entryPrice}`,
      })
    }
    if (stopPrice) {
      candleSeries.createPriceLine({
        price: stopPrice,
        color: "#ef5350",
        lineWidth: 1,
        lineStyle: 2,
        axisLabelVisible: true,
        title: `Stop ₹${stopPrice}`,
      })
    }

    // ── Crosshair → OHLC overlay ────────────────────────────
    chart.subscribeCrosshairMove((param) => {
      if (!param.time || !param.seriesData?.size) {
        setOhlc(null)
        return
      }
      const candle = param.seriesData.get(candleSeries) as any
      const vol = param.seriesData.get(volSeries) as any
      if (candle) {
        // Find matching bar for full data
        const dateStr = param.time as string
        const bar = bars.find((b) => b.date === dateStr)
        if (bar) setOhlc(bar)
      }
    })

    // Fit content
    chart.timeScale().fitContent()

    // Resize handler
    const ro = new ResizeObserver(() => {
      if (container) chart.applyOptions({ width: container.clientWidth })
    })
    ro.observe(container)

    return () => {
      ro.disconnect()
      chart.remove()
      chartRef.current = null
    }
  }, [bars, entryPrice, stopPrice])

  // Close on Escape
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose()
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [onClose])

  const fmtVol = (v: number) => {
    if (v >= 10_000_000) return (v / 10_000_000).toFixed(2) + " Cr"
    if (v >= 100_000) return (v / 100_000).toFixed(2) + " L"
    if (v >= 1000) return (v / 1000).toFixed(1) + "K"
    return v.toString()
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-3"
      style={{ backgroundColor: "rgba(0,0,0,0.8)" }}
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div
        className="w-full max-w-6xl rounded-xl shadow-2xl flex flex-col"
        style={{
          backgroundColor: "#0d1117",
          border: "1px solid #30363d",
          maxHeight: "95vh",
        }}
      >
        {/* ── Header ─────────────────────────────────────────── */}
        <div
          className="flex items-center justify-between px-4 py-2.5 border-b"
          style={{ borderColor: "#21262d" }}
        >
          <div className="flex items-center gap-4">
            <span className="text-base font-bold" style={{ color: "#e6edf3" }}>
              {symbol}
            </span>
            {last && (
              <div className="flex items-center gap-2 text-sm">
                <span
                  className="font-bold"
                  style={{ color: bullish ? "#26a69a" : "#ef5350" }}
                >
                  ₹{last.close.toLocaleString("en-IN", { minimumFractionDigits: 2 })}
                </span>
                <span
                  className="flex items-center gap-0.5 text-xs"
                  style={{ color: bullish ? "#26a69a" : "#ef5350" }}
                >
                  {bullish ? <TrendingUp size={12} /> : <TrendingDown size={12} />}
                  {bullish ? "+" : ""}
                  {change.toFixed(2)} ({bullish ? "+" : ""}
                  {changePct.toFixed(2)}%)
                </span>
              </div>
            )}
          </div>
          <div className="flex items-center gap-2">
            <div className="flex gap-1">
              {PERIODS.map((p) => (
                <button
                  key={p.days}
                  onClick={() => setDays(p.days)}
                  className="px-3 py-1 rounded text-xs font-medium transition-all"
                  style={{
                    backgroundColor:
                      days === p.days ? "rgba(38,166,154,0.2)" : "transparent",
                    color: days === p.days ? "#26a69a" : "#8b949e",
                    border:
                      days === p.days
                        ? "1px solid rgba(38,166,154,0.4)"
                        : "1px solid #30363d",
                  }}
                >
                  {p.label}
                </button>
              ))}
            </div>
            <button
              onClick={onClose}
              className="p-1 rounded hover:bg-white/5 transition-colors"
              style={{ color: "#8b949e" }}
            >
              <X size={16} />
            </button>
          </div>
        </div>

        {/* ── OHLC data overlay + Legend ──────────────────────── */}
        {displayBar && !loading && (
          <div className="px-4 py-1" style={{ borderBottom: "1px solid #21262d" }}>
            <div className="flex items-center gap-4 text-xs flex-wrap">
              {/* OHLC values */}
              <span className="font-mono" style={{ color: "#6e7681" }}>
                {displayBar.date}
              </span>
              <span style={{ color: "#8b949e" }}>
                O <span style={{ color: displayBar.close >= displayBar.open ? "#26a69a" : "#ef5350" }}>
                  {displayBar.open.toFixed(2)}
                </span>
              </span>
              <span style={{ color: "#8b949e" }}>
                H <span style={{ color: "#26a69a" }}>{displayBar.high.toFixed(2)}</span>
              </span>
              <span style={{ color: "#8b949e" }}>
                L <span style={{ color: "#ef5350" }}>{displayBar.low.toFixed(2)}</span>
              </span>
              <span style={{ color: "#8b949e" }}>
                C <span className="font-semibold" style={{ color: displayBar.close >= displayBar.open ? "#26a69a" : "#ef5350" }}>
                  {displayBar.close.toFixed(2)}
                </span>
              </span>
              <span style={{ color: "#6e7681" }}>Vol {fmtVol(displayBar.volume)}</span>

              {/* Separator */}
              <span style={{ color: "#30363d" }}>|</span>

              {/* MA values */}
              <span className="flex items-center gap-1">
                <span className="w-2.5 h-[2px] rounded inline-block" style={{ backgroundColor: "#a78bfa" }} />
                <span style={{ color: "#a78bfa" }}>10</span>
                {displayBar.ema10 && <span style={{ color: "#8b949e" }}>{displayBar.ema10.toFixed(2)}</span>}
              </span>
              <span className="flex items-center gap-1">
                <span className="w-2.5 h-[2px] rounded inline-block" style={{ backgroundColor: "#60a5fa" }} />
                <span style={{ color: "#60a5fa" }}>50</span>
                {displayBar.sma50 && <span style={{ color: "#8b949e" }}>{displayBar.sma50.toFixed(2)}</span>}
              </span>
              <span className="flex items-center gap-1">
                <span className="w-2.5 h-[2px] rounded inline-block" style={{ backgroundColor: "#f59e0b" }} />
                <span style={{ color: "#f59e0b" }}>200</span>
                {displayBar.sma200 && <span style={{ color: "#8b949e" }}>{displayBar.sma200.toFixed(2)}</span>}
              </span>
            </div>
          </div>
        )}

        {/* ── Chart canvas ───────────────────────────────────── */}
        <div className="flex-1 px-1 pb-1">
          {loading && (
            <div
              className="flex items-center justify-center h-[400px] text-sm"
              style={{ color: "#8b949e" }}
            >
              Loading chart…
            </div>
          )}
          {error && (
            <div
              className="flex items-center justify-center h-[400px] text-sm"
              style={{ color: "#ef5350" }}
            >
              {error}
            </div>
          )}
          {!loading && !error && bars.length > 0 && (
            <div ref={chartContainerRef} className="w-full" />
          )}
        </div>
      </div>
    </div>
  )
}

"use client"
import { useEffect, useRef, useState, useCallback } from "react"
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
  type ISeriesApi,
  type CandlestickData,
  type HistogramData,
  type LineData,
  type Time,
} from "lightweight-charts"

interface Props {
  ticker: string
  entryPrice?: number
  stopPrice?: number
  onClose: () => void
}

const PERIODS = [
  { label: "3M",  days: 90 },
  { label: "6M",  days: 180 },
  { label: "1Y",  days: 365 },
]

export default function StockChartModal({ ticker, entryPrice, stopPrice, onClose }: Props) {
  const [bars, setBars]       = useState<ChartBar[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState<string | null>(null)
  const [days, setDays]       = useState(180)

  const chartContainerRef = useRef<HTMLDivElement>(null)
  const volumeContainerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const volumeChartRef = useRef<IChartApi | null>(null)

  const symbol  = ticker.replace(".NS", "")
  const last    = bars[bars.length - 1]
  const prev    = bars.length > 1 ? bars[bars.length - 2] : null
  const change  = last && prev ? last.close - prev.close : 0
  const changePct = prev ? (change / prev.close * 100) : 0
  const bullish = change >= 0

  // Fetch data
  useEffect(() => {
    setLoading(true)
    setError(null)
    fetchChart(ticker, days)
      .then(r => setBars(r.bars))
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [ticker, days])

  // Build charts
  useEffect(() => {
    if (!bars.length || !chartContainerRef.current || !volumeContainerRef.current) return

    // Cleanup previous
    chartRef.current?.remove()
    volumeChartRef.current?.remove()

    const commonOpts = {
      layout: {
        background: { color: "#0d1117" },
        textColor: "#8b949e",
        fontFamily: "'Inter', -apple-system, sans-serif",
        fontSize: 11,
      },
      grid: {
        vertLines: { color: "rgba(48,54,61,0.5)" },
        horzLines: { color: "rgba(48,54,61,0.5)" },
      },
      crosshair: {
        mode: CrosshairMode.Normal,
        vertLine: { color: "rgba(139,148,158,0.4)", width: 1 as any, style: 2 as any, labelBackgroundColor: "#30363d" },
        horzLine: { color: "rgba(139,148,158,0.4)", width: 1 as any, style: 2 as any, labelBackgroundColor: "#30363d" },
      },
      timeScale: {
        borderColor: "#30363d",
        timeVisible: false,
        rightOffset: 5,
        barSpacing: Math.max(4, Math.min(10, 800 / bars.length)),
      },
      rightPriceScale: {
        borderColor: "#30363d",
        scaleMargins: { top: 0.08, bottom: 0.08 },
      },
      handleScale: { axisPressedMouseMove: { time: true, price: true } },
      handleScroll: { vertTouchDrag: false },
    }

    // ── Price chart ──────────────────────────────────────────
    const chart = createChart(chartContainerRef.current, {
      ...commonOpts,
      width: chartContainerRef.current.clientWidth,
      height: 380,
    })
    chartRef.current = chart

    // Candlestick series
    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: "#00c49a",
      downColor: "#ff4d4d",
      borderUpColor: "#00c49a",
      borderDownColor: "#ff4d4d",
      wickUpColor: "#00c49a",
      wickDownColor: "#ff4d4d",
    })

    const candleData: CandlestickData[] = bars.map(b => ({
      time: b.date as Time,
      open: b.open,
      high: b.high,
      low: b.low,
      close: b.close,
    }))
    candleSeries.setData(candleData)

    // EMA 10 line
    const ema10Data: LineData[] = bars
      .filter(b => b.ema10 != null)
      .map(b => ({ time: b.date as Time, value: b.ema10! }))
    if (ema10Data.length) {
      const ema10Series = chart.addSeries(LineSeries, {
        color: "#a78bfa",
        lineWidth: 1,
        priceLineVisible: false,
        lastValueVisible: false,
        crosshairMarkerVisible: false,
      })
      ema10Series.setData(ema10Data)
    }

    // SMA 50 line
    const sma50Data: LineData[] = bars
      .filter(b => b.sma50 != null)
      .map(b => ({ time: b.date as Time, value: b.sma50! }))
    if (sma50Data.length) {
      const sma50Series = chart.addSeries(LineSeries, {
        color: "#60a5fa",
        lineWidth: 1,
        priceLineVisible: false,
        lastValueVisible: false,
        crosshairMarkerVisible: false,
      })
      sma50Series.setData(sma50Data)
    }

    // SMA 200 line
    const sma200Data: LineData[] = bars
      .filter(b => b.sma200 != null)
      .map(b => ({ time: b.date as Time, value: b.sma200! }))
    if (sma200Data.length) {
      const sma200Series = chart.addSeries(LineSeries, {
        color: "#f59e0b",
        lineWidth: 1,
        lineStyle: 2, // dashed
        priceLineVisible: false,
        lastValueVisible: false,
        crosshairMarkerVisible: false,
      })
      sma200Series.setData(sma200Data)
    }

    // Entry / Stop price lines
    if (entryPrice) {
      candleSeries.createPriceLine({
        price: entryPrice,
        color: "#00c49a",
        lineWidth: 1,
        lineStyle: 2,
        axisLabelVisible: true,
        title: `Entry ₹${entryPrice}`,
      })
    }
    if (stopPrice) {
      candleSeries.createPriceLine({
        price: stopPrice,
        color: "#ff4d4d",
        lineWidth: 1,
        lineStyle: 2,
        axisLabelVisible: true,
        title: `Stop ₹${stopPrice}`,
      })
    }

    // ── Volume chart ─────────────────────────────────────────
    const volChart = createChart(volumeContainerRef.current, {
      ...commonOpts,
      width: volumeContainerRef.current.clientWidth,
      height: 100,
      rightPriceScale: {
        borderColor: "#30363d",
        scaleMargins: { top: 0.1, bottom: 0 },
      },
      timeScale: {
        ...commonOpts.timeScale,
        visible: true,
      },
    })
    volumeChartRef.current = volChart

    const volSeries = volChart.addSeries(HistogramSeries, {
      priceFormat: { type: "volume" },
      priceLineVisible: false,
      lastValueVisible: false,
    })

    const volData: HistogramData[] = bars.map(b => ({
      time: b.date as Time,
      value: b.volume,
      color: b.close >= b.open ? "rgba(0,196,154,0.45)" : "rgba(255,77,77,0.45)",
    }))
    volSeries.setData(volData)

    // Sync crosshair between price and volume charts
    chart.timeScale().subscribeVisibleLogicalRangeChange(range => {
      if (range) volChart.timeScale().setVisibleLogicalRange(range)
    })
    volChart.timeScale().subscribeVisibleLogicalRangeChange(range => {
      if (range) chart.timeScale().setVisibleLogicalRange(range)
    })

    // Sync crosshair movement
    chart.subscribeCrosshairMove(param => {
      if (param.time) {
        volChart.setCrosshairPosition(NaN, param.time, volSeries)
      } else {
        volChart.clearCrosshairPosition()
      }
    })
    volChart.subscribeCrosshairMove(param => {
      if (param.time) {
        chart.setCrosshairPosition(NaN, param.time, candleSeries)
      } else {
        chart.clearCrosshairPosition()
      }
    })

    // Fit content
    chart.timeScale().fitContent()
    volChart.timeScale().fitContent()

    // Resize handler
    const resizeObserver = new ResizeObserver(() => {
      if (chartContainerRef.current && volumeContainerRef.current) {
        chart.applyOptions({ width: chartContainerRef.current.clientWidth })
        volChart.applyOptions({ width: volumeContainerRef.current.clientWidth })
      }
    })
    if (chartContainerRef.current) resizeObserver.observe(chartContainerRef.current)

    return () => {
      resizeObserver.disconnect()
      chart.remove()
      volChart.remove()
      chartRef.current = null
      volumeChartRef.current = null
    }
  }, [bars, entryPrice, stopPrice])

  // Close on Escape
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose() }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [onClose])

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4"
         style={{ backgroundColor: "rgba(0,0,0,0.75)" }}
         onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="w-full max-w-5xl rounded-2xl shadow-2xl flex flex-col"
           style={{ backgroundColor: "#0d1117", border: "1px solid #30363d", maxHeight: "95vh" }}>

        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3 border-b"
             style={{ borderColor: "#30363d" }}>
          <div className="flex items-center gap-4">
            <div className="text-lg font-bold" style={{ color: "#e6edf3" }}>{symbol}</div>
            {last && (
              <div className="flex items-center gap-3 text-sm">
                <span className="font-bold text-base" style={{ color: bullish ? "#00c49a" : "#ff4d4d" }}>
                  ₹{last.close.toLocaleString("en-IN", { minimumFractionDigits: 2 })}
                </span>
                <span className="flex items-center gap-0.5" style={{ color: bullish ? "#00c49a" : "#ff4d4d" }}>
                  {bullish ? <TrendingUp size={13} /> : <TrendingDown size={13} />}
                  {bullish ? "+" : ""}{change.toFixed(2)} ({bullish ? "+" : ""}{changePct.toFixed(2)}%)
                </span>
              </div>
            )}
          </div>
          <div className="flex items-center gap-3">
            {/* Period selector */}
            <div className="flex gap-1">
              {PERIODS.map(p => (
                <button key={p.days} onClick={() => setDays(p.days)}
                        className="px-3 py-1 rounded-md text-xs font-medium transition-all"
                        style={{
                          backgroundColor: days === p.days ? "rgba(0,196,154,0.2)" : "rgba(48,54,61,0.6)",
                          color:           days === p.days ? "#00c49a" : "#8b949e",
                          border:          days === p.days ? "1px solid rgba(0,196,154,0.4)" : "1px solid #30363d",
                        }}>
                  {p.label}
                </button>
              ))}
            </div>
            <button onClick={onClose} className="p-1.5 rounded-md hover:opacity-70 transition-opacity"
                    style={{ color: "#8b949e" }}>
              <X size={18} />
            </button>
          </div>
        </div>

        {/* Chart area */}
        <div className="flex-1 px-2 pt-2 pb-1 overflow-hidden">
          {loading && (
            <div className="flex items-center justify-center h-[480px] text-sm" style={{ color: "#8b949e" }}>
              Loading chart…
            </div>
          )}
          {error && (
            <div className="flex items-center justify-center h-[480px] text-sm" style={{ color: "#ff4d4d" }}>
              {error}
            </div>
          )}
          {!loading && !error && bars.length > 0 && (
            <>
              <div ref={chartContainerRef} className="w-full" />
              <div ref={volumeContainerRef} className="w-full" />

              {/* Legend */}
              <div className="flex items-center gap-5 px-3 py-2 text-xs" style={{ color: "#8b949e" }}>
                <span className="flex items-center gap-1.5">
                  <span className="w-4 h-0.5 rounded inline-block" style={{ backgroundColor: "#a78bfa" }} />
                  EMA 10
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="w-4 h-0.5 rounded inline-block" style={{ backgroundColor: "#60a5fa" }} />
                  SMA 50
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="w-4 h-0.5 rounded inline-block" style={{ backgroundColor: "#f59e0b" }} />
                  SMA 200
                </span>
                {entryPrice && (
                  <span className="flex items-center gap-1.5">
                    <span className="w-4 h-0 border-t border-dashed inline-block" style={{ borderColor: "#00c49a" }} />
                    Entry ₹{entryPrice}
                  </span>
                )}
                {stopPrice && (
                  <span className="flex items-center gap-1.5">
                    <span className="w-4 h-0 border-t border-dashed inline-block" style={{ borderColor: "#ff4d4d" }} />
                    Stop ₹{stopPrice}
                  </span>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}

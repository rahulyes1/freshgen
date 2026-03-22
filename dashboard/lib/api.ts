import type {
  ScanResponse, Position, PositionCreate, PositionUpdate,
  BacktestResponse, ScanHistoryEntry,
} from "./types"

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  })
  if (!res.ok) {
    const err = await res.text()
    throw new Error(`${res.status}: ${err}`)
  }
  return res.json() as Promise<T>
}

// ── Scan ──────────────────────────────────────────────────────

export async function fetchScan(universe = "nifty500", force = false): Promise<ScanResponse> {
  const q = new URLSearchParams({ universe, ...(force ? { force: "true" } : {}) })
  return request<ScanResponse>(`/scan?${q}`)
}

export async function fetchScanHistory(): Promise<ScanHistoryEntry[]> {
  return request<ScanHistoryEntry[]>("/scan/history")
}

// ── Positions ─────────────────────────────────────────────────

export async function fetchPositions(status?: "open" | "closed"): Promise<Position[]> {
  const q = status ? `?status=${status}` : ""
  return request<Position[]>(`/positions${q}`)
}

export async function createPosition(data: PositionCreate): Promise<Position> {
  return request<Position>("/positions", {
    method: "POST",
    body: JSON.stringify(data),
  })
}

export async function updatePosition(id: number, data: PositionUpdate): Promise<Position> {
  return request<Position>(`/positions/${id}`, {
    method: "PUT",
    body: JSON.stringify(data),
  })
}

export async function deletePosition(id: number): Promise<void> {
  await fetch(`${API}/positions/${id}`, { method: "DELETE" })
}

// ── Backtest ──────────────────────────────────────────────────

export interface BacktestParams {
  start?: string
  end?: string
  universe?: "nifty500" | "momentum" | "nifty50" | "custom"
  tickers?: string[]
  account_size?: number
}

export async function runBacktest(params: BacktestParams = {}): Promise<BacktestResponse> {
  return request<BacktestResponse>("/backtest", {
    method: "POST",
    body: JSON.stringify({
      start: params.start ?? "2020-01-01",
      end: params.end ?? "2024-12-31",
      universe: params.universe ?? "momentum",
      tickers: params.tickers ?? null,
      account_size: params.account_size ?? 1000000,
    }),
  })
}

// ── Journal ───────────────────────────────────────────────────

export async function fetchJournal(): Promise<import("./types").JournalEntry[]> {
  return request("/journal")
}
export async function fetchJournalAnalytics(): Promise<import("./types").JournalAnalytics> {
  return request("/journal/analytics")
}
export async function createJournalEntry(data: any) {
  return request("/journal", { method: "POST", body: JSON.stringify(data) })
}
export async function updateJournalEntry(id: number, data: any) {
  return request(`/journal/${id}`, { method: "PUT", body: JSON.stringify(data) })
}
export async function deleteJournalEntry(id: number) {
  await fetch(`${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/journal/${id}`, { method: "DELETE" })
}
export function exportJournalUrl() {
  return `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/journal/export`
}

// ── Watchlist ─────────────────────────────────────────────────

export async function fetchWatchlist(): Promise<import("./types").WatchlistItem[]> {
  return request("/watchlist")
}
export async function addToWatchlist(data: { ticker: string; notes?: string; alert_on_scan?: boolean }) {
  return request("/watchlist", { method: "POST", body: JSON.stringify(data) })
}
export async function removeFromWatchlist(ticker: string) {
  await fetch(`${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/watchlist/${ticker}`, { method: "DELETE" })
}

// ── Price refresh ─────────────────────────────────────────────

export async function refreshPrices(): Promise<{ updated: number; stop_alerts: any[] }> {
  return request("/positions/refresh-prices", { method: "POST" })
}

// ── Chart ─────────────────────────────────────────────────────

export async function fetchChart(ticker: string, days = 120) {
  return request<{ ticker: string; bars: import("./types").ChartBar[] }>(`/chart/${ticker}?days=${days}`)
}

// ── Sectors ───────────────────────────────────────────────────

export async function fetchSectorPerformance(): Promise<{ sectors: import("./types").SectorPerf[]; count: number }> {
  return request("/sectors/performance")
}

// ── Announcements ─────────────────────────────────────────────

export async function fetchAnnouncements(days = 7): Promise<import("./types").AnnouncementsResponse> {
  return request(`/announcements?days=${days}`)
}

// ── Market Quadrant ───────────────────────────────────────────

export async function fetchMarketQuadrant(): Promise<import("./types").MarketQuadrant> {
  return request("/market-quadrant")
}

export async function refreshMarketQuadrant(): Promise<void> {
  await request("/market-quadrant/refresh", { method: "POST" })
}

// ── Momentum ─────────────────────────────────────────────────

export async function fetchMomentum(): Promise<import("./types").MomentumResponse> {
  return request<import("./types").MomentumResponse>("/momentum")
}

// ── Health ────────────────────────────────────────────────────

export async function fetchHealth(): Promise<import("./types").HealthResponse> {
  return request<import("./types").HealthResponse>("/health")
}

// ── Paper Trading ─────────────────────────────────────────────

export async function fetchPaperTrades(status?: "open" | "closed"): Promise<import("./types").PaperTrade[]> {
  const q = status ? `?status=${status}` : ""
  return request(`/paper${q}`)
}

export async function fetchPaperStats(): Promise<import("./types").PaperStats> {
  return request("/paper/stats")
}

export async function createPaperTrade(data: any) {
  return request("/paper", { method: "POST", body: JSON.stringify(data) })
}

export async function updatePaperTrade(id: number, data: any) {
  return request(`/paper/${id}`, { method: "PUT", body: JSON.stringify(data) })
}

export async function deletePaperTrade(id: number) {
  await fetch(`${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/paper/${id}`, { method: "DELETE" })
}

export async function refreshPaperPrices(): Promise<{ updated: number }> {
  return request("/paper/refresh-prices", { method: "POST" })
}

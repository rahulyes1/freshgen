export interface Setup {
  ticker: string
  date: string
  pattern: "BREAKOUT" | "EP" | "VCP" | "SA" | "EMERGING" | "S2HIGH"
  patterns: string   // All detected patterns, comma-separated (e.g. "BREAKOUT, S2HIGH")
  entry_price: number
  stop_price: number
  risk_pct: number
  volume_ratio: number
  distance_52w_pct: number
  base_weeks: number | string
  gap_pct: number
  atr14: number
  rs_rank: number
  near_earnings: boolean
  eps_qoq: number
  eps_yoy: number
  revenue_qoq: number
  revenue_yoy: number
  has_announcement: boolean
  strong_catalyst: boolean
  grade: string
  regime_size_pct: number
  position_size_shares: number
  position_value: number
  risk_amount: number
}

export interface PaperTrade {
  id: number
  ticker: string
  pattern: string
  entry_price: number
  stop_price: number
  shares: number
  entry_date: string
  signal_date: string
  current_price: number | null
  exit_price: number | null
  exit_date: string | null
  exit_reason: string
  status: "open" | "closed"
  notes: string
  created_at: string
  unrealized_pnl: number | null
  unrealized_pnl_pct: number | null
  pnl: number | null
  pnl_pct: number | null
  r_multiple: number | null
  hold_days: number | null
}

export interface PaperStats {
  total: number
  closed: number
  open: number
  win_rate: number
  profit_factor: number
  expectancy_r: number
  total_pnl: number
  avg_r: number
  best_r: number
  worst_r: number
  by_pattern: Record<string, { trades: number; wins: number; total_pnl: number }>
}

export interface ScanResponse {
  scan_date: string
  setups: Setup[]
  total_found: number
  universe_size: number
  scan_duration_seconds: number
  cached: boolean
  stale: boolean
}

export interface HealthResponse {
  status: string
  timestamp: string
  scheduler_running: boolean
  db_ok: boolean
  market_bullish: boolean
  regime_note: string
  nifty500_price: number | null
  nifty500_sma200: number | null
  kite_connected: boolean
  kite_user: string
  data_source: "kite" | "yfinance"
}

export interface ChartBar {
  date: string
  open: number
  high: number
  low: number
  close: number
  volume: number
  ema10: number | null
  sma50: number | null
  sma200: number | null
}

export interface Position {
  id: number
  ticker: string
  pattern: string
  entry_price: number
  stop_price: number
  current_price?: number
  shares: number
  entry_date: string
  exit_price?: number
  exit_date?: string
  status: "open" | "closed"
  notes?: string
  unrealized_pnl?: number
  unrealized_pnl_pct?: number
  risk_amount: number
  created_at: string
}

export interface PositionCreate {
  ticker: string
  pattern: string
  entry_price: number
  stop_price: number
  shares: number
  entry_date: string
  notes?: string
}

export interface PositionUpdate {
  current_price?: number
  stop_price?: number
  exit_price?: number
  exit_date?: string
  status?: "open" | "closed"
  notes?: string
}

export interface JournalEntry {
  id: number
  ticker: string
  pattern: string
  entry_date: string
  entry_price: number
  shares: number
  stop_price: number | null
  exit_date: string | null
  exit_price: number | null
  notes: string
  tags: string
  created_at: string
  pnl: number | null
  pnl_pct: number | null
  r_multiple: number | null
  hold_days: number | null
  status: "open" | "closed"
}

export interface JournalAnalytics {
  total: number
  closed: number
  open: number
  win_rate: number
  profit_factor: number
  total_pnl: number
  avg_win: number
  avg_loss: number
  avg_r: number
  best_r: number
  worst_r: number
  expectancy_r: number
  avg_hold_days: number
  by_pattern: Record<string, { trades: number; wins: number; total_pnl: number }>
  monthly: Record<string, { trades: number; pnl: number }>
}

export interface WatchlistItem {
  id: number
  ticker: string
  notes: string
  alert_on_scan: boolean
  created_at: string
  in_todays_scan: boolean
}

export interface EquityPoint {
  date: string
  value: number
}

export interface TradeRecord {
  ticker: string
  pattern: string
  entry_date: string
  exit_date: string
  entry_price: number
  exit_price: number
  exit_reason: string
  shares: number
  pnl: number
  pnl_pct: number
  r_multiple: number
  hold_days: number
}

export interface BacktestStats {
  total_trades: number
  winners: number
  losers: number
  win_rate_pct: number
  avg_win_pct: number
  avg_loss_pct: number
  profit_factor: number
  expectancy_r: number
  avg_r: number
  total_pnl_dollars: number
  total_return_pct: number
  cagr_pct: number
  max_drawdown_pct: number
  best_trade_r: number
  worst_trade_r: number
  avg_hold_days: number
  breakout_trades: number
  breakout_win_rate: number
  ep_trades: number
  ep_win_rate: number
}

export interface BacktestResponse {
  stats: BacktestStats
  equity_curve: EquityPoint[]
  trades: TradeRecord[]
  run_duration_seconds: number
}

export interface SectorPerf {
  sector: string
  ticker: string
  price: number
  sma50: number | null
  above_sma50: boolean
  return_1d: number | null
  return_1w: number | null
  return_1m: number | null
  return_3m: number | null
  status: "HOT" | "WARM" | "COLD" | "WEAK"
}

export interface Announcement {
  symbol: string
  company: string
  subject: string
  category: "Results" | "Concall" | "Board Meeting" | "Dividend" | "Buyback" | "Corporate Action"
  date: string
  datetime: string
}

export interface AnnouncementsResponse {
  announcements: Announcement[]
  count: number
  days: number
}

export interface UpgradeCondition {
  metric: string
  current: number
  needs: number
  gap: number
}

export interface MarketQuadrant {
  bias: "BULL" | "BEAR"
  trend: "UP" | "DOWN"
  swing: "HOT" | "WARM" | "COOL" | "COLD"
  momentum: "RISING" | "FALLING"
  swing_confidence: number
  momentum_change: number
  pct_above_10: number
  pct_above_50: number
  pct_above_200: number
  above_10: number
  above_50: number
  above_200: number
  total: number
  nnh_20: number
  nnh_65: number
  nnh_52w: number
  new_highs: number
  new_lows: number
  overall: "INVEST" | "SELECTIVE" | "CASH"
  phase_weeks: number
  thrust_detected: boolean
  to_upgrade: { to: string; conditions: UpgradeCondition[] }[]
  updated_at: string
}

export interface ScanHistoryEntry {
  id: number
  scan_date: string
  total_found: number
  universe_sz: number
  duration_s: number
  created_at: string
}

export interface MomentumLeader {
  ticker: string
  close: number
  rs_rank: number
  distance_52w_pct: number
  above_sma50: boolean
  above_sma200: boolean
  volume_ratio: number
  atr14: number
  sector: string
}

export interface MomentumResponse {
  leaders: MomentumLeader[]
  count: number
  cached: boolean
}

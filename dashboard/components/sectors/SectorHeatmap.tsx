"use client"

// Sector groupings for NSE / Nifty 500 universe
const SECTORS: Record<string, string[]> = {
  "Banking & Finance": ["HDFCBANK","ICICIBANK","KOTAKBANK","AXISBANK","SBIN","INDUSINDBK","BANDHANBNK","FEDERALBNK","IDFCFIRSTB","RBLBANK","BAJFINANCE","BAJAJFINSV","CHOLAFIN","MUTHOOTFIN","MANAPPURAM","SBICARD","HDFCAMC","ICICIGI","NAUKRI"],
  "IT & Tech":         ["TCS","INFY","HCLTECH","WIPRO","TECHM","LTIM","PERSISTENT","COFORGE","MPHASIS","OFSS"],
  "Auto & EV":         ["MARUTI","TATAMOTORS","M&M","BAJAJ-AUTO","HEROMOTOCO","EICHERMOT","TVSMOTOR","MOTHERSON","BALKRISIND","BHARATFORG"],
  "Pharma":            ["SUNPHARMA","DRREDDY","CIPLA","DIVISLAB","BIOCON","AUROPHARMA","LUPIN","TORNTPHARM","ALKEM","IPCALAB"],
  "Metals & Mining":   ["TATASTEEL","JSWSTEEL","HINDALCO","VEDL","SAIL","NMDC","NATIONALUM","HINDZINC","APL","RATNAMANI"],
  "Energy & Oil":      ["RELIANCE","ONGC","BPCL","IOC","HINDPETRO","GAIL","IGL","MGL","PETRONET","ATGL"],
  "FMCG":              ["HINDUNILVR","ITC","NESTLEIND","BRITANNIA","DABUR","MARICO","COLPAL","GODREJCP","EMAMILTD","VBL"],
  "Capital Goods":     ["LT","SIEMENS","ABB","BHEL","HAVELLS","CUMMINSIND","THERMAX","VOLTAS","GRINDWELL","AIAENG"],
  "Real Estate":       ["DLF","GODREJPROP","OBEROIRLTY","PRESTIGE","BRIGADE","SOBHA","SUNTECK","MAHINDCIE","NUVOCO","SIGNATURE"],
  "Chemicals":         ["PIDILITIND","AAPL","ATUL","DEEPAKNTR","NAVINFLUOR","FINEORG","GALAXYSURF","TATACHEM","GNFC","ALKYLAMINE"],
}

interface SetupCount {
  [sector: string]: { count: number; tickers: string[] }
}

interface Props {
  setupTickers: string[]  // tickers from today's scan (without .NS)
}

function intensity(count: number): string {
  if (count === 0) return "rgba(48,54,61,0.4)"
  if (count === 1) return "rgba(0,196,154,0.15)"
  if (count === 2) return "rgba(0,196,154,0.30)"
  if (count === 3) return "rgba(0,196,154,0.45)"
  return "rgba(0,196,154,0.65)"
}

export default function SectorHeatmap({ setupTickers }: Props) {
  const sectorData: SetupCount = {}

  for (const [sector, members] of Object.entries(SECTORS)) {
    const hits = members.filter(m => setupTickers.includes(m))
    sectorData[sector] = { count: hits.length, tickers: hits }
  }

  // Sort by count descending
  const sorted = Object.entries(sectorData).sort((a, b) => b[1].count - a[1].count)
  const maxCount = Math.max(...sorted.map(s => s[1].count), 1)

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
      {sorted.map(([sector, data]) => (
        <div key={sector}
             className="rounded-xl p-3.5 flex flex-col gap-1.5 transition-all hover:scale-[1.02]"
             style={{
               backgroundColor: intensity(data.count),
               border: `1px solid ${data.count > 0 ? "rgba(0,196,154,0.3)" : "var(--border)"}`,
             }}>
          <div className="text-xs font-semibold leading-tight"
               style={{ color: data.count > 0 ? "var(--green)" : "var(--text-muted)" }}>
            {sector}
          </div>
          <div className="text-2xl font-bold tabular-nums"
               style={{ color: data.count > 0 ? "var(--text-primary)" : "var(--text-muted)" }}>
            {data.count}
          </div>
          {data.tickers.length > 0 && (
            <div className="flex flex-wrap gap-1 mt-0.5">
              {data.tickers.map(t => (
                <span key={t} className="text-xs px-1.5 py-0.5 rounded"
                      style={{ backgroundColor: "rgba(0,196,154,0.15)", color: "var(--green)" }}>
                  {t}
                </span>
              ))}
            </div>
          )}
          {/* Mini bar */}
          <div className="h-1 rounded-full mt-1 overflow-hidden"
               style={{ backgroundColor: "rgba(48,54,61,0.6)" }}>
            <div className="h-full rounded-full transition-all"
                 style={{
                   width: `${(data.count / maxCount) * 100}%`,
                   backgroundColor: "var(--green)",
                 }} />
          </div>
        </div>
      ))}
    </div>
  )
}

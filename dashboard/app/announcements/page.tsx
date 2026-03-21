"use client"
import { useState } from "react"
import useSWR from "swr"
import { RefreshCw, Bell, Calendar, Building2 } from "lucide-react"
import { fetchAnnouncements } from "@/lib/api"
import type { Announcement } from "@/lib/types"

const CATEGORIES = ["All", "Results", "Concall", "Board Meeting", "Dividend", "Buyback", "Corporate Action"] as const
type Filter = typeof CATEGORIES[number]

const CATEGORY_STYLE: Record<string, { bg: string; color: string; border: string }> = {
  Results:          { bg: "rgba(0,196,154,0.12)",  color: "var(--green)", border: "rgba(0,196,154,0.3)"  },
  Concall:          { bg: "rgba(77,159,255,0.12)", color: "var(--blue)",  border: "rgba(77,159,255,0.3)" },
  "Board Meeting":  { bg: "rgba(168,85,247,0.12)", color: "#a855f7",      border: "rgba(168,85,247,0.3)" },
  Dividend:         { bg: "rgba(251,191,36,0.12)", color: "#f59e0b",      border: "rgba(251,191,36,0.3)" },
  Buyback:          { bg: "rgba(249,115,22,0.12)", color: "#f97316",      border: "rgba(249,115,22,0.3)" },
  "Corporate Action":{ bg: "rgba(236,72,153,0.12)", color: "#ec4899",    border: "rgba(236,72,153,0.3)" },
}

export default function AnnouncementsPage() {
  const [days,   setDays]   = useState(7)
  const [filter, setFilter] = useState<Filter>("All")

  const { data, isLoading, mutate } = useSWR(
    `announcements-${days}`,
    () => fetchAnnouncements(days),
    { refreshInterval: 1800_000 }, // refresh every 30 min
  )

  const announcements: Announcement[] = data?.announcements ?? []
  const filtered = filter === "All" ? announcements : announcements.filter(a => a.category === filter)

  // Count per category
  const counts: Record<string, number> = {}
  for (const a of announcements) {
    counts[a.category] = (counts[a.category] ?? 0) + 1
  }

  return (
    <div className="max-w-5xl mx-auto space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold flex items-center gap-2" style={{ color: "var(--text-primary)" }}>
            <Bell size={18} style={{ color: "var(--green)" }} />
            Corporate Announcements
          </h1>
          <p className="text-xs mt-0.5" style={{ color: "var(--text-muted)" }}>
            NSE results · concalls · board meetings · live from NSE India
          </p>
        </div>
        <div className="flex items-center gap-2">
          {/* Days selector */}
          <select value={days}
                  onChange={e => setDays(Number(e.target.value))}
                  className="rounded-lg px-2.5 py-1.5 text-xs"
                  style={{ backgroundColor: "var(--bg-primary)", border: "1px solid var(--border)", color: "var(--text-primary)" }}>
            <option value={3}>Last 3 days</option>
            <option value={7}>Last 7 days</option>
            <option value={14}>Last 14 days</option>
            <option value={30}>Last 30 days</option>
          </select>
          <button onClick={() => mutate()}
                  className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs"
                  style={{ backgroundColor: "rgba(77,159,255,0.12)", color: "var(--blue)", border: "1px solid rgba(77,159,255,0.3)" }}>
            <RefreshCw size={12} className={isLoading ? "animate-spin" : ""} />
            Refresh
          </button>
        </div>
      </div>

      {/* Category stats bar */}
      <div className="grid grid-cols-3 sm:grid-cols-6 gap-2">
        {(["Results", "Concall", "Board Meeting", "Dividend", "Buyback", "Corporate Action"] as const).map(cat => {
          const s = CATEGORY_STYLE[cat]
          return (
            <button key={cat}
                    onClick={() => setFilter(filter === cat ? "All" : cat)}
                    className="rounded-xl px-3 py-2 text-center transition-all"
                    style={{
                      backgroundColor: filter === cat ? s.bg : "var(--bg-card)",
                      border: `1px solid ${filter === cat ? s.border : "var(--border)"}`,
                    }}>
              <div className="text-lg font-bold" style={{ color: filter === cat ? s.color : "var(--text-primary)" }}>
                {counts[cat] ?? 0}
              </div>
              <div className="text-xs mt-0.5" style={{ color: "var(--text-muted)" }}>{cat}</div>
            </button>
          )
        })}
      </div>

      {/* Filter pills */}
      <div className="flex gap-2 flex-wrap">
        {CATEGORIES.map(cat => (
          <button key={cat}
                  onClick={() => setFilter(cat)}
                  className="px-3 py-1 rounded-full text-xs transition-colors"
                  style={{
                    backgroundColor: filter === cat ? "rgba(0,196,154,0.15)" : "rgba(48,54,61,0.6)",
                    color: filter === cat ? "var(--green)" : "var(--text-muted)",
                    border: `1px solid ${filter === cat ? "rgba(0,196,154,0.3)" : "var(--border)"}`,
                    fontWeight: filter === cat ? 600 : 400,
                  }}>
            {cat} {cat !== "All" && counts[cat] ? `(${counts[cat]})` : ""}
          </button>
        ))}
      </div>

      {/* Loading */}
      {isLoading && (
        <div className="space-y-3">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="h-20 rounded-xl animate-pulse"
                 style={{ backgroundColor: "var(--bg-card)", border: "1px solid var(--border)" }} />
          ))}
        </div>
      )}

      {/* Empty state */}
      {!isLoading && filtered.length === 0 && (
        <div className="flex flex-col items-center justify-center h-48 rounded-xl gap-3"
             style={{ backgroundColor: "var(--bg-card)", border: "1px solid var(--border)" }}>
          <Bell size={28} style={{ color: "var(--text-muted)" }} />
          <p className="text-sm" style={{ color: "var(--text-muted)" }}>
            {announcements.length === 0
              ? "No announcements found — NSE API may be temporarily unavailable"
              : `No ${filter} announcements in the last ${days} days`}
          </p>
        </div>
      )}

      {/* Announcement cards */}
      {!isLoading && filtered.length > 0 && (
        <div className="space-y-2">
          <p className="text-xs" style={{ color: "var(--text-muted)" }}>
            {filtered.length} announcement{filtered.length !== 1 ? "s" : ""} · sorted newest first
          </p>
          {filtered.map((a, i) => (
            <AnnouncementCard key={`${a.symbol}-${a.datetime}-${i}`} announcement={a} />
          ))}
        </div>
      )}
    </div>
  )
}

function AnnouncementCard({ announcement: a }: { announcement: Announcement }) {
  const s = CATEGORY_STYLE[a.category] ?? CATEGORY_STYLE["Results"]
  const dateLabel = new Date(a.date).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" })

  return (
    <div className="rounded-xl px-4 py-3 flex items-start gap-4 transition-all hover:scale-[1.005]"
         style={{ backgroundColor: "var(--bg-card)", border: "1px solid var(--border)" }}>
      {/* Category badge */}
      <div className="flex-shrink-0 mt-0.5">
        <span className="px-2 py-1 rounded-lg text-xs font-semibold whitespace-nowrap"
              style={{ backgroundColor: s.bg, color: s.color, border: `1px solid ${s.border}` }}>
          {a.category}
        </span>
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="font-bold text-sm" style={{ color: "var(--text-primary)" }}>
            {a.symbol}
          </span>
          {a.company && a.company !== a.symbol && (
            <span className="text-xs truncate max-w-xs" style={{ color: "var(--text-muted)" }}>
              {a.company}
            </span>
          )}
        </div>
        <p className="text-xs mt-1 leading-relaxed" style={{ color: "var(--text-muted)" }}>
          {a.subject}
        </p>
      </div>

      {/* Date */}
      <div className="flex-shrink-0 flex items-center gap-1 text-xs" style={{ color: "var(--text-muted)" }}>
        <Calendar size={11} />
        {dateLabel}
      </div>
    </div>
  )
}

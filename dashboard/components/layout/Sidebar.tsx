"use client"
import Link from "next/link"
import { usePathname } from "next/navigation"
import { BarChart2, TrendingUp, BookOpen, Grid, Activity, PenLine, Eye, FlaskConical, Network, Bell, Layers } from "lucide-react"
import { cn } from "@/lib/utils"

const nav = [
  { href: "/setups",       label: "Live Setups",  icon: TrendingUp   },
  { href: "/positions",    label: "Positions",    icon: BookOpen     },
  { href: "/journal",      label: "Journal",      icon: PenLine      },
  { href: "/watchlist",    label: "Watchlist",    icon: Eye          },
  { href: "/paper",        label: "Paper Trades", icon: FlaskConical },
  { href: "/backtest",       label: "Backtest",       icon: BarChart2    },
  { href: "/announcements",  label: "Announcements",  icon: Bell         },
  { href: "/quadrant",       label: "Market Quadrant", icon: Layers       },
  { href: "/sectors",        label: "Sectors",        icon: Grid         },
  { href: "/architecture",   label: "System Map",     icon: Network      },
]

export default function Sidebar() {
  const path = usePathname()
  return (
    <aside className="w-56 flex-shrink-0 flex flex-col border-r"
           style={{ backgroundColor: "var(--bg-card)", borderColor: "var(--border)" }}>
      {/* Logo */}
      <div className="px-5 py-5 border-b" style={{ borderColor: "var(--border)" }}>
        <div className="flex items-center gap-2">
          <Activity size={20} color="var(--green)" />
          <div>
            <div className="text-sm font-bold" style={{ color: "var(--text-primary)" }}>
              Q-Scanner
            </div>
            <div className="text-xs" style={{ color: "var(--text-muted)" }}>
              Nifty 500
            </div>
          </div>
        </div>
      </div>

      {/* Nav links */}
      <nav className="flex-1 p-3 space-y-1">
        {nav.map(({ href, label, icon: Icon }) => {
          const active = path.startsWith(href)
          return (
            <Link key={href} href={href}
              className={cn(
                "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors",
                active
                  ? "font-semibold"
                  : "hover:opacity-80"
              )}
              style={{
                backgroundColor: active ? "rgba(0,196,154,0.12)" : "transparent",
                color: active ? "var(--green)" : "var(--text-muted)",
              }}
            >
              <Icon size={16} />
              {label}
            </Link>
          )
        })}
      </nav>

      {/* Footer */}
      <div className="px-4 py-3 text-xs border-t" style={{ borderColor: "var(--border)", color: "var(--text-muted)" }}>
        Qullamaggie Method
      </div>
    </aside>
  )
}

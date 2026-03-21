import type { Metadata } from "next"
import "./globals.css"
import Sidebar from "@/components/layout/Sidebar"
import TopBar  from "@/components/layout/TopBar"

export const metadata: Metadata = {
  title: "Q-Scanner — Nifty 500",
  description: "Qullamaggie swing-trading scanner for NSE India",
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="h-full">
      <body className="h-full flex flex-col antialiased" style={{ backgroundColor: "var(--bg-primary)", color: "var(--text-primary)" }}>
        <TopBar />
        <div className="flex flex-1 overflow-hidden">
          <Sidebar />
          <main className="flex-1 overflow-y-auto p-6">
            {children}
          </main>
        </div>
      </body>
    </html>
  )
}

import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatINR(amount: number): string {
  if (Math.abs(amount) >= 10_000_000) {
    return `₹${(amount / 10_000_000).toFixed(2)}Cr`
  }
  if (Math.abs(amount) >= 100_000) {
    return `₹${(amount / 100_000).toFixed(2)}L`
  }
  return `₹${amount.toLocaleString("en-IN", { maximumFractionDigits: 0 })}`
}

export function formatPct(value: number, decimals = 1): string {
  const sign = value >= 0 ? "+" : ""
  return `${sign}${value.toFixed(decimals)}%`
}

export function formatR(value: number): string {
  const sign = value >= 0 ? "+" : ""
  return `${sign}${value.toFixed(2)}R`
}

export function pnlColor(value: number): string {
  if (value > 0) return "var(--green)"
  if (value < 0) return "var(--red)"
  return "var(--text-muted)"
}

export function patternColor(pattern: string): string {
  if (pattern === "EP")       return "bg-blue-500/20 text-blue-300 border-blue-500/40"
  if (pattern === "VCP")      return "bg-purple-500/20 text-purple-300 border-purple-500/40"
  if (pattern === "SA")       return "bg-amber-500/20 text-amber-300 border-amber-500/40"
  if (pattern === "EMERGING") return "bg-gray-500/20 text-gray-300 border-gray-500/40"
  if (pattern === "S2HIGH")   return "bg-cyan-500/20 text-cyan-300 border-cyan-500/40"
  return "bg-green-500/20 text-green-300 border-green-500/40"
}

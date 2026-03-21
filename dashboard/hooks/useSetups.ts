"use client"
import useSWR from "swr"
import { fetchScan } from "@/lib/api"
import type { Setup } from "@/lib/types"

export function useSetups(universe = "nifty500") {
  const { data, error, isLoading, mutate } = useSWR(
    `scan-${universe}`,
    () => fetchScan(universe),
    { refreshInterval: 0, revalidateOnFocus: false }
  )
  return {
    setups:   (data?.setups ?? []) as Setup[],
    meta:     data,
    error,
    isLoading,
    refresh:  mutate,
  }
}

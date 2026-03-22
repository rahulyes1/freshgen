"use client"
import useSWR from "swr"
import { useRef } from "react"
import { fetchScan } from "@/lib/api"
import type { Setup } from "@/lib/types"

export function useSetups(universe = "nifty500") {
  const forceRef = useRef(false)
  const { data, error, isLoading, isValidating, mutate } = useSWR(
    `scan-${universe}`,
    () => fetchScan(universe, forceRef.current),
    { refreshInterval: 0, revalidateOnFocus: false }
  )
  return {
    setups:    (data?.setups ?? []) as Setup[],
    meta:      data,
    error,
    isLoading: isLoading || isValidating,
    refresh:   () => {
      forceRef.current = true
      return mutate().finally(() => { forceRef.current = false })
    },
  }
}

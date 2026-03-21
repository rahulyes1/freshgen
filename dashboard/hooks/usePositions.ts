"use client"
import useSWR from "swr"
import { fetchPositions, createPosition, updatePosition, deletePosition } from "@/lib/api"
import type { Position, PositionCreate, PositionUpdate } from "@/lib/types"

export function usePositions(status?: "open" | "closed") {
  const key = status ? `positions-${status}` : "positions-all"
  const { data, error, isLoading, mutate } = useSWR<Position[]>(
    key,
    () => fetchPositions(status),
    { refreshInterval: 30_000 }
  )

  async function add(pos: PositionCreate) {
    await createPosition(pos)
    await mutate()
  }

  async function update(id: number, updates: PositionUpdate) {
    await updatePosition(id, updates)
    await mutate()
  }

  async function remove(id: number) {
    await deletePosition(id)
    await mutate()
  }

  return {
    positions: data ?? [],
    error,
    isLoading,
    add,
    update,
    remove,
    refresh: mutate,
  }
}

import { API_BASE } from './constants'
import type { GameState } from './types'

export async function fetchGameState(): Promise<GameState> {
  const res = await fetch(`${API_BASE}/state`, { cache: 'no-store' })
  if (!res.ok) throw new Error(`API error: ${res.status}`)
  return res.json()
}

export async function resetGame(): Promise<void> {
  const res = await fetch(`${API_BASE}/reset`, { method: 'POST' })
  if (!res.ok) throw new Error(`API error: ${res.status}`)
}

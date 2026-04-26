'use client'

import { create } from 'zustand'
import type {
  GameState, GameEvent, Company, CEOId,
  DirectorMode, DirectorPhase, DemoEvent, ConnectionLine, PopupMessage,
} from '@/lib/types'
import { DEMO_SCRIPT } from '@/lib/demoScript'
import { CEO_IDS, COMPANY_MAP } from '@/lib/constants'

// ─── Module-level director control ───
let directorActive = false
let directorEpoch = 0
const pendingTimeouts = new Set<ReturnType<typeof setTimeout>>()

function clearPending() {
  for (const t of pendingTimeouts) clearTimeout(t)
  pendingTimeouts.clear()
}

function sleep(ms: number, epoch: number): Promise<void> {
  return new Promise((resolve, reject) => {
    const t = setTimeout(() => {
      pendingTimeouts.delete(t)
      if (directorEpoch !== epoch) {
        reject(new Error('epoch_changed'))
      } else {
        resolve()
      }
    }, ms)
    pendingTimeouts.add(t)
  })
}

// ─── Initial demo state ───
function makeInitialCompanies(): Company[] {
  return CEO_IDS.map(id => ({
    id,
    name: COMPANY_MAP[id].name,
    sector: COMPANY_MAP[id].sector,
    cash: 50,
    market_share: 14.29,
    stock_price: 100,
    reputation: 0.70,
    alive: true,
    stock_history: [100],
  }))
}

function makeInitialGameState(): GameState {
  return {
    turn: 0,
    max_turns: 12,
    status: 'in_progress',
    current_active_ceo: null,
    companies: makeInitialCompanies(),
    recent_emails: [],
    press_wire: [],
    active_partnerships: [],
    recent_actions: [],
    events: [],
  }
}

// Only these event types trigger cinematic banners
const BANNER_EVENT_TYPES = ['BETRAYAL', 'BANKRUPTCY', 'HOSTILE_TAKEOVER']

// ─── Store interface ───
interface GameStore {
  state: GameState
  isLive: boolean
  error: string | null
  newEvents: GameEvent[]

  mode: DirectorMode
  phase: DirectorPhase
  isRunning: boolean
  commsLog: string[]
  connectionLines: ConnectionLine[]
  popupMessages: PopupMessage[]
  reactingCeos: Set<CEOId>
  showControls: boolean

  // Legacy compat
  isPolling: boolean
  demoTurn: number
  isAutoPlaying: boolean
  isPausedForBanner: boolean

  // Actions
  setState: (state: GameState) => void
  startPolling: () => void
  stopPolling: () => void
  clearNewEvents: () => void
  resumeAutoPlay: () => void

  startDirector: () => void
  stopDirector: () => void
  toggleControls: () => void

  setDemoTurn: (turn: number) => void
  nextTurn: () => void
  prevTurn: () => void
  startAutoPlay: () => void
  stopAutoPlay: () => void

  // Internal
  _addCommsLog: (msg: string) => void
  _setPhase: (phase: DirectorPhase) => void
  _setActiveCeo: (ceo: CEOId | null) => void
  _addConnectionLine: (line: ConnectionLine) => void
  _removeConnectionLine: (id: string) => void
  _addPopupMessage: (msg: PopupMessage) => void
  _removePopupMessage: (id: string) => void
  _addReactingCeo: (ceo: CEOId) => void
  _removeReactingCeo: (ceo: CEOId) => void
  _applyStatChanges: (changes: DemoEvent['stat_changes']) => void
  _addGameEvent: (event: GameEvent) => void
  _addEmail: (from: CEOId, to: CEOId, text: string, turn: number) => void
  _addPartnership: (a: CEOId, b: CEOId, turn: number) => void
  _setTurn: (turn: number) => void
}

export const useGameStore = create<GameStore>((set, get) => ({
  state: makeInitialGameState(),
  isLive: false,
  error: null,
  newEvents: [],

  mode: 'demo',
  phase: 'IDLE',
  isRunning: false,
  commsLog: ['[SYSTEM] BOARDROOM v2.0 initialized.'],
  connectionLines: [],
  popupMessages: [],
  reactingCeos: new Set(),
  showControls: false,

  isPolling: false,
  demoTurn: 0,
  isAutoPlaying: false,
  isPausedForBanner: false,

  setState: (state) => set({ state }),

  // Polling is now a no-op — director drives everything in demo mode
  startPolling: () => {},
  stopPolling: () => {},

  clearNewEvents: () => set({ newEvents: [] }),
  resumeAutoPlay: () => set({ isPausedForBanner: false }),

  startDirector: () => {
    // Guard: only one director at a time
    if (get().isRunning) return
    directorEpoch++
    directorActive = true
    clearPending()
    const epoch = directorEpoch

    set({
      isRunning: true,
      mode: 'demo',
      state: makeInitialGameState(),
      demoTurn: 0,
      phase: 'IDLE',
      commsLog: ['[SYSTEM] Director started.'],
      connectionLines: [],
      popupMessages: [],
      newEvents: [],
    })

    runDemoLoop(epoch, get)
  },

  stopDirector: () => {
    directorActive = false
    directorEpoch++
    clearPending()
    set({
      isRunning: false,
      phase: 'IDLE',
      connectionLines: [],
      popupMessages: [],
    })
  },

  toggleControls: () => set((s) => ({ showControls: !s.showControls })),

  setDemoTurn: () => {},
  nextTurn: () => {},
  prevTurn: () => {},
  startAutoPlay: () => { if (!get().isRunning) get().startDirector() },
  stopAutoPlay: () => { get().stopDirector() },

  // ─── Internal actions ───
  _addCommsLog: (msg) => set((s) => ({
    commsLog: [...s.commsLog.slice(-99), msg],
  })),

  _setPhase: (phase) => set({ phase }),

  _setActiveCeo: (ceo) => set((s) => ({
    state: { ...s.state, current_active_ceo: ceo },
  })),

  _addConnectionLine: (line) => set((s) => ({
    connectionLines: [...s.connectionLines, line],
  })),

  _removeConnectionLine: (id) => set((s) => ({
    connectionLines: s.connectionLines.filter((l) => l.id !== id),
  })),

  _addPopupMessage: (msg) => set((s) => ({
    popupMessages: [...s.popupMessages, msg],
  })),

  _removePopupMessage: (id) => set((s) => ({
    popupMessages: s.popupMessages.filter((m) => m.id !== id),
  })),

  _addReactingCeo: (ceo) => set((s) => {
    const next = new Set(s.reactingCeos)
    next.add(ceo)
    return { reactingCeos: next }
  }),

  _removeReactingCeo: (ceo) => set((s) => {
    const next = new Set(s.reactingCeos)
    next.delete(ceo)
    return { reactingCeos: next }
  }),

  _applyStatChanges: (changes) => {
    if (!changes) return
    set((s) => {
      const companies = s.state.companies.map((c) => {
        const delta = changes[c.id]
        if (!delta) return c
        const updated = { ...c }
        if (delta.stock_price !== undefined) {
          updated.stock_price = delta.stock_price
          updated.stock_history = [...c.stock_history, delta.stock_price]
        }
        if (delta.cash !== undefined) updated.cash = delta.cash
        if (delta.reputation !== undefined) updated.reputation = delta.reputation
        if (delta.market_share !== undefined) updated.market_share = delta.market_share
        if (delta.alive !== undefined) updated.alive = delta.alive
        return updated
      })
      return { state: { ...s.state, companies } }
    })
  },

  _addGameEvent: (event) => set((s) => ({
    state: { ...s.state, events: [...s.state.events, event] },
    newEvents: [...s.newEvents, event],
  })),

  _addEmail: (from, to, text, turn) => set((s) => ({
    state: {
      ...s.state,
      recent_emails: [{ turn, from, to, text }, ...s.state.recent_emails].slice(0, 10),
    },
  })),

  _addPartnership: (a, b, turn) => set((s) => ({
    state: {
      ...s.state,
      active_partnerships: [
        ...s.state.active_partnerships,
        { ceo_a: a, ceo_b: b, started_turn: turn, expires_turn: turn + 3, active: true },
      ],
    },
  })),

  _setTurn: (turn) => set((s) => ({
    state: { ...s.state, turn },
    demoTurn: turn,
  })),
}))

// ─── Map DemoEvent types to GameEvent EventType ───
function demoTypeToEventType(type: DemoEvent['type']): GameEvent['type'] {
  const map: Record<string, GameEvent['type']> = {
    PRIVATE_MESSAGE: 'ALLIANCE',
    ALLIANCE: 'ALLIANCE',
    EARNINGS_CALL: 'EARNINGS_CALL',
    SABOTAGE: 'SABOTAGE',
    BETRAYAL: 'BETRAYAL',
    HIRE_SPY: 'HIRE_SPY',
    FAKE_NEWS: 'FAKE_NEWS',
    FAKE_NEWS_EXPOSED: 'FAKE_NEWS_EXPOSED',
    BANKRUPTCY: 'BANKRUPTCY',
    PARTNERSHIP: 'PARTNERSHIP_FORMED',
    HOSTILE_TAKEOVER: 'HOSTILE_TAKEOVER',
    GAME_END: 'MERGER',
  }
  return map[type] ?? 'ALLIANCE'
}

// ─── fireEvent — processes one DemoEvent with deliberate timed steps ───
async function fireEvent(
  event: DemoEvent,
  turn: number,
  epoch: number,
  get: () => GameStore,
) {
  const perpetrator = event.perpetrator
  const victim = event.victim
  const perpName = perpetrator ? COMPANY_MAP[perpetrator]?.shortName ?? perpetrator : ''
  const victName = victim ? COMPANY_MAP[victim]?.shortName ?? victim : ''
  const perpColor = perpetrator ? COMPANY_MAP[perpetrator]?.color ?? '#FFD700' : '#FFD700'

  // T+0: Spotlight the perpetrator
  if (perpetrator) {
    get()._setActiveCeo(perpetrator)
  }
  get()._addCommsLog(`[T${turn}] ${event.type.replace(/_/g, ' ')} — ${perpName}${victName ? ' > ' + victName : ''}`)

  await sleep(600, epoch)

  // T+600: Draw connection line between perpetrator and victim
  const lineId = `line-${turn}-${perpetrator}-${victim}-${event.type}`
  if (perpetrator && victim) {
    const lineStyle = event.type === 'SABOTAGE' || event.type === 'HOSTILE_TAKEOVER' || event.type === 'BETRAYAL'
      ? 'broken' as const
      : event.type === 'PRIVATE_MESSAGE' || event.type === 'HIRE_SPY'
        ? 'dash' as const
        : 'solid' as const
    get()._addConnectionLine({
      id: lineId,
      from: perpetrator,
      to: victim,
      style: lineStyle,
      color: perpColor,
    })
  }

  await sleep(600, epoch)

  // T+1200: Show popup for private messages, add email
  const popupId = `popup-${turn}-${perpetrator}-${victim}-${event.type}`
  if (event.type === 'PRIVATE_MESSAGE' && perpetrator && victim && event.message_text) {
    get()._addPopupMessage({
      id: popupId,
      from: perpetrator,
      to: victim,
      text: event.message_text,
      color: perpColor,
    })
    get()._addEmail(perpetrator, victim, event.message_text, turn)
  }

  // Add email for non-PM events too
  if (event.type !== 'PRIVATE_MESSAGE' && perpetrator && victim && event.message_text) {
    get()._addEmail(perpetrator, victim, event.message_text, turn)
  }

  await sleep(800, epoch)

  // T+2000: Apply stat changes + shake affected CEOs
  if (event.stat_changes) {
    get()._applyStatChanges(event.stat_changes)
    for (const ceoId of Object.keys(event.stat_changes) as CEOId[]) {
      get()._addReactingCeo(ceoId)
    }
  }

  await sleep(600, epoch)

  // T+2600: Log the event
  const gameEvent: GameEvent = {
    turn,
    type: demoTypeToEventType(event.type),
    perpetrator: perpetrator ?? undefined,
    victim: victim ?? undefined,
    message: event.message_text ?? `${event.type} event`,
  }
  get()._addGameEvent(gameEvent)

  // Add partnership record
  if ((event.type === 'PARTNERSHIP' || event.type === 'ALLIANCE') && perpetrator && victim) {
    get()._addPartnership(perpetrator, victim, turn)
  }

  await sleep(800, epoch)

  // T+3400: Clean up — remove line, popup, stop shaking
  get()._removeConnectionLine(lineId)
  get()._removePopupMessage(popupId)
  if (event.stat_changes) {
    for (const ceoId of Object.keys(event.stat_changes) as CEOId[]) {
      get()._removeReactingCeo(ceoId)
    }
  }

  // T+3400: If it's a banner event, hold longer so the banner can display
  if (BANNER_EVENT_TYPES.includes(event.type)) {
    await sleep(4000, epoch)
    get().clearNewEvents()
  }

  await sleep(400, epoch)
}

// ─── playTurn — processes all events in a turn sequentially ───
async function playTurn(
  turnData: typeof DEMO_SCRIPT[0],
  epoch: number,
  get: () => GameStore,
) {
  get()._setTurn(turnData.number)
  get()._setPhase('NEGOTIATION')
  get()._addCommsLog(`--- TURN ${turnData.number} ---`)

  await sleep(1000, epoch)

  for (let i = 0; i < turnData.events.length; i++) {
    const event = turnData.events[i]

    // Set phase based on event type
    if (event.type === 'PRIVATE_MESSAGE' || event.type === 'ALLIANCE' || event.type === 'PARTNERSHIP') {
      get()._setPhase('NEGOTIATION')
    } else if (event.type === 'EARNINGS_CALL' || event.type === 'GAME_END') {
      get()._setPhase('RESOLUTION')
    } else {
      get()._setPhase('ACTION')
    }

    await fireEvent(event, turnData.number, epoch, get)

    // Breathing room between events within a turn
    await sleep(800, epoch)
  }

  // Turn end
  get()._setPhase('TURN_END')
  get()._setActiveCeo(null)
  get()._addCommsLog(`[T${turnData.number}] Turn complete.`)

  // Expire old partnerships
  const state = get().state
  const partnerships = state.active_partnerships.map(p =>
    p.expires_turn <= turnData.number ? { ...p, active: false } : p
  )
  useGameStore.setState((s) => ({
    state: { ...s.state, active_partnerships: partnerships },
  }))

  await sleep(2000, epoch)
}

// ─── runDemoLoop — infinite cycling through the 12-turn script ───
async function runDemoLoop(
  epoch: number,
  get: () => GameStore,
) {
  while (directorActive && directorEpoch === epoch) {
    // Reset for each cycle
    useGameStore.setState({
      state: makeInitialGameState(),
      demoTurn: 0,
      phase: 'IDLE',
      connectionLines: [],
      popupMessages: [],
      newEvents: [],
    })

    get()._addCommsLog('[SYSTEM] === NEW GAME ===')

    try {
      await sleep(3000, epoch)

      for (const turnData of DEMO_SCRIPT) {
        if (!directorActive || directorEpoch !== epoch) return
        await playTurn(turnData, epoch, get)
      }

      // Game over
      get()._setPhase('IDLE')
      get()._setActiveCeo(null)
      get()._addCommsLog('[SYSTEM] Game complete. Restarting in 10s...')
      useGameStore.setState((s) => ({
        state: { ...s.state, status: 'finished' },
      }))

      await sleep(10000, epoch)
    } catch (e: unknown) {
      if (e instanceof Error && e.message === 'epoch_changed') return
      throw e
    }
  }
}

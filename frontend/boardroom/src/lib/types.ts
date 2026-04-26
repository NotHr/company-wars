export type CEOId =
  | 'vermillion' | 'goldspire' | 'sablemark' | 'ironhold'
  | 'ashen' | 'cobalt' | 'verdant'

export type ActionType =
  | 'EARNINGS_CALL' | 'SABOTAGE' | 'PROPOSE_MERGER'
  | 'PARTNERSHIP' | 'HIRE_SPY' | 'HOSTILE_TAKEOVER'

export type EventType =
  | 'BETRAYAL' | 'BANKRUPTCY' | 'MERGER'
  | 'FAKE_NEWS_EXPOSED' | 'HOSTILE_TAKEOVER' | 'SABOTAGE_FAILED'
  | 'SABOTAGE' | 'ALLIANCE' | 'PARTNERSHIP_FORMED'
  | 'EARNINGS_CALL' | 'HIRE_SPY' | 'FAKE_NEWS'

export interface Company {
  id: CEOId
  name: string
  sector: string
  cash: number
  market_share: number
  stock_price: number
  reputation: number
  alive: boolean
  stock_history: number[]
}

export interface Email {
  turn: number
  from: CEOId
  to: CEOId
  text: string
}

export interface PressRelease {
  turn: number
  from: CEOId
  headline: string
  exposed_as_fake: boolean
}

export interface Partnership {
  ceo_a: CEOId
  ceo_b: CEOId
  started_turn: number
  expires_turn: number
  active: boolean
}

export interface Action {
  turn: number
  ceo: CEOId
  type: ActionType
  target?: CEOId
  succeeded: boolean
}

export interface GameEvent {
  turn: number
  type: EventType
  perpetrator?: CEOId
  victim?: CEOId
  message: string
}

export interface GameState {
  turn: number
  max_turns: number
  status: 'in_progress' | 'finished'
  current_active_ceo: CEOId | null
  companies: Company[]
  recent_emails: Email[]
  press_wire: PressRelease[]
  active_partnerships: Partnership[]
  recent_actions: Action[]
  events: GameEvent[]
}

// Director types
export type DirectorMode = 'live' | 'replay' | 'demo'
export type DirectorPhase = 'IDLE' | 'NEGOTIATION' | 'ACTION' | 'RESOLUTION' | 'TURN_END'

export type DemoEventType =
  | 'PRIVATE_MESSAGE' | 'ALLIANCE' | 'EARNINGS_CALL' | 'SABOTAGE'
  | 'BETRAYAL' | 'HIRE_SPY' | 'FAKE_NEWS' | 'FAKE_NEWS_EXPOSED'
  | 'BANKRUPTCY' | 'PARTNERSHIP' | 'HOSTILE_TAKEOVER' | 'GAME_END'

export interface DemoEvent {
  type: DemoEventType
  perpetrator?: CEOId
  victim?: CEOId
  message_text?: string
  winner?: CEOId
  stat_changes?: Partial<Record<CEOId, Partial<{
    stock_price: number
    cash: number
    reputation: number
    market_share: number
    alive: boolean
  }>>>
}

export interface TurnData {
  number: number
  events: DemoEvent[]
}

export interface ConnectionLine {
  id: string
  from: CEOId
  to: CEOId
  style: 'solid' | 'dash' | 'broken'
  color: string
}

export interface PopupMessage {
  id: string
  from: CEOId
  to: CEOId
  text: string
  color: string
}

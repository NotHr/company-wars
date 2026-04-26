import type { GameState, CEOId, Email, PressRelease, Action, GameEvent, Partnership, ActionType } from './types'

// Seed-based random for reproducibility
function seededRandom(seed: number) {
  let s = seed
  return () => {
    s = (s * 16807 + 0) % 2147483647
    return (s - 1) / 2147483646
  }
}

const CEO_IDS: CEOId[] = ['vermillion', 'goldspire', 'sablemark', 'ironhold', 'ashen', 'cobalt', 'verdant']
const ACTIONS: ActionType[] = ['EARNINGS_CALL', 'SABOTAGE', 'PROPOSE_MERGER', 'PARTNERSHIP', 'HIRE_SPY', 'HOSTILE_TAKEOVER']

const COMPANY_NAMES: Record<CEOId, string> = {
  vermillion: 'CRIMSON & CO',
  goldspire: 'HELIOS LABS',
  sablemark: 'OBSIDIAN MEDIA',
  ironhold: 'ATLAS FREIGHT',
  ashen: 'DRACO PETROLEUM',
  cobalt: 'AZURE WIRELESS',
  verdant: 'SERAPHIM BIOTECH',
}

const SHORT_NAMES: Record<CEOId, string> = {
  vermillion: 'CRIMSON',
  goldspire: 'HELIOS',
  sablemark: 'OBSIDIAN',
  ironhold: 'ATLAS',
  ashen: 'DRACO',
  cobalt: 'AZURE',
  verdant: 'SERAPHIM',
}

const ACTIVE_CEO_ORDER: CEOId[] = ['vermillion', 'goldspire', 'sablemark', 'ironhold', 'ashen', 'cobalt', 'verdant']

const EMAIL_TEMPLATES = [
  "Your position is weakening. Consider our proposal before it's too late.",
  "We know what you did last turn. Cooperate or we go public.",
  "Alliance? My terms: 60/40 split, I get the larger share.",
  "Your stock is tanking. Merge with us or face hostile takeover.",
  "I have intelligence on {target}. Meet me at the usual place.",
  "Don't trust {target}. They've been playing both sides.",
  "Our partnership has been profitable. Let's extend it.",
  "Your shipping lanes are vulnerable. Align with us or watch them burn.",
  "After what they did to us, we need allies. Joint R&D partnership?",
  "I'm proposing a non-aggression pact. Two turns. What say you?",
]

const PRESS_TEMPLATES = [
  "{company} posts record quarterly earnings, stock surges",
  "BREAKING: {company} under investigation for market manipulation",
  "Sources confirm {company} planning major acquisition",
  "{company} announces breakthrough technology partnership",
  "EXCLUSIVE: Internal revolt at {company} — board members resign",
  "{company} secures exclusive government contract worth billions",
  "Whistleblower reveals {company} cooking the books",
  "{company} CEO spotted at secret meeting with {target} executives",
]

export function generateMockState(turn: number): GameState {
  const rand = seededRandom(turn * 42 + 7)
  const maxTurns = 12

  // Generate stock histories up to this turn — each CEO has a unique trajectory
  // Predetermined personality: some trend up, some volatile, some crash
  const STOCK_PROFILES: Record<string, { bias: number; volatility: number; crash?: number }> = {
    vermillion: { bias: 0.6, volatility: 18 },      // aggressive growth
    goldspire:  { bias: 0.3, volatility: 12 },       // steady climber
    sablemark:  { bias: -0.1, volatility: 22 },      // volatile media
    ironhold:   { bias: 0.15, volatility: 8 },        // boring stable
    ashen:      { bias: 0.4, volatility: 16 },        // oil boom
    cobalt:     { bias: 0.2, volatility: 14 },        // moderate
    verdant:    { bias: -0.3, volatility: 25, crash: 8 }, // crash before bankruptcy
  }

  const companies = CEO_IDS.map((id, idx) => {
    const basePrice = 100
    const history: number[] = [basePrice]
    let alive = true
    const profile = STOCK_PROFILES[id]

    for (let t = 1; t <= turn; t++) {
      const r = seededRandom(t * 997 + idx * 131 + 43)
      // Use multiple calls for more variation
      const v1 = r()
      const v2 = r()
      const v3 = r()
      const lastPrice = history[history.length - 1]

      let bias = profile.bias
      // Crash trajectory for verdant approaching bankruptcy
      if (profile.crash && t >= profile.crash) {
        bias = -3
      }
      // Event-driven shocks
      if (id === 'vermillion' && t === 5) bias += 1.5  // betrayal pays off
      if (id === 'goldspire' && t === 5) bias -= 2     // betrayal victim
      if (id === 'ashen' && t === 11) bias -= 3        // hostile takeover target

      const noise = ((v1 + v2 + v3) / 3 - 0.5) * profile.volatility
      const change = bias + noise
      const newPrice = Math.max(5, lastPrice + change)
      history.push(Math.round(newPrice * 100) / 100)
    }

    const currentPrice = history[history.length - 1]
    const cash = Math.max(0, 50_000_000 + (rand() - 0.5) * 40_000_000)
    const marketShare = 14.3 + (rand() - 0.5) * 8

    // Kill verdant at turn 9+
    if (id === 'verdant' && turn >= 9) alive = false

    return {
      id,
      name: COMPANY_NAMES[id],
      sector: ['Finance', 'Tech', 'Media', 'Shipping', 'Oil', 'Telecom', 'Biotech'][idx],
      cash: alive ? Math.round(cash) : 0,
      market_share: alive ? Math.round(marketShare * 10) / 10 : 0,
      stock_price: alive ? currentPrice : 0,
      reputation: alive ? Math.round((0.3 + rand() * 0.6) * 100) / 100 : 0,
      alive,
      stock_history: history,
    }
  })

  // Active CEO rotates
  const activeCeo = ACTIVE_CEO_ORDER[turn % 7]

  // Generate emails for this turn
  const emails: Email[] = []
  for (let i = 0; i < 3 + Math.floor(rand() * 3); i++) {
    const fromIdx = Math.floor(rand() * 7)
    let toIdx = Math.floor(rand() * 7)
    if (toIdx === fromIdx) toIdx = (toIdx + 1) % 7
    const template = EMAIL_TEMPLATES[Math.floor(rand() * EMAIL_TEMPLATES.length)]
    const targetIdx = Math.floor(rand() * 7)
    emails.push({
      turn,
      from: CEO_IDS[fromIdx],
      to: CEO_IDS[toIdx],
      text: template.replace('{target}', SHORT_NAMES[CEO_IDS[targetIdx]]),
    })
  }

  // Press releases — accumulate across turns
  const pressWire: PressRelease[] = []
  for (let t = 1; t <= turn; t++) {
    const pr = seededRandom(t * 37)
    const count = 1 + Math.floor(pr() * 2)
    for (let j = 0; j < count; j++) {
      const fromIdx = Math.floor(pr() * 7)
      const targetIdx = Math.floor(pr() * 7)
      const template = PRESS_TEMPLATES[Math.floor(pr() * PRESS_TEMPLATES.length)]
      pressWire.push({
        turn: t,
        from: CEO_IDS[fromIdx],
        headline: template
          .replace('{company}', COMPANY_NAMES[CEO_IDS[fromIdx]])
          .replace('{target}', SHORT_NAMES[CEO_IDS[targetIdx]]),
        exposed_as_fake: pr() < 0.2,
      })
    }
  }

  // Partnerships
  const partnerships: Partnership[] = []
  if (turn >= 2) {
    partnerships.push({ ceo_a: 'cobalt', ceo_b: 'ironhold', started_turn: 2, expires_turn: 6, active: turn < 6 })
  }
  if (turn >= 4) {
    partnerships.push({ ceo_a: 'sablemark', ceo_b: 'goldspire', started_turn: 4, expires_turn: 8, active: turn < 8 })
  }
  if (turn >= 7) {
    partnerships.push({ ceo_a: 'vermillion', ceo_b: 'ashen', started_turn: 7, expires_turn: 11, active: turn < 11 })
  }

  // Actions for this turn
  const actions: Action[] = CEO_IDS.filter((_, i) => companies[i].alive).map(id => {
    const r2 = seededRandom(turn * 50 + CEO_IDS.indexOf(id))
    const actionType = ACTIONS[Math.floor(r2() * ACTIONS.length)]
    const targetIdx = Math.floor(r2() * 7)
    const target = CEO_IDS[targetIdx] !== id ? CEO_IDS[targetIdx] : undefined
    return {
      turn,
      ceo: id,
      type: actionType,
      target,
      succeeded: r2() > 0.3,
    }
  })

  // Events — dramatic moments
  const events: GameEvent[] = []
  if (turn >= 3) {
    events.push({ turn: 3, type: 'FAKE_NEWS_EXPOSED', perpetrator: 'vermillion', victim: 'verdant', message: 'CRIMSON & CO exposed for spreading false FDA trial results' })
  }
  if (turn >= 5) {
    events.push({ turn: 5, type: 'BETRAYAL', perpetrator: 'vermillion', victim: 'goldspire', message: 'CRIMSON & CO has betrayed HELIOS LABS' })
  }
  if (turn >= 7) {
    events.push({ turn: 7, type: 'SABOTAGE_FAILED', perpetrator: 'ashen', victim: 'cobalt', message: "DRACO's sabotage attempt against AZURE backfires" })
  }
  if (turn >= 9) {
    events.push({ turn: 9, type: 'BANKRUPTCY', perpetrator: 'verdant', message: 'SERAPHIM BIOTECH has gone bankrupt' })
  }
  if (turn >= 11) {
    events.push({ turn: 11, type: 'HOSTILE_TAKEOVER', perpetrator: 'vermillion', victim: 'ashen', message: 'CRIMSON & CO executes hostile takeover of DRACO PETROLEUM' })
  }

  return {
    turn,
    max_turns: maxTurns,
    status: turn >= maxTurns ? 'finished' : 'in_progress',
    current_active_ceo: activeCeo,
    companies,
    recent_emails: emails,
    press_wire: pressWire,
    active_partnerships: partnerships.filter(p => p.active),
    recent_actions: actions,
    events: events.filter(e => e.turn <= turn),
  }
}

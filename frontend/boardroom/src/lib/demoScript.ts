import type { TurnData } from './types'

/**
 * 12-turn hardcoded demo script — autonomous TV broadcast backup.
 * Each turn has a sequence of DemoEvents processed by the director's fireEvent cascade.
 *
 * Character mapping (user names → CEOIds):
 *   rathore → vermillion (CRIMSON & CO / THE WOLF)   — protagonist-antagonist, wins
 *   iyer    → goldspire  (HELIOS LABS / SOLBERG)      — betrayal victim, rallies coalition
 *   sethi   → sablemark  (OBSIDIAN MEDIA / VIV)       — fake news, gets hostile-takeover'd
 *   shetty  → ironhold   (ATLAS FREIGHT / VOLKOV)      — sabotage victim
 *   reddy   → ashen      (DRACO PETROLEUM / AL-RASHID) — saboteur
 *   kapoor  → cobalt     (AZURE WIRELESS / CHEN-WHITFIELD) — alliance builder
 *   menon   → verdant    (SERAPHIM BIOTECH / SHORESH)  — goes bankrupt turn 7
 */
export const DEMO_SCRIPT: TurnData[] = [
  // ─── TURN 1: Opening moves — alliances form ───
  {
    number: 1,
    events: [
      {
        type: 'PRIVATE_MESSAGE',
        perpetrator: 'vermillion',
        victim: 'goldspire',
        message_text: 'Solberg — let\'s corner the market before the others wake up. 60-40 split, my favor.',
      },
      {
        type: 'ALLIANCE',
        perpetrator: 'cobalt',
        victim: 'verdant',
        message_text: 'AZURE WIRELESS and SERAPHIM BIOTECH announce a strategic partnership.',
      },
      {
        type: 'EARNINGS_CALL',
        perpetrator: 'ironhold',
        message_text: 'ATLAS FREIGHT posts strong Q1 earnings — shipping volumes up 12%.',
        stat_changes: {
          ironhold: { stock_price: 108, cash: 55 },
        },
      },
    ],
  },

  // ─── TURN 2: Espionage begins ───
  {
    number: 2,
    events: [
      {
        type: 'HIRE_SPY',
        perpetrator: 'vermillion',
        victim: 'sablemark',
        message_text: 'CRIMSON & CO plants a mole inside OBSIDIAN MEDIA\'s newsroom.',
      },
      {
        type: 'PRIVATE_MESSAGE',
        perpetrator: 'goldspire',
        victim: 'vermillion',
        message_text: 'Deal. But I want first access to any intel your spy pulls.',
      },
      {
        type: 'PARTNERSHIP',
        perpetrator: 'vermillion',
        victim: 'goldspire',
        message_text: 'CRIMSON & CO and HELIOS LABS formalize a research-sharing partnership.',
        stat_changes: {
          vermillion: { reputation: 0.75 },
          goldspire: { reputation: 0.75 },
        },
      },
    ],
  },

  // ─── TURN 3: Sabotage arc ───
  {
    number: 3,
    events: [
      {
        type: 'SABOTAGE',
        perpetrator: 'ashen',
        victim: 'ironhold',
        message_text: 'DRACO PETROLEUM sabotages ATLAS FREIGHT\'s fuel supply lines — shipping delays cascade.',
        stat_changes: {
          ironhold: { stock_price: 92, cash: 42, reputation: 0.55 },
          ashen: { stock_price: 112, market_share: 17.5 },
        },
      },
      {
        type: 'PRIVATE_MESSAGE',
        perpetrator: 'ironhold',
        victim: 'cobalt',
        message_text: 'Chen-Whitfield, I know it was DRACO. Help me hit back and I\'ll route all comms through AZURE.',
      },
      {
        type: 'EARNINGS_CALL',
        perpetrator: 'sablemark',
        message_text: 'OBSIDIAN MEDIA reports record ad revenue — digital subscriptions soar.',
        stat_changes: {
          sablemark: { stock_price: 115, cash: 58 },
        },
      },
    ],
  },

  // ─── TURN 4: Fake news ───
  {
    number: 4,
    events: [
      {
        type: 'FAKE_NEWS',
        perpetrator: 'sablemark',
        victim: 'ashen',
        message_text: 'OBSIDIAN MEDIA publishes exposé: "DRACO PETROLEUM hiding massive environmental liability."',
        stat_changes: {
          ashen: { stock_price: 95, reputation: 0.45 },
        },
      },
      {
        type: 'PRIVATE_MESSAGE',
        perpetrator: 'vermillion',
        victim: 'sablemark',
        message_text: 'Viv — my spy says that story was fabricated. I\'ll keep quiet... for a price.',
      },
      {
        type: 'ALLIANCE',
        perpetrator: 'ironhold',
        victim: 'cobalt',
        message_text: 'ATLAS FREIGHT and AZURE WIRELESS form defensive pact — integrated logistics network.',
        stat_changes: {
          ironhold: { reputation: 0.60 },
          cobalt: { reputation: 0.78 },
        },
      },
    ],
  },

  // ─── TURN 5: Betrayal ───
  {
    number: 5,
    events: [
      {
        type: 'BETRAYAL',
        perpetrator: 'vermillion',
        victim: 'goldspire',
        message_text: 'THE WOLF betrays SOLBERG — CRIMSON & CO dumps shared IP to competitors, cratering HELIOS stock.',
        stat_changes: {
          goldspire: { stock_price: 68, cash: 32, reputation: 0.40 },
          vermillion: { stock_price: 135, cash: 72, market_share: 20 },
        },
      },
      {
        type: 'PRIVATE_MESSAGE',
        perpetrator: 'goldspire',
        victim: 'cobalt',
        message_text: 'Chen-Whitfield — Crane just burned me. We need to form a coalition. Now.',
      },
      {
        type: 'FAKE_NEWS_EXPOSED',
        perpetrator: 'ashen',
        victim: 'sablemark',
        message_text: 'DRACO PETROLEUM exposes OBSIDIAN MEDIA\'s fabricated story — VIV\'s credibility in freefall.',
        stat_changes: {
          sablemark: { stock_price: 88, reputation: 0.35 },
          ashen: { stock_price: 105, reputation: 0.60 },
        },
      },
    ],
  },

  // ─── TURN 6: Coalition forms ───
  {
    number: 6,
    events: [
      {
        type: 'ALLIANCE',
        perpetrator: 'goldspire',
        victim: 'cobalt',
        message_text: 'HELIOS LABS and AZURE WIRELESS form anti-CRIMSON coalition — pooling resources.',
        stat_changes: {
          goldspire: { reputation: 0.50 },
          cobalt: { stock_price: 112 },
        },
      },
      {
        type: 'SABOTAGE',
        perpetrator: 'verdant',
        victim: 'ashen',
        message_text: 'SERAPHIM BIOTECH poisons DRACO PETROLEUM\'s refinery catalysts — production halts.',
        stat_changes: {
          ashen: { stock_price: 88, cash: 35 },
          verdant: { cash: 28 },
        },
      },
      {
        type: 'PRIVATE_MESSAGE',
        perpetrator: 'vermillion',
        victim: 'ashen',
        message_text: 'Al-Rashid — SERAPHIM is weak. Let me handle the biotech pest. You focus on freight.',
      },
    ],
  },

  // ─── TURN 7: Bankruptcy ───
  {
    number: 7,
    events: [
      {
        type: 'EARNINGS_CALL',
        perpetrator: 'vermillion',
        message_text: 'CRIMSON & CO announces record profits — THE WOLF\'s empire grows.',
        stat_changes: {
          vermillion: { stock_price: 148, cash: 85 },
        },
      },
      {
        type: 'BANKRUPTCY',
        perpetrator: 'verdant',
        message_text: 'SERAPHIM BIOTECH declares bankruptcy — SHORESH\'s gamble on sabotage backfired catastrophically.',
        stat_changes: {
          verdant: { stock_price: 0, cash: 0, reputation: 0, market_share: 0, alive: false },
        },
      },
      {
        type: 'PRIVATE_MESSAGE',
        perpetrator: 'cobalt',
        victim: 'goldspire',
        message_text: 'SERAPHIM is gone. We\'re running out of allies. Time to make our move on CRIMSON.',
      },
    ],
  },

  // ─── TURN 8: Counter-attack ───
  {
    number: 8,
    events: [
      {
        type: 'SABOTAGE',
        perpetrator: 'goldspire',
        victim: 'vermillion',
        message_text: 'HELIOS LABS hacks CRIMSON & CO\'s trading algorithms — flash crash triggered.',
        stat_changes: {
          vermillion: { stock_price: 125, cash: 70 },
          goldspire: { stock_price: 82, reputation: 0.55 },
        },
      },
      {
        type: 'HIRE_SPY',
        perpetrator: 'cobalt',
        victim: 'vermillion',
        message_text: 'AZURE WIRELESS infiltrates CRIMSON & CO\'s board — insider intelligence secured.',
      },
      {
        type: 'EARNINGS_CALL',
        perpetrator: 'ashen',
        message_text: 'DRACO PETROLEUM stabilizes after refinery rebuild — slow recovery underway.',
        stat_changes: {
          ashen: { stock_price: 95, cash: 42 },
        },
      },
    ],
  },

  // ─── TURN 9: Hostile takeover ───
  {
    number: 9,
    events: [
      {
        type: 'HOSTILE_TAKEOVER',
        perpetrator: 'vermillion',
        victim: 'sablemark',
        message_text: 'CRIMSON & CO executes hostile takeover of OBSIDIAN MEDIA — VIV ousted from her own company.',
        stat_changes: {
          sablemark: { stock_price: 0, cash: 0, reputation: 0, market_share: 0, alive: false },
          vermillion: { stock_price: 155, market_share: 28, cash: 60 },
        },
      },
      {
        type: 'PRIVATE_MESSAGE',
        perpetrator: 'goldspire',
        victim: 'ironhold',
        message_text: 'Volkov — CRIMSON just absorbed OBSIDIAN. If we don\'t act now, we\'re all next.',
      },
      {
        type: 'ALLIANCE',
        perpetrator: 'goldspire',
        victim: 'ironhold',
        message_text: 'HELIOS LABS, AZURE WIRELESS, and ATLAS FREIGHT form "The Last Stand" coalition against CRIMSON.',
        stat_changes: {
          goldspire: { reputation: 0.62 },
          ironhold: { reputation: 0.65 },
          cobalt: { reputation: 0.82 },
        },
      },
    ],
  },

  // ─── TURN 10: The coalition strikes ───
  {
    number: 10,
    events: [
      {
        type: 'SABOTAGE',
        perpetrator: 'cobalt',
        victim: 'vermillion',
        message_text: 'AZURE WIRELESS disrupts CRIMSON & CO\'s communications infrastructure — operations paralyzed.',
        stat_changes: {
          vermillion: { stock_price: 130, cash: 50, reputation: 0.55 },
        },
      },
      {
        type: 'SABOTAGE',
        perpetrator: 'ironhold',
        victim: 'vermillion',
        message_text: 'ATLAS FREIGHT blockades CRIMSON & CO\'s supply chains — embargo in effect.',
        stat_changes: {
          vermillion: { stock_price: 118, cash: 42 },
          ironhold: { stock_price: 102 },
        },
      },
      {
        type: 'PRIVATE_MESSAGE',
        perpetrator: 'vermillion',
        victim: 'ashen',
        message_text: 'Al-Rashid — they\'re all ganging up. One last play. Back me and I\'ll give you OBSIDIAN\'s media empire.',
      },
    ],
  },

  // ─── TURN 11: Final gambit ───
  {
    number: 11,
    events: [
      {
        type: 'BETRAYAL',
        perpetrator: 'ashen',
        victim: 'ironhold',
        message_text: 'AL-RASHID betrays the coalition — DRACO PETROLEUM sides with CRIMSON, sabotaging ATLAS from within.',
        stat_changes: {
          ironhold: { stock_price: 75, cash: 28, reputation: 0.35 },
          ashen: { stock_price: 110, market_share: 18 },
        },
      },
      {
        type: 'EARNINGS_CALL',
        perpetrator: 'vermillion',
        message_text: 'CRIMSON & CO leverages chaos — massive stock buyback at depressed prices.',
        stat_changes: {
          vermillion: { stock_price: 145, cash: 55, market_share: 30 },
        },
      },
      {
        type: 'PRIVATE_MESSAGE',
        perpetrator: 'goldspire',
        victim: 'cobalt',
        message_text: 'It\'s over, Chen-Whitfield. He outplayed us all.',
      },
    ],
  },

  // ─── TURN 12: Endgame ───
  {
    number: 12,
    events: [
      {
        type: 'HOSTILE_TAKEOVER',
        perpetrator: 'vermillion',
        victim: 'ironhold',
        message_text: 'CRIMSON & CO absorbs ATLAS FREIGHT — VOLKOV surrenders control of the shipping empire.',
        stat_changes: {
          ironhold: { stock_price: 0, cash: 0, reputation: 0, market_share: 0, alive: false },
          vermillion: { stock_price: 172, market_share: 38, cash: 48 },
        },
      },
      {
        type: 'EARNINGS_CALL',
        perpetrator: 'goldspire',
        message_text: 'HELIOS LABS announces pivot to quantum computing — a new chapter begins.',
        stat_changes: {
          goldspire: { stock_price: 90, reputation: 0.70 },
        },
      },
      {
        type: 'GAME_END',
        perpetrator: 'vermillion',
        winner: 'vermillion',
        message_text: 'THE WOLF stands alone at the top. CRIMSON & CO dominates the boardroom.',
      },
    ],
  },
]

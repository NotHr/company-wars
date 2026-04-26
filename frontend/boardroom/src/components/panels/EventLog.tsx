'use client'

import { useMemo } from 'react'
import { useGameStore } from '@/store/gameStore'
import { COMPANY_MAP } from '@/lib/constants'
import type { CEOId, EventType, ActionType } from '@/lib/types'
import HUDFrame from '@/components/ui/HUDFrame'

const EVENT_ICONS: Record<EventType, string> = {
  BETRAYAL: '\u2694\uFE0F',
  BANKRUPTCY: '\uD83D\uDC80',
  HOSTILE_TAKEOVER: '\uD83C\uDFF4',
  FAKE_NEWS_EXPOSED: '\uD83D\uDCF0',
  SABOTAGE_FAILED: '\uD83D\uDCA5',
  MERGER: '\uD83E\uDD1D',
  SABOTAGE: '\uD83D\uDCA3',
  ALLIANCE: '\uD83D\uDD17',
  PARTNERSHIP_FORMED: '\uD83E\uDD1D',
  EARNINGS_CALL: '\uD83D\uDCC8',
  HIRE_SPY: '\uD83D\uDD75\uFE0F',
  FAKE_NEWS: '\uD83D\uDCF0',
}

const ACTION_ICONS: Record<ActionType, string> = {
  EARNINGS_CALL: '\uD83D\uDCC8',
  SABOTAGE: '\uD83D\uDCA3',
  PROPOSE_MERGER: '\uD83E\uDD1D',
  PARTNERSHIP: '\uD83D\uDD17',
  HIRE_SPY: '\uD83D\uDD75\uFE0F',
  HOSTILE_TAKEOVER: '\uD83C\uDFF4',
}

function CeoName({ ceoId }: { ceoId: CEOId }) {
  const company = COMPANY_MAP[ceoId]
  if (!company) return <span className="font-mono">{ceoId}</span>
  return (
    <span className="font-display font-bold tracking-wider" style={{ color: company.color }}>
      {company.shortName}
    </span>
  )
}

/** Replaces CEO ids found in a message string with colored spans */
function ColoredMessage({ message }: { message: string }) {
  const ceoIds = Object.keys(COMPANY_MAP) as CEOId[]
  // Build a regex that matches any company name or short name
  const nameMap = Object.fromEntries(
    ceoIds.flatMap((id) => [
      [COMPANY_MAP[id].name, id],
      [COMPANY_MAP[id].shortName, id],
    ])
  )
  const pattern = new RegExp(
    `(${Object.keys(nameMap).map((n) => n.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|')})`,
    'g'
  )

  const parts = message.split(pattern)

  return (
    <span>
      {parts.map((part, i) => {
        const matchedId = nameMap[part]
        if (matchedId) {
          return (
            <span key={i} className="font-display font-bold tracking-wider" style={{ color: COMPANY_MAP[matchedId].color }}>
              {part}
            </span>
          )
        }
        return <span key={i}>{part}</span>
      })}
    </span>
  )
}

export default function EventLog() {
  const events = useGameStore((s) => s.state.events)
  const recentActions = useGameStore((s) => s.state.recent_actions)
  const currentTurn = useGameStore((s) => s.state.turn)

  // Group events by turn, most recent first
  const groupedEvents = useMemo(() => {
    const map = new Map<number, typeof events>()

    for (const ev of events) {
      const arr = map.get(ev.turn) ?? []
      arr.push(ev)
      map.set(ev.turn, arr)
    }

    // Sort descending by turn
    return Array.from(map.entries()).sort((a, b) => b[0] - a[0])
  }, [events])

  return (
    <HUDFrame color="#00E5FF" label="EVENT LOG" className="w-full h-full">
      <div className="flex flex-col h-full bg-black/80 p-4">
        {/* Header */}
        <div className="flex items-center gap-2 mb-3 shrink-0">
          <span className="text-lg">{'\uD83D\uDCDC'}</span>
          <h2 className="font-display text-hud-electric text-lg tracking-widest uppercase">
            Event Log
          </h2>
          <span className="ml-auto font-mono text-xs text-hud-bone/40">
            {events.length} events
          </span>
        </div>

        {/* Scrollable body */}
        <div className="flex-1 overflow-y-auto pr-1 min-h-0 space-y-4">
          {/* Recent actions for current turn */}
          {recentActions.length > 0 && (
            <div className="space-y-1">
              <div className="flex items-center gap-2 mb-1">
                <span
                  className="font-mono text-[10px] leading-none px-1.5 py-0.5 rounded bg-hud-electric/15 text-hud-electric border border-hud-electric/20"
                >
                  T{currentTurn}
                </span>
                <span className="font-mono text-[10px] uppercase tracking-wider text-hud-warning/70">
                  Recent Actions
                </span>
              </div>
              {recentActions.map((action, i) => (
                <div
                  key={`action-${i}`}
                  className="flex items-start gap-2 pl-4 py-1 border-l border-hud-warning/20"
                >
                  <span className="text-sm shrink-0">
                    {ACTION_ICONS[action.type] ?? '\u25B6'}
                  </span>
                  <div className="text-xs text-hud-bone/60 leading-snug">
                    <span className="font-mono text-hud-bone/40">{action.type.replace(/_/g, ' ')}</span>
                    {' \u2014 '}
                    <CeoName ceoId={action.ceo} />
                    {action.target && (
                      <>
                        {' \u2192 '}
                        <CeoName ceoId={action.target} />
                      </>
                    )}
                    {' \u2014 '}
                    <span
                      className={`font-mono font-bold ${
                        action.succeeded ? 'text-hud-success' : 'text-hud-danger'
                      }`}
                    >
                      {action.succeeded ? 'SUCCESS' : 'FAILED'}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Events grouped by turn */}
          {groupedEvents.map(([turn, turnEvents]) => (
            <div key={turn} className="space-y-1">
              <div className="flex items-center gap-2 mb-1">
                <span
                  className="font-mono text-[10px] leading-none px-1.5 py-0.5 rounded bg-hud-bone/10 text-hud-bone/70 border border-hud-bone/10"
                >
                  T{turn}
                </span>
                <div className="flex-1 h-px bg-hud-bone/6" />
              </div>

              {turnEvents.map((ev, i) => (
                <div
                  key={`${turn}-${i}`}
                  className="flex items-start gap-2 pl-4 py-1.5 border-l border-hud-electric/15 hover:border-hud-electric/40 transition-colors"
                >
                  <span className="text-base shrink-0 leading-none mt-0.5">
                    {EVENT_ICONS[ev.type] ?? '\u26A0\uFE0F'}
                  </span>
                  <div className="flex flex-col gap-0.5 min-w-0">
                    <span className="font-mono text-[10px] uppercase tracking-wider text-hud-warning/60">
                      {ev.type.replace(/_/g, ' ')}
                    </span>
                    <span className="text-sm text-hud-bone/80 leading-snug">
                      <ColoredMessage message={ev.message} />
                    </span>
                  </div>
                </div>
              ))}
            </div>
          ))}

          {/* Empty state */}
          {events.length === 0 && recentActions.length === 0 && (
            <div className="flex items-center justify-center h-32 text-hud-bone/20 font-mono text-xs">
              No events yet
            </div>
          )}
        </div>
      </div>
    </HUDFrame>
  )
}

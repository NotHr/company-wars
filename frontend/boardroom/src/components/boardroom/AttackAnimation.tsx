'use client'

import { useEffect, useRef, useState, useCallback } from 'react'
import { motion, AnimatePresence } from 'motion/react'
import { useGameStore } from '@/store/gameStore'
import { COMPANY_MAP } from '@/lib/constants'
import type { GameEvent, EventType, CEOId } from '@/lib/types'

const ATTACK_EVENTS: EventType[] = [
  'BETRAYAL',
  'HOSTILE_TAKEOVER',
  'SABOTAGE_FAILED',
  'FAKE_NEWS_EXPOSED',
]

interface AttackState {
  fromX: number
  fromY: number
  toX: number
  toY: number
  color: string
  type: EventType
  key: string
}

interface ExplosionState {
  x: number
  y: number
  color: string
  key: string
}

interface Props {
  positions: Record<CEOId, { x: number; y: number }>
}

export default function AttackAnimation({ positions }: Props) {
  const newEvents = useGameStore((s) => s.newEvents)
  const turn = useGameStore((s) => s.state.turn)
  const seenKeys = useRef(new Set<string>())
  const lastTurn = useRef(turn)
  const containerRef = useRef<HTMLDivElement>(null)

  // Clear seen keys when turn resets (director loop restart)
  if (turn < lastTurn.current) {
    seenKeys.current.clear()
  }
  lastTurn.current = turn

  const [attack, setAttack] = useState<AttackState | null>(null)
  const [explosion, setExplosion] = useState<ExplosionState | null>(null)
  const [containerSize, setContainerSize] = useState({ w: 1, h: 1 })

  // Measure container on mount and resize
  useEffect(() => {
    const measure = () => {
      if (containerRef.current) {
        const rect = containerRef.current.getBoundingClientRect()
        setContainerSize({ w: rect.width, h: rect.height })
      }
    }
    measure()
    window.addEventListener('resize', measure)
    return () => window.removeEventListener('resize', measure)
  }, [])

  // Convert percentage position to pixel position
  const toPixel = useCallback((pctX: number, pctY: number) => ({
    x: (pctX / 100) * containerSize.w,
    y: (pctY / 100) * containerSize.h,
  }), [containerSize])

  // Handle attack projectile events
  useEffect(() => {
    const e = newEvents.find(
      (ev: GameEvent) =>
        ATTACK_EVENTS.includes(ev.type) && ev.perpetrator && ev.victim
    )
    if (!e?.perpetrator || !e?.victim) return

    const key = `atk-${e.type}-${e.turn}-${e.perpetrator}-${e.victim}`
    if (seenKeys.current.has(key)) return
    seenKeys.current.add(key)

    const fromPos = positions[e.perpetrator]
    const toPos = positions[e.victim]
    if (!fromPos || !toPos) return

    const perpDef = COMPANY_MAP[e.perpetrator]

    setAttack({
      fromX: fromPos.x,
      fromY: fromPos.y,
      toX: toPos.x,
      toY: toPos.y,
      color: perpDef?.color ?? '#FF2E4D',
      type: e.type,
      key,
    })

    const t = setTimeout(() => setAttack(null), 1400)
    return () => clearTimeout(t)
  }, [newEvents, positions])

  // Handle bankruptcy events
  useEffect(() => {
    const e = newEvents.find(
      (ev: GameEvent) => ev.type === 'BANKRUPTCY' && ev.perpetrator
    )
    if (!e?.perpetrator) return

    const key = `exp-${e.turn}-${e.perpetrator}`
    if (seenKeys.current.has(key)) return
    seenKeys.current.add(key)

    const pos = positions[e.perpetrator]
    const def = COMPANY_MAP[e.perpetrator]
    if (!pos) return

    setExplosion({
      x: pos.x,
      y: pos.y,
      color: def?.color ?? '#FF2E4D',
      key,
    })

    const t = setTimeout(() => setExplosion(null), 1500)
    return () => clearTimeout(t)
  }, [newEvents, positions])

  // Use pixel-based viewBox so strokes and circles render uniformly
  const vw = containerSize.w
  const vh = containerSize.h

  // Compute pixel coords for attack
  const atkFrom = attack ? toPixel(attack.fromX, attack.fromY) : null
  const atkTo = attack ? toPixel(attack.toX, attack.toY) : null

  // Compute pixel coords for explosion
  const expPos = explosion ? toPixel(explosion.x, explosion.y) : null

  return (
    <div ref={containerRef} className="absolute inset-0 pointer-events-none z-20">
      <svg
        className="absolute inset-0 w-full h-full"
        viewBox={`0 0 ${vw} ${vh}`}
        preserveAspectRatio="xMidYMid meet"
      >
        <defs>
          {attack && (
            <filter id={`glow-${attack.key}`} x="-50%" y="-50%" width="200%" height="200%">
              <feGaussianBlur stdDeviation="3" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          )}
          {explosion && (
            <filter id={`glow-${explosion.key}`} x="-50%" y="-50%" width="200%" height="200%">
              <feGaussianBlur stdDeviation="4" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          )}
        </defs>

        <AnimatePresence>
          {attack && atkFrom && atkTo && (
            <g key={attack.key}>
              {/* Trail line from perpetrator to victim */}
              <motion.line
                x1={atkFrom.x}
                y1={atkFrom.y}
                x2={atkFrom.x}
                y2={atkFrom.y}
                stroke={attack.color}
                strokeWidth="2"
                strokeOpacity="0.5"
                filter={`url(#glow-${attack.key})`}
                animate={{
                  x2: atkTo.x,
                  y2: atkTo.y,
                }}
                transition={{ duration: 0.8, ease: [0.4, 0, 0.2, 1] }}
              />

              {/* Projectile circle traveling along the line */}
              <motion.circle
                cx={atkFrom.x}
                cy={atkFrom.y}
                r="6"
                fill={attack.color}
                filter={`url(#glow-${attack.key})`}
                animate={{
                  cx: atkTo.x,
                  cy: atkTo.y,
                }}
                transition={{ duration: 0.8, ease: [0.4, 0, 0.2, 1] }}
              />

              {/* Impact glow at target */}
              <motion.circle
                cx={atkTo.x}
                cy={atkTo.y}
                r="4"
                fill={attack.color}
                fillOpacity="0"
                filter={`url(#glow-${attack.key})`}
                initial={{ r: 4, fillOpacity: 0 }}
                animate={{
                  r: [4, 30, 50],
                  fillOpacity: [0, 0.6, 0],
                }}
                transition={{ delay: 0.75, duration: 0.6, ease: 'easeOut' }}
              />

              {/* Impact ring at target */}
              <motion.circle
                cx={atkTo.x}
                cy={atkTo.y}
                r="4"
                fill="none"
                stroke={attack.color}
                strokeWidth="1.5"
                initial={{ r: 4, strokeOpacity: 0 }}
                animate={{
                  r: [4, 40, 60],
                  strokeOpacity: [0, 0.5, 0],
                }}
                transition={{ delay: 0.8, duration: 0.5, ease: 'easeOut' }}
              />
            </g>
          )}
        </AnimatePresence>

        <AnimatePresence>
          {explosion && expPos && (
            <g key={explosion.key}>
              {/* Central flash */}
              <motion.circle
                cx={expPos.x}
                cy={expPos.y}
                r="4"
                fill={explosion.color}
                filter={`url(#glow-${explosion.key})`}
                initial={{ r: 4, fillOpacity: 0 }}
                animate={{
                  r: [4, 40, 15],
                  fillOpacity: [0, 0.8, 0],
                }}
                transition={{ duration: 1.2, ease: 'easeOut' }}
              />

              {/* Expanding shockwave rings */}
              {[0, 0.15, 0.3].map((delay, i) => (
                <motion.circle
                  key={i}
                  cx={expPos.x}
                  cy={expPos.y}
                  r="8"
                  fill="none"
                  stroke={explosion.color}
                  strokeWidth="1.5"
                  initial={{ r: 8, strokeOpacity: 0 }}
                  animate={{
                    r: [8, 60, 80],
                    strokeOpacity: [0, 0.5, 0],
                  }}
                  transition={{ delay, duration: 1, ease: 'easeOut' }}
                />
              ))}

              {/* X mark using two crossing lines */}
              <motion.g
                initial={{ opacity: 0 }}
                animate={{ opacity: [0, 1, 0.6, 0] }}
                transition={{ delay: 0.3, duration: 1 }}
              >
                <motion.line
                  x1={expPos.x - 15}
                  y1={expPos.y - 15}
                  x2={expPos.x + 15}
                  y2={expPos.y + 15}
                  stroke="#FF2E4D"
                  strokeWidth="2.5"
                  strokeLinecap="round"
                />
                <motion.line
                  x1={expPos.x + 15}
                  y1={expPos.y - 15}
                  x2={expPos.x - 15}
                  y2={expPos.y + 15}
                  stroke="#FF2E4D"
                  strokeWidth="2.5"
                  strokeLinecap="round"
                />
              </motion.g>
            </g>
          )}
        </AnimatePresence>
      </svg>
    </div>
  )
}

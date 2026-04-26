'use client'

import { useEffect, useState, useRef, useCallback } from 'react'
import { motion, AnimatePresence } from 'motion/react'
import { COMPANY_MAP } from '@/lib/constants'
import { useGameStore } from '@/store/gameStore'
import type { GameEvent, EventType } from '@/lib/types'

interface ActiveEvent {
  perpetrator: string
  victim: string
  perpColor: string
  victColor: string
  turn: number
  type: EventType
  key: string
}

const TITLES: Partial<Record<EventType, string>> = {
  BETRAYAL: 'BETRAYAL',
  BANKRUPTCY: 'BANKRUPTCY',
  HOSTILE_TAKEOVER: 'HOSTILE TAKEOVER',
}

const BANNER_TYPES: EventType[] = ['BETRAYAL', 'BANKRUPTCY', 'HOSTILE_TAKEOVER']
const SHOW_DELAY = 800
const BANNER_DURATION = 3000

export default function BetrayalBanner() {
  const newEvents = useGameStore((s) => s.newEvents)
  const clearNewEvents = useGameStore((s) => s.clearNewEvents)
  const resumeAutoPlay = useGameStore((s) => s.resumeAutoPlay)
  const turn = useGameStore((s) => s.state.turn)
  const [active, setActive] = useState<ActiveEvent | null>(null)
  const seenKeys = useRef(new Set<string>())
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const showTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const lastTurn = useRef(turn)

  // Clear seen keys when turn resets (director loop restart)
  if (turn < lastTurn.current) {
    seenKeys.current.clear()
  }
  lastTurn.current = turn

  const dismiss = useCallback(() => {
    if (timerRef.current) clearTimeout(timerRef.current)
    if (showTimerRef.current) clearTimeout(showTimerRef.current)
    timerRef.current = null
    showTimerRef.current = null
    setActive(null)
    clearNewEvents()
    resumeAutoPlay()
  }, [clearNewEvents, resumeAutoPlay])

  useEffect(() => {
    const e = newEvents.find((ev: GameEvent) => BANNER_TYPES.includes(ev.type))
    if (!e?.perpetrator) return

    const key = `${e.type}-${e.turn}-${e.perpetrator}-${e.victim ?? ''}`
    if (seenKeys.current.has(key)) {
      clearNewEvents()
      resumeAutoPlay()
      return
    }
    seenKeys.current.add(key)

    const p = COMPANY_MAP[e.perpetrator]
    const v = e.victim ? COMPANY_MAP[e.victim] : null
    const event: ActiveEvent = {
      perpetrator: p?.shortName ?? e.perpetrator,
      victim: v?.shortName ?? '',
      perpColor: p?.color ?? '#FFD700',
      victColor: v?.color ?? '#F5F1E8',
      turn: e.turn,
      type: e.type,
      key,
    }

    if (showTimerRef.current) clearTimeout(showTimerRef.current)
    showTimerRef.current = setTimeout(() => {
      setActive(event)
      if (timerRef.current) clearTimeout(timerRef.current)
      timerRef.current = setTimeout(dismiss, BANNER_DURATION)
    }, SHOW_DELAY)

    return () => {
      if (showTimerRef.current) clearTimeout(showTimerRef.current)
      if (timerRef.current) clearTimeout(timerRef.current)
    }
  }, [newEvents, clearNewEvents, dismiss, resumeAutoPlay])

  const title = active ? TITLES[active.type] : null
  const isDanger = active?.type === 'BETRAYAL' || active?.type === 'BANKRUPTCY'
  const accentColor = isDanger ? '#FF2E4D' : '#FFD700'

  return (
    <AnimatePresence>
      {active && title && (
        <motion.div
          className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 z-30 cursor-pointer"
          onClick={dismiss}
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0, scale: 0.95 }}
          transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
        >
          {/* Compact card */}
          <div
            className="relative px-10 py-5 text-center"
            style={{
              background: isDanger
                ? 'linear-gradient(135deg, rgba(255,46,77,0.2) 0%, rgba(0,0,0,0.95) 50%, rgba(255,46,77,0.15) 100%)'
                : 'linear-gradient(135deg, rgba(255,215,0,0.15) 0%, rgba(0,0,0,0.95) 50%, rgba(255,215,0,0.1) 100%)',
              border: `1px solid ${accentColor}40`,
              boxShadow: `0 0 40px ${accentColor}20, 0 0 80px ${accentColor}10, inset 0 0 30px rgba(0,0,0,0.5)`,
              minWidth: 320,
            }}
          >
            {/* Corner brackets */}
            <div className="absolute top-0 left-0 w-3 h-3 border-t-2 border-l-2" style={{ borderColor: accentColor }} />
            <div className="absolute top-0 right-0 w-3 h-3 border-t-2 border-r-2" style={{ borderColor: accentColor }} />
            <div className="absolute bottom-0 left-0 w-3 h-3 border-b-2 border-l-2" style={{ borderColor: accentColor }} />
            <div className="absolute bottom-0 right-0 w-3 h-3 border-b-2 border-r-2" style={{ borderColor: accentColor }} />

            {/* Top accent line */}
            <motion.div
              className="absolute top-0 left-3 right-3 h-px"
              style={{ backgroundColor: `${accentColor}60` }}
              initial={{ scaleX: 0 }}
              animate={{ scaleX: 1 }}
              transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
            />

            {/* Turn label */}
            <p
              className="font-mono text-[9px] tracking-[0.4em] mb-1"
              style={{ color: `${accentColor}80` }}
            >
              TURN {active.turn}
            </p>

            {/* Title */}
            <h2
              className="font-display leading-none mb-2"
              style={{
                fontSize: 'clamp(24px, 3vw, 40px)',
                color: accentColor,
                letterSpacing: '0.08em',
                textShadow: `0 0 20px ${accentColor}40`,
              }}
            >
              {title}
            </h2>

            {/* Companies involved */}
            <div className="flex items-center justify-center gap-2">
              <span className="font-serif text-sm font-bold italic" style={{ color: active.perpColor }}>
                {active.perpetrator}
              </span>
              {active.victim && (
                <>
                  <span className="font-display text-xs text-hud-bone/30 tracking-[0.15em]">VS</span>
                  <span className="font-serif text-sm font-bold italic" style={{ color: active.victColor }}>
                    {active.victim}
                  </span>
                </>
              )}
            </div>

            {/* Bottom accent line */}
            <motion.div
              className="absolute bottom-0 left-3 right-3 h-px"
              style={{ backgroundColor: `${accentColor}60` }}
              initial={{ scaleX: 0 }}
              animate={{ scaleX: 1 }}
              transition={{ duration: 0.4, delay: 0.1, ease: [0.16, 1, 0.3, 1] }}
            />
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}

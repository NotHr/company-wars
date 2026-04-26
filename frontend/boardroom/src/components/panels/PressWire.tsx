'use client'

import { motion } from 'motion/react'
import { useGameStore } from '@/store/gameStore'
import { COMPANY_MAP } from '@/lib/constants'

export default function PressWire() {
  const pressWire = useGameStore((s) => s.state.press_wire)
  const actions = useGameStore((s) => s.state.recent_actions)
  const reversed = [...pressWire].reverse()

  return (
    <div className="bg-black overflow-hidden">
      {/* PRESS WIRE section */}
      <div className="px-5 pt-4 pb-2">
        <h2 className="font-display text-2xl tracking-[0.15em] text-hud-warning">
          PRESS WIRE
        </h2>
      </div>

      <div className="px-4 space-y-2 pb-4">
        {reversed.slice(0, 5).map((pr, i) => {
          const from = COMPANY_MAP[pr.from]
          const fake = pr.exposed_as_fake
          return (
            <motion.div
              key={`${pr.from}-${pr.turn}-${i}`}
              className="relative p-3 bg-hud-ink border border-white/[0.04] overflow-hidden"
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.4, delay: i * 0.07 }}
            >
              <div className={fake ? 'opacity-25' : ''}>
                <div className="flex items-center gap-2 mb-1.5">
                  <span className="font-mono text-xs font-bold px-1.5 py-0.5" style={{ backgroundColor: `${from.color}15`, color: from.color }}>
                    T{pr.turn}
                  </span>
                  <span className="font-display text-sm tracking-wider" style={{ color: from.color }}>
                    {from.shortName}
                  </span>
                </div>
                <p className="font-sans text-sm text-hud-bone/50 leading-relaxed">
                  {pr.headline}
                </p>
              </div>

              {/* FAKE NEWS stamp */}
              {fake && (
                <motion.div
                  className="absolute top-1/2 left-1/2 pointer-events-none z-10"
                  initial={{ scale: 2, opacity: 0 }}
                  animate={{ scale: 1, opacity: 0.85 }}
                  transition={{ duration: 0.4 }}
                  style={{ transform: 'translate(-50%, -50%) rotate(-12deg)' }}
                >
                  <div className="px-5 py-1.5 border-[3px] border-hud-danger font-display text-2xl tracking-[0.2em] text-hud-danger">
                    FAKE NEWS
                  </div>
                </motion.div>
              )}
            </motion.div>
          )
        })}
      </div>

      {/* ACTIONS LOG section */}
      <div className="px-5 pt-2 pb-2 border-t border-white/[0.04]">
        <h2 className="font-display text-2xl tracking-[0.15em] text-hud-electric">
          ACTIONS
        </h2>
      </div>

      <div className="px-4 space-y-1 pb-4">
        {actions.map((action, i) => {
          const ceo = COMPANY_MAP[action.ceo]
          const target = action.target ? COMPANY_MAP[action.target] : null
          return (
            <motion.div
              key={`${action.ceo}-${action.type}-${i}`}
              className="flex items-center gap-2 py-2 px-3 bg-hud-ink border border-white/[0.02]"
              initial={{ opacity: 0, x: 15 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.05, duration: 0.3 }}
            >
              <span className="font-display text-sm tracking-wider" style={{ color: ceo.color }}>
                {ceo.shortName}
              </span>
              <span className="font-mono text-xs text-hud-bone/40 tracking-wider uppercase">
                {action.type.replace(/_/g, ' ')}
              </span>
              {target && (
                <span className="font-mono text-xs" style={{ color: `${target.color}70` }}>
                  → {target.shortName}
                </span>
              )}
              <span className="ml-auto">
                {action.succeeded
                  ? <span className="font-mono text-xs font-bold text-hud-success">OK</span>
                  : <span className="font-mono text-xs font-bold text-hud-danger">FAIL</span>}
              </span>
            </motion.div>
          )
        })}
      </div>
    </div>
  )
}

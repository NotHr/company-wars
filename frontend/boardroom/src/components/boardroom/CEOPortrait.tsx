'use client'

import { motion } from 'motion/react'
import { COMPANY_MAP } from '@/lib/constants'
import { formatStockPrice } from '@/lib/format'
import type { Company } from '@/lib/types'
import CEOSigil from './CEOSigil'
import { useGameStore } from '@/store/gameStore'

interface CEOPortraitProps {
  company: Company
  isActive: boolean
  position: { x: number; y: number }
}

// Card has py-2 (8px top padding) and the sigil is 70px tall,
// so the SIGIL CENTER sits 8 + 35 = 43px from the card's top edge.
// We translate the card up by exactly this amount so the sigil
// center aligns with the anchor point — which is where lines terminate.
const SIGIL_CENTER_FROM_CARD_TOP = 43

export default function CEOPortrait({ company, isActive, position }: CEOPortraitProps) {
  const def = COMPANY_MAP[company.id]
  const dead = !company.alive
  const activeCeo = useGameStore((s) => s.state.current_active_ceo)
  const reactingCeos = useGameStore((s) => s.reactingCeos)
  const isReacting = reactingCeos.has(company.id)

  const spotlightOpacity = dead ? 0.4 : (activeCeo && !isActive) ? 0.6 : 1

  return (
    <motion.div
      className="absolute"
      style={{
        left: `${position.x}%`,
        top: `${position.y}%`,
        // NOTE: no transform here — this is just a zero-size anchor point.
        // The card below translates itself so its sigil center lands here.
        zIndex: isActive ? 10 : 2,
        opacity: spotlightOpacity,
        transition: 'opacity 0.5s ease',
        animation: isReacting ? 'ceo-shake 0.5s ease-in-out' : undefined,
      }}
      initial={{ opacity: 0, scale: 0.5 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
    >
      {/* Card — translated so SIGIL CENTER lands exactly on the anchor */}
      <div
        className="relative flex flex-col items-center px-3 py-2"
        style={{
          transform: `translate(-50%, -${SIGIL_CENTER_FROM_CARD_TOP}px)`,
          border: isActive && !dead
            ? `2px solid ${def.color}`
            : dead
              ? '1px solid #222'
              : '1px solid transparent',
          borderRadius: 8,
          background: dead ? 'rgba(0,0,0,0.6)' : isActive ? 'rgba(0,0,0,0.7)' : 'transparent',
          boxShadow: isActive && !dead ? `0 0 24px ${def.color}40, 0 0 48px ${def.color}15` : 'none',
          filter: dead ? 'grayscale(1) opacity(0.4)' : 'none',
        }}
      >
        {/* ACTING badge — absolute, floats above the card without affecting layout */}
        {isActive && !dead && (
          <motion.div
            className="absolute font-mono text-[10px] tracking-[0.2em] uppercase px-2 py-0.5 whitespace-nowrap"
            style={{
              color: def.color,
              border: `1px solid ${def.color}40`,
              left: '50%',
              bottom: 'calc(100% + 6px)',
              transform: 'translateX(-50%)',
            }}
            initial={{ opacity: 0, y: 5 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3 }}
          >
            ACTING
          </motion.div>
        )}

        {/* Pulse rings when active */}
        {isActive && !dead && (
          <motion.div
            className="absolute rounded-full pointer-events-none"
            style={{ width: 80, height: 80, top: 3, border: `2px solid ${def.color}` }}
            animate={{ scale: [1, 1.6], opacity: [0.5, 0] }}
            transition={{ duration: 2, repeat: Infinity, ease: 'easeOut' }}
          />
        )}

        {/* Sigil circle */}
        <div
          className="relative w-[70px] h-[70px] rounded-full flex items-center justify-center"
          style={{
            background: dead ? '#111' : `radial-gradient(circle at 35% 35%, ${def.color}30 0%, ${def.color}05 70%, transparent 100%)`,
            boxShadow: isActive ? `0 0 40px ${def.color}50, 0 0 80px ${def.color}20` : dead ? 'none' : `0 0 20px ${def.color}15`,
          }}
        >
          <div className="absolute inset-0 rounded-full" style={{ border: `2px solid ${dead ? '#333' : isActive ? def.color : `${def.color}40`}` }} />
          <CEOSigil ceoId={company.id} size={36} color={dead ? '#333' : def.color} />
          {dead && (
            <div className="absolute inset-0 rounded-full flex items-center justify-center">
              <div className="w-10 h-0.5 bg-hud-danger/60 rotate-45 absolute" />
              <div className="w-10 h-0.5 bg-hud-danger/60 -rotate-45 absolute" />
            </div>
          )}
        </div>

        {/* COMPANY NAME */}
        <p className="font-display text-[14px] tracking-[0.2em] mt-1.5 leading-none text-center" style={{ color: dead ? '#444' : def.color }}>
          {def.shortName}
        </p>

        {/* CEO name */}
        <p className="font-serif text-[11px] italic text-hud-bone/30 mt-0.5 leading-none">
          {def.ceoName}
        </p>

        {/* Stock price */}
        {!dead && (
          <p className="font-mono text-[10px] text-hud-bone/40 mt-1 leading-none">
            {formatStockPrice(company.stock_price)}
          </p>
        )}

        {/* DEFUNCT stamp — anchored at sigil center, not card center */}
        {dead && (
          <div
            className="absolute pointer-events-none"
            style={{
              top: SIGIL_CENTER_FROM_CARD_TOP,
              left: '50%',
              transform: 'translate(-50%, -50%) rotate(-12deg)',
              border: '2px dotted #FF2E4D',
              padding: '2px 8px',
            }}
          >
            <span className="font-display text-sm tracking-[0.15em] text-hud-danger/80">
              DEFUNCT
            </span>
          </div>
        )}
      </div>
    </motion.div>
  )
}
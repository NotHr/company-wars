'use client'

import { useGameStore } from '@/store/gameStore'
import { COMPANY_MAP } from '@/lib/constants'
import CEOPortrait from './CEOPortrait'
import LineOverlay from './LineOverlay'
import AttackAnimation from './AttackAnimation'
import BetrayalBanner from './BetrayalBanner'
import HUDFrame from '@/components/ui/HUDFrame'
import type { CEOId } from '@/lib/types'

// Heptagonal arrangement — 7 points evenly spaced (percentage of container)
const ANGLE_OFFSET = -90
const RADIUS_X = 38
const RADIUS_Y = 36
const CEO_ORDER: CEOId[] = ['vermillion', 'goldspire', 'sablemark', 'ironhold', 'ashen', 'cobalt', 'verdant']

const CEO_POSITIONS: Record<CEOId, { x: number; y: number }> = {} as Record<CEOId, { x: number; y: number }>
CEO_ORDER.forEach((id, i) => {
  const angle = ANGLE_OFFSET + (360 / 7) * i
  const rad = (angle * Math.PI) / 180
  CEO_POSITIONS[id] = {
    x: 50 + RADIUS_X * Math.cos(rad),
    y: 50 + RADIUS_Y * Math.sin(rad),
  }
})

// Sector rune SVG paths
const SECTOR_RUNES: Record<CEOId, string> = {
  vermillion: 'M8 22 L15 6 L18 12 L21 6 L28 22 M12 16 L24 16',
  goldspire:  'M15 4 L15 12 L9 18 L9 26 M15 4 L15 12 L21 18 L21 26 M11 12 L19 12',
  sablemark:  'M15 6 L15 12 M15 24 L15 18 M6 10 L11 14 M24 10 L19 14 M6 20 L11 18 M24 20 L19 18',
  ironhold:   'M15 4 L26 10 L26 20 L15 28 L4 20 L4 10 Z',
  ashen:      'M15 4 C15 4 7 14 7 18 C7 24 11 28 15 28 C19 28 23 24 23 18 C23 14 15 4 15 4 Z',
  cobalt:     'M15 6 L6 15 L15 24 L24 15 Z M10 10 L20 20 M20 10 L10 20',
  verdant:    'M10 4 C10 4 20 12 20 16 C20 20 10 26 10 30 M20 4 C20 4 10 12 10 16 C10 20 20 26 20 30',
}

const RUNE_RADIUS = 52
const RUNE_POSITIONS = CEO_ORDER.map((id, i) => {
  const angle = ANGLE_OFFSET + (360 / 7) * i
  const rad = (angle * Math.PI) / 180
  return { id, x: 60 + RUNE_RADIUS * Math.cos(rad), y: 60 + RUNE_RADIUS * Math.sin(rad) }
})

const PARTICLES = Array.from({ length: 20 }, (_, i) => ({
  id: i,
  left: `${(i * 37 + 13) % 100}%`,
  top: `${(i * 53 + 7) % 100}%`,
  delay: `${(i * 1.3) % 8}s`,
  duration: `${12 + (i % 8) * 3}s`,
  size: 1 + (i % 3),
}))

export default function Boardroom() {
  const companies = useGameStore((s) => s.state.companies)
  const activeCeo = useGameStore((s) => s.state.current_active_ceo)
  const popupMessages = useGameStore((s) => s.popupMessages)

  return (
    <HUDFrame color="#FFD700" label="THE BOARDROOM" className="w-full h-full">
      <div className="relative w-full h-full bg-black overflow-hidden">

        {/* Background glow */}
        <div className="absolute inset-0 pointer-events-none"
          style={{ background: 'radial-gradient(circle at 50% 50%, rgba(212,175,55,0.03) 0%, transparent 60%)' }}
        />

        {/* Grid underlay */}
        <div className="absolute inset-0 pointer-events-none opacity-[0.02]"
          style={{
            backgroundImage: 'linear-gradient(rgba(255,215,0,0.4) 1px, transparent 1px), linear-gradient(90deg, rgba(255,215,0,0.4) 1px, transparent 1px)',
            backgroundSize: '80px 80px',
          }}
        />

        {/* Floating particles */}
        {PARTICLES.map(p => (
          <div key={p.id} className="absolute rounded-full pointer-events-none"
            style={{ left: p.left, top: p.top, width: p.size, height: p.size, backgroundColor: 'rgba(212,175,55,0.25)', animation: `particle-drift ${p.duration} ease-in-out ${p.delay} infinite alternate` }}
          />
        ))}

        {/* Center sigil */}
        <div className="absolute left-1/2 top-1/2 pointer-events-none"
          style={{ width: 120, height: 120, marginLeft: -60, marginTop: -60, animation: 'sigil-rotate 90s linear infinite', filter: 'drop-shadow(0 0 12px rgba(212,175,55,0.6))' }}
        >
          <svg width="120" height="120" viewBox="0 0 120 120" className="sigil-pulse">
            <circle cx="60" cy="60" r="56" fill="none" stroke="#D4AF37" strokeWidth="0.8" opacity="0.8" />
            <circle cx="60" cy="60" r="48" fill="none" stroke="#D4AF37" strokeWidth="0.4" opacity="0.5" />
            {CEO_ORDER.map((_, i) => {
              const a = (ANGLE_OFFSET + (360 / 7) * i) * Math.PI / 180
              return <line key={i} x1={(60 + 20 * Math.cos(a)).toFixed(2)} y1={(60 + 20 * Math.sin(a)).toFixed(2)} x2={(60 + 44 * Math.cos(a)).toFixed(2)} y2={(60 + 44 * Math.sin(a)).toFixed(2)} stroke="#D4AF37" strokeWidth="0.6" opacity="0.7" />
            })}
            <polygon
              points={CEO_ORDER.map((_, i) => {
                const a = (ANGLE_OFFSET + (360 / 7) * i) * Math.PI / 180
                return `${(60 + 20 * Math.cos(a)).toFixed(2)},${(60 + 20 * Math.sin(a)).toFixed(2)}`
              }).join(' ')}
              fill="none" stroke="#D4AF37" strokeWidth="0.5" opacity="0.6"
            />
            <circle cx="60" cy="60" r="2" fill="none" stroke="#D4AF37" strokeWidth="0.8" opacity="0.8" />
          </svg>

          {RUNE_POSITIONS.map(rune => (
            <svg key={rune.id} width="30" height="30" viewBox="0 0 30 30" className="absolute pointer-events-none"
              style={{ left: rune.x - 15, top: rune.y - 15, color: COMPANY_MAP[rune.id].color, opacity: 0.5, animation: 'sigil-counter-rotate 90s linear infinite' }}
            >
              <path d={SECTOR_RUNES[rune.id]} fill="none" stroke="currentColor" strokeWidth="1" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          ))}
        </div>

        {/* Ambient heartbeat */}
        <div className="absolute left-1/2 top-1/2 w-[160px] h-[160px] -translate-x-1/2 -translate-y-1/2 pointer-events-none rounded-full"
          style={{ background: 'radial-gradient(circle, rgba(212,175,55,0.08) 0%, transparent 70%)', animation: 'ambient-breathe 3s ease-in-out infinite' }}
        />

        {/* ═══ CANVAS LINE OVERLAY — pixel-perfect connections ═══ */}
        <LineOverlay positions={CEO_POSITIONS} />

        {/* Radial light toward active CEO */}
        {activeCeo && (
          <div className="absolute inset-0 pointer-events-none">
            <div className="absolute left-1/2 top-1/2 w-[400px] h-[400px] -translate-x-1/2 -translate-y-1/2"
              style={{ background: `radial-gradient(circle, ${COMPANY_MAP[activeCeo]?.color ?? '#FFD700'}10 0%, transparent 60%)` }}
            />
          </div>
        )}

        {/* Popup messages */}
        {popupMessages.map(msg => {
          const fromPos = CEO_POSITIONS[msg.from]
          const toPos = CEO_POSITIONS[msg.to]
          if (!fromPos || !toPos) return null
          return (
            <div key={msg.id} className="absolute z-20 max-w-[180px] px-2 py-1.5 pointer-events-none"
              style={{
                left: `${(fromPos.x + toPos.x) / 2}%`, top: `${(fromPos.y + toPos.y) / 2}%`,
                transform: 'translate(-50%, -50%)', background: 'rgba(0,0,0,0.9)',
                border: `1px solid ${msg.color}40`, animation: 'fadeIn 0.3s ease-out',
              }}
            >
              <p className="font-mono text-[9px] text-hud-bone/50 leading-snug line-clamp-2">
                &ldquo;{msg.text.slice(0, 60)}{msg.text.length > 60 ? '...' : ''}&rdquo;
              </p>
            </div>
          )
        })}

        {/* Attack animations */}
        <AttackAnimation positions={CEO_POSITIONS} />

        {/* CEO portraits */}
        {companies.map(company => (
          <CEOPortrait key={company.id} company={company} isActive={activeCeo === company.id} position={CEO_POSITIONS[company.id]} />
        ))}

        {/* Event banner */}
        <BetrayalBanner />
      </div>
    </HUDFrame>
  )
}

'use client'

import { motion } from 'motion/react'
import { useGameStore } from '@/store/gameStore'
import { COMPANY_MAP } from '@/lib/constants'
import HUDFrame from '@/components/ui/HUDFrame'
import CEOSigil from '@/components/boardroom/CEOSigil'

// Pre-computed rotations and clip-path variations for visual variety
const CARD_STYLES = [
  { rotation: -1.2, clipPath: 'polygon(0 0, 100% 0, 100% calc(100% - 10px), calc(100% - 6px) 100%, 0 100%)' },
  { rotation: 0.8, clipPath: 'polygon(0 0, 100% 0, 100% calc(100% - 8px), calc(100% - 10px) 100%, 0 calc(100% - 2px))' },
  { rotation: -0.5, clipPath: 'polygon(0 2px, 100% 0, 100% calc(100% - 12px), calc(100% - 8px) 100%, 0 100%)' },
  { rotation: 1.0, clipPath: 'polygon(0 0, 100% 1px, 100% calc(100% - 6px), calc(100% - 12px) 100%, 0 calc(100% - 3px))' },
  { rotation: -0.8, clipPath: 'polygon(0 0, 100% 0, 100% calc(100% - 9px), calc(100% - 7px) 100%, 0 100%)' },
]

// Seeded pseudo-random to determine which emails get REDACTED bars
function hashEmail(from: string, to: string, i: number): boolean {
  const h = (from.charCodeAt(0) * 31 + to.charCodeAt(0) * 17 + i * 53) % 100
  return h < 20 // ~20% get redacted treatment
}

export default function EmailInbox() {
  const emails = useGameStore((s) => s.state.recent_emails)
  const turn = useGameStore((s) => s.state.turn)

  return (
    <HUDFrame color="#00E5FF" label="INTEL FEED" className="h-full">
      <div className="flex flex-col h-full bg-black overflow-hidden">
        {/* Header */}
        <div className="px-5 pt-6 pb-3">
          <h2 className="font-display text-3xl tracking-[0.15em] text-hud-electric">
            INTEL FEED
          </h2>
          <p className="font-mono text-xs text-hud-bone/30 mt-1 tracking-wider">
            {emails.length} INTERCEPTED TRANSMISSIONS
          </p>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-4 pb-4 space-y-4">
          {emails.map((email, i) => {
            const from = COMPANY_MAP[email.from]
            const to = COMPANY_MAP[email.to]
            const style = CARD_STYLES[i % CARD_STYLES.length]
            const isRedacted = hashEmail(email.from, email.to, i)
            const timestamp = `${String(23 - i * 3).padStart(2, '0')}:${String(14 + i * 7).padStart(2, '0')}:${String(8 + i * 13).padStart(2, '0')}`

            return (
              <motion.div
                key={`${email.from}-${email.to}-${i}`}
                className="relative"
                style={{ transform: `rotate(${style.rotation}deg)` }}
                initial={{ opacity: 0, x: -30 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ duration: 0.5, delay: i * 0.1, ease: [0.16, 1, 0.3, 1] }}
              >
                {/* Tape strip sticker */}
                <div
                  className="absolute -top-1 right-3 w-10 h-4 z-10"
                  style={{
                    backgroundColor: 'rgba(212,175,55,0.25)',
                    transform: 'rotate(-15deg)',
                    borderRadius: 1,
                  }}
                />

                {/* Main card */}
                <div
                  className="relative p-4 border border-white/[0.04] overflow-hidden"
                  style={{
                    clipPath: style.clipPath,
                    background: 'linear-gradient(135deg, rgba(30,25,18,0.9) 0%, rgba(10,10,10,0.95) 100%)',
                  }}
                >
                  {/* Top accent stripe */}
                  <div className="absolute top-0 left-0 right-0 h-0.5" style={{ backgroundColor: `${from.color}40` }} />

                  {/* INTERCEPTED header block */}
                  <div className="font-mono text-[9px] leading-snug mb-3 text-hud-bone/30 border border-hud-bone/10 px-2 py-1.5 inline-block">
                    <div className="text-hud-electric/60 tracking-[0.2em] mb-0.5">INTERCEPTED</div>
                    <div>
                      <span className="tracking-wider">FROM </span>
                      <span className="font-bold tracking-wider" style={{ color: from.color }}>{from.shortName}</span>
                    </div>
                    <div>
                      <span className="tracking-wider">TO </span>
                      <span className="tracking-wider" style={{ color: `${to.color}80` }}>{to.shortName}</span>
                    </div>
                    <div className="text-hud-bone/15 mt-0.5">T-{String(turn).padStart(2, '0')} {timestamp}</div>
                  </div>

                  {/* Body — serif italic, like a real letter */}
                  <div className="relative">
                    <p className="font-serif text-[15px] italic text-hud-bone/60 leading-relaxed">
                      &ldquo;{email.text}&rdquo;
                    </p>

                    {/* REDACTED overlay on some messages */}
                    {isRedacted && (
                      <div
                        className="absolute top-1/2 left-2"
                        style={{
                          width: `${60 + (i * 17) % 30}px`,
                          height: 18,
                          backgroundColor: '#000',
                          transform: 'translateY(-50%)',
                        }}
                      >
                        <span className="font-mono text-[9px] text-hud-danger/80 tracking-[0.15em] absolute inset-0 flex items-center justify-center">
                          [CLASSIFIED]
                        </span>
                      </div>
                    )}
                  </div>

                  {/* Sender signature sigil — bottom right */}
                  <div className="absolute bottom-2 right-2 opacity-30">
                    <CEOSigil ceoId={email.from} size={20} color={from.color} />
                  </div>
                </div>

                {/* Speech bubble tail pointing toward boardroom (top-right) */}
                <div
                  className="absolute -top-1.5 right-8 w-3 h-3 rotate-45"
                  style={{
                    backgroundColor: 'rgba(30,25,18,0.9)',
                    borderTop: '1px solid rgba(255,255,255,0.04)',
                    borderLeft: '1px solid rgba(255,255,255,0.04)',
                  }}
                />
              </motion.div>
            )
          })}
        </div>
      </div>
    </HUDFrame>
  )
}

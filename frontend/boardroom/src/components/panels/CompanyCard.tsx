'use client'

import { useEffect, useRef, useState } from 'react'
import { motion } from 'motion/react'
import { COMPANY_MAP } from '@/lib/constants'
import { formatCurrency, formatPercent, formatReputation } from '@/lib/format'
import type { Company } from '@/lib/types'
import CEOSigil from '@/components/boardroom/CEOSigil'

function AnimatedNumber({ value, formatter }: { value: number; formatter: (v: number) => string }) {
  const [display, setDisplay] = useState(value)
  const prev = useRef(value)
  useEffect(() => {
    const from = prev.current
    const to = value
    if (from === to) return
    prev.current = to
    const duration = 600
    const start = performance.now()
    const tick = (now: number) => {
      const elapsed = now - start
      const progress = Math.min(elapsed / duration, 1)
      const eased = 1 - Math.pow(1 - progress, 3)
      setDisplay(from + (to - from) * eased)
      if (progress < 1) requestAnimationFrame(tick)
    }
    requestAnimationFrame(tick)
  }, [value])
  return <span>{formatter(display)}</span>
}

export default function CompanyCard({ company, index }: { company: Company; index: number }) {
  const def = COMPANY_MAP[company.id]
  const dead = !company.alive
  const prev = company.stock_history.length >= 2 ? company.stock_history[company.stock_history.length - 2] : company.stock_price
  const delta = company.stock_price - prev
  const up = delta >= 0

  return (
    <motion.div
      className={`relative overflow-hidden ${dead ? 'grayscale opacity-30' : ''}`}
      style={{
        background: '#0A0A0A',
        border: `1px solid ${dead ? '#222' : `${def.color}20`}`,
      }}
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: dead ? 0.3 : 1, y: 0 }}
      transition={{ duration: 0.5, delay: index * 0.06 }}
    >
      {/* Top color bar */}
      <div className="h-1" style={{ background: dead ? '#333' : def.color }} />

      {/* Diagonal accent stripe */}
      {!dead && (
        <div
          className="absolute top-0 right-0 w-16 h-full pointer-events-none opacity-[0.04]"
          style={{
            background: def.color,
            transform: 'skewX(-15deg)',
            transformOrigin: 'top right',
          }}
        />
      )}

      <div className="p-4 relative">
        {/* Header row: Sigil + Name + Stock */}
        <div className="flex items-start justify-between mb-3">
          <div className="flex items-center gap-2">
            <CEOSigil ceoId={company.id} size={28} color={dead ? '#444' : def.color} />
            <div>
              <h3 className="font-display text-xl tracking-wider leading-none" style={{ color: dead ? '#444' : def.color }}>
                {def.shortName}
              </h3>
              <p className="font-mono text-[10px] text-hud-bone/20 tracking-[0.15em] uppercase mt-0.5">
                {def.sector}
              </p>
              <p className="font-serif text-[10px] italic text-hud-bone/25 mt-0.5">
                {def.tagline}
              </p>
            </div>
          </div>
        </div>

        {dead ? (
          <div className="flex items-center justify-center py-3">
            <div className="px-4 py-1 border-2 border-hud-danger/50 font-display text-lg tracking-[0.2em] text-hud-danger/70 -rotate-3">
              BANKRUPT
            </div>
          </div>
        ) : (
          <>
            {/* Hero stock price */}
            <div className="mb-3">
              <span className="font-mono text-4xl font-bold text-hud-bone tracking-tight leading-none">
                $<AnimatedNumber value={company.stock_price} formatter={(v) => v.toFixed(2)} />
              </span>
              <span className={`ml-2 font-mono text-lg font-bold ${up ? 'text-hud-success' : 'text-hud-danger'}`}>
                {up ? '\u25B2' : '\u25BC'}{Math.abs(delta).toFixed(1)}
              </span>
            </div>

            {/* Stats row */}
            <div className="grid grid-cols-3 gap-3 pt-3 border-t border-white/[0.04]">
              <div>
                <p className="font-mono text-[9px] text-hud-bone/20 tracking-wider uppercase">Cash</p>
                <p className="font-mono text-sm text-hud-bone/70 mt-0.5">
                  <AnimatedNumber value={company.cash} formatter={formatCurrency} />
                </p>
              </div>
              <div>
                <p className="font-mono text-[9px] text-hud-bone/20 tracking-wider uppercase">Share</p>
                <p className="font-mono text-sm text-hud-bone/70 mt-0.5">
                  <AnimatedNumber value={company.market_share} formatter={formatPercent} />
                </p>
              </div>
              <div>
                <p className="font-mono text-[9px] text-hud-bone/20 tracking-wider uppercase">Rep</p>
                <p className="font-mono text-sm text-hud-bone/70 mt-0.5">
                  <AnimatedNumber value={company.reputation} formatter={formatReputation} />
                </p>
                {/* Rep bar */}
                <div className="h-1 mt-1 bg-white/[0.04] rounded-full overflow-hidden">
                  <motion.div
                    className="h-full rounded-full"
                    style={{
                      backgroundColor: company.reputation > 0.6 ? '#00D67A' : company.reputation > 0.3 ? '#FFB800' : '#FF2E4D',
                    }}
                    animate={{ width: `${company.reputation * 100}%` }}
                    transition={{ duration: 0.6 }}
                  />
                </div>
              </div>
            </div>
          </>
        )}
      </div>
    </motion.div>
  )
}

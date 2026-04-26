'use client'

import { useGameStore } from '@/store/gameStore'
import { COMPANY_MAP } from '@/lib/constants'
import { formatStockPrice } from '@/lib/format'

export default function StockTicker() {
  const companies = useGameStore((s) => s.state.companies)
  const items = [...companies, ...companies, ...companies]

  return (
    <div className="relative overflow-hidden bg-black border-y border-hud-electric/10 py-3">
      {/* Top accent line */}
      <div className="absolute top-0 left-0 right-0 h-px bg-hud-electric/20" />

      <div
        className="flex items-center whitespace-nowrap"
        style={{ animation: 'marquee 35s linear infinite' }}
      >
        {items.map((c, i) => {
          const def = COMPANY_MAP[c.id]
          const prev = c.stock_history.length >= 2 ? c.stock_history[c.stock_history.length - 2] : c.stock_price
          const delta = c.stock_price - prev
          const pct = prev > 0 ? (delta / prev) * 100 : 0
          const up = delta >= 0

          return (
            <div key={`${c.id}-${i}`} className="flex items-center gap-3 px-6">
              {/* Company name */}
              <span className="font-display text-2xl tracking-wider" style={{ color: def.color }}>
                {def.shortName}
              </span>
              {/* Price */}
              <span className="font-mono text-xl font-bold text-hud-bone/90 tracking-tight">
                {formatStockPrice(c.stock_price)}
              </span>
              {/* Delta */}
              <span className={`font-mono text-base font-bold ${up ? 'text-hud-success' : 'text-hud-danger'}`}>
                {up ? '\u25B2' : '\u25BC'} {Math.abs(pct).toFixed(1)}%
              </span>
              {/* Separator */}
              <span className="text-hud-electric/15 text-lg mx-2">|</span>
            </div>
          )
        })}
      </div>

      {/* Edge fades */}
      <div className="absolute inset-y-0 left-0 w-20 bg-gradient-to-r from-black to-transparent pointer-events-none z-10" />
      <div className="absolute inset-y-0 right-0 w-20 bg-gradient-to-l from-black to-transparent pointer-events-none z-10" />

      {/* Bottom accent line */}
      <div className="absolute bottom-0 left-0 right-0 h-px bg-hud-electric/10" />
    </div>
  )
}

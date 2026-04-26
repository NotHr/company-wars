'use client'

import { useState, useEffect } from 'react'
import {
  XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine,
  AreaChart, Area, CartesianGrid,
} from 'recharts'
import { useGameStore } from '@/store/gameStore'
import { COMPANY_MAP } from '@/lib/constants'
import HUDFrame from '@/components/ui/HUDFrame'

function CustomTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-black/95 border border-hud-royal/20 backdrop-blur-md px-4 py-3 shadow-2xl"
      style={{ boxShadow: '0 0 30px rgba(0,0,0,0.8), 0 0 2px rgba(255,215,0,0.2)' }}>
      <p className="font-display text-sm tracking-[0.2em] text-hud-royal mb-2">{label}</p>
      <div className="space-y-1">
        {payload
          .sort((a: any, b: any) => (b.value ?? 0) - (a.value ?? 0))
          .map((entry: any) => (
          <div key={entry.dataKey} className="flex items-center justify-between gap-6">
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 rounded-full" style={{ backgroundColor: entry.color, boxShadow: `0 0 6px ${entry.color}60` }} />
              <span className="font-mono text-[11px] text-hud-bone/50">{entry.name}</span>
            </div>
            <span className="font-mono text-xs font-bold" style={{ color: entry.color }}>
              ${(entry.value as number)?.toFixed(2)}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}

export default function StockChart() {
  const [mounted, setMounted] = useState(false)
  useEffect(() => setMounted(true), [])

  const companies = useGameStore((s) => s.state.companies)
  const turn = useGameStore((s) => s.state.turn)
  const maxLen = Math.max(...companies.map((c) => c.stock_history.length))
  const data = Array.from({ length: maxLen }, (_, i) => {
    const point: Record<string, number | string> = { turn: `T${i}` }
    for (const c of companies) {
      if (c.alive || i < c.stock_history.length) {
        point[c.id] = c.stock_history[i] ?? 0
      }
    }
    return point
  })

  const allPrices = companies.flatMap(c => c.stock_history)
  const minPrice = Math.floor(Math.min(...allPrices) / 10) * 10
  const maxPrice = Math.ceil(Math.max(...allPrices) / 10) * 10

  return (
    <HUDFrame color="#FFB800" label="MARKET" className="w-full h-full">
      <div className="w-full h-full bg-black relative overflow-hidden">
        {/* Ambient glow */}
        <div className="absolute inset-0 pointer-events-none"
          style={{ background: 'radial-gradient(ellipse at 50% 80%, rgba(255,184,0,0.03) 0%, transparent 60%)' }}
        />

        {/* Header */}
        <div className="flex items-center justify-between px-5 pt-4 pb-2 relative z-10">
          <div className="flex items-center gap-3">
            <h2 className="font-display text-2xl tracking-[0.15em] text-hud-warning">MARKET</h2>
            <div className="w-px h-5 bg-hud-bone/10" />
            <span className="font-mono text-[10px] text-hud-bone/25 tracking-wider">TURN {turn}</span>
          </div>
          <div className="flex items-center gap-4 flex-wrap justify-end">
            {companies.map(c => (
              <div key={c.id} className="flex items-center gap-1.5 group">
                <div className="w-2.5 h-2.5 rounded-full transition-all group-hover:scale-125"
                  style={{
                    backgroundColor: COMPANY_MAP[c.id].color,
                    boxShadow: `0 0 6px ${COMPANY_MAP[c.id].color}40`,
                    opacity: c.alive ? 1 : 0.25,
                  }}
                />
                <span className={`font-mono text-[10px] tracking-wide transition-colors ${c.alive ? 'text-hud-bone/40 group-hover:text-hud-bone/70' : 'text-hud-bone/15 line-through'}`}>
                  {COMPANY_MAP[c.id].shortName}
                </span>
                <span className="font-mono text-[9px] ml-0.5" style={{
                  color: c.alive ? COMPANY_MAP[c.id].color : 'rgba(245,241,232,0.1)',
                }}>
                  ${c.stock_price.toFixed(0)}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Chart */}
        <div className="h-[calc(100%-52px)] px-2 relative">
          {!mounted ? (
            <div className="w-full h-full flex items-center justify-center">
              <span className="font-mono text-xs text-hud-bone/15 tracking-wider">LOADING MARKET DATA...</span>
            </div>
          ) : (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data} margin={{ top: 8, right: 16, left: -10, bottom: 4 }}>
              <defs>
                {companies.map(c => (
                  <linearGradient key={`grad-${c.id}`} id={`gradient-${c.id}`} x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={COMPANY_MAP[c.id].color} stopOpacity={0.12} />
                    <stop offset="100%" stopColor={COMPANY_MAP[c.id].color} stopOpacity={0} />
                  </linearGradient>
                ))}
              </defs>

              <CartesianGrid strokeDasharray="3 6" stroke="rgba(255,215,0,0.04)" vertical={false} />

              <ReferenceLine y={100} stroke="rgba(255,215,0,0.08)" strokeDasharray="8 4"
                label={{ value: 'IPO $100', position: 'right', fill: 'rgba(255,215,0,0.15)', fontSize: 9, fontFamily: 'var(--font-jetbrains)' }}
              />

              <XAxis
                dataKey="turn"
                tick={{ fill: 'rgba(245,241,232,0.2)', fontSize: 10, fontFamily: 'var(--font-jetbrains)' }}
                axisLine={{ stroke: 'rgba(255,255,255,0.04)' }}
                tickLine={false}
              />
              <YAxis
                domain={[minPrice, maxPrice]}
                tick={{ fill: 'rgba(245,241,232,0.15)', fontSize: 9, fontFamily: 'var(--font-jetbrains)' }}
                axisLine={false}
                tickLine={false}
                width={35}
                tickFormatter={(v: number) => `$${v}`}
              />
              <Tooltip content={<CustomTooltip />} />

              {companies.map(c => (
                <Area
                  key={c.id}
                  type="monotone"
                  dataKey={c.id}
                  name={COMPANY_MAP[c.id].shortName}
                  stroke={COMPANY_MAP[c.id].color}
                  strokeWidth={c.alive ? 2.5 : 1}
                  strokeOpacity={c.alive ? 1 : 0.2}
                  strokeDasharray={c.alive ? undefined : '4 4'}
                  fill={c.alive ? `url(#gradient-${c.id})` : 'transparent'}
                  dot={{
                    r: 3,
                    fill: COMPANY_MAP[c.id].color,
                    stroke: COMPANY_MAP[c.id].color,
                    strokeWidth: 1,
                    style: { filter: `drop-shadow(0 0 4px ${COMPANY_MAP[c.id].color}80)` },
                  }}
                  activeDot={{
                    r: 6,
                    strokeWidth: 2,
                    stroke: COMPANY_MAP[c.id].color,
                    fill: '#000',
                    style: { filter: `drop-shadow(0 0 8px ${COMPANY_MAP[c.id].color})` },
                  }}
                  animationDuration={800}
                  animationEasing="ease-out"
                />
              ))}
            </AreaChart>
          </ResponsiveContainer>
          )}
        </div>
      </div>
    </HUDFrame>
  )
}

'use client'

import { useEffect, useRef } from 'react'
import { useGameStore } from '@/store/gameStore'
import StockTicker from '@/components/ticker/StockTicker'
import Boardroom from '@/components/boardroom/Boardroom'
import EmailInbox from '@/components/panels/EmailInbox'
import EventLog from '@/components/panels/EventLog'
import PressWire from '@/components/panels/PressWire'
import CompanyCard from '@/components/panels/CompanyCard'
import StockChart from '@/components/charts/StockChart'
import HUDFrame from '@/components/ui/HUDFrame'
import DemoControls from '@/components/replay/DemoControls'

function PhaseBanner() {
  const mode = useGameStore((s) => s.mode)
  const phase = useGameStore((s) => s.phase)
  const turn = useGameStore((s) => s.state.turn)
  const maxTurns = useGameStore((s) => s.state.max_turns)
  const status = useGameStore((s) => s.state.status)

  const phaseColors: Record<string, string> = {
    IDLE: '#666',
    NEGOTIATION: '#00E5FF',
    ACTION: '#FF2E4D',
    RESOLUTION: '#FFD700',
    TURN_END: '#00D67A',
  }

  return (
    <header className="sticky top-0 z-40 bg-black/90 backdrop-blur-sm border-b border-white/[0.04]">
      <div className="max-w-[1920px] mx-auto flex items-center justify-between px-6 h-14">
        {/* Logo */}
        <div className="flex items-center gap-4">
          <h1 className="gold-text font-display text-3xl tracking-[0.3em]">
            BOARDROOM
          </h1>
          <div className="w-8 h-6 bg-hud-royal/5 -skew-x-12 hidden md:block" />
        </div>

        {/* Center: Phase indicator */}
        <div className="flex items-center gap-4">
          <span
            className="font-mono text-xs tracking-[0.25em] uppercase px-3 py-1 border"
            style={{
              color: phaseColors[phase] ?? '#666',
              borderColor: `${phaseColors[phase] ?? '#666'}40`,
              backgroundColor: `${phaseColors[phase] ?? '#666'}10`,
            }}
          >
            {phase === 'IDLE' ? 'STANDBY' : phase.replace(/_/g, ' ')}
          </span>
        </div>

        {/* Right side */}
        <div className="flex items-center gap-6">
          {/* Turn counter */}
          <div className="flex items-baseline gap-2">
            <span className="font-mono text-xs text-hud-bone/25 tracking-widest">TURN</span>
            <span className="font-display text-4xl text-hud-royal leading-none">{turn}</span>
            <span className="font-mono text-lg text-hud-bone/15">/ {maxTurns}</span>
          </div>

          <div className="w-px h-6 bg-white/[0.06]" />

          {/* Status */}
          {status === 'finished' ? (
            <span className="font-display text-xl text-hud-danger tracking-[0.2em] animate-pulse">GAME OVER</span>
          ) : (
            <div className="flex items-center gap-2">
              <div
                className={`w-2 h-2 rounded-full ${mode === 'live' ? 'bg-hud-success' : 'bg-hud-warning'}`}
                style={{ boxShadow: mode === 'live' ? '0 0 8px #00D67A' : '0 0 8px #FFB800' }}
              />
              <span className={`font-display text-lg tracking-[0.15em] ${mode === 'live' ? 'text-hud-success' : 'text-hud-warning'}`}>
                {mode === 'live' ? 'LIVE' : 'DEMO'}
              </span>
            </div>
          )}
        </div>
      </div>
    </header>
  )
}

function CommsLog() {
  const commsLog = useGameStore((s) => s.commsLog)
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollLeft = scrollRef.current.scrollWidth
    }
  }, [commsLog])

  // Show last 5 messages as a ticker
  const recent = commsLog.slice(-5)

  return (
    <div className="fixed bottom-0 left-0 right-0 z-30 bg-black/95 border-t border-hud-success/10">
      <div
        ref={scrollRef}
        className="max-w-[1920px] mx-auto px-4 py-2 flex items-center gap-6 overflow-x-auto scrollbar-hide"
      >
        <span className="shrink-0 font-mono text-[10px] text-hud-success/60 tracking-[0.15em] uppercase">
          COMMS
        </span>
        <div className="flex-1 flex items-center gap-4 min-w-0">
          {recent.map((msg, i) => (
            <span
              key={`${commsLog.length - 5 + i}`}
              className="shrink-0 font-mono text-[11px] text-hud-success/80 whitespace-nowrap"
              style={{
                opacity: 0.4 + (i / recent.length) * 0.6,
                animation: i === recent.length - 1 ? 'fadeIn 0.3s ease-out' : undefined,
              }}
            >
              {msg}
            </span>
          ))}
          <span className="comms-cursor shrink-0" />
        </div>
      </div>
    </div>
  )
}

export default function Home() {
  const startDirector = useGameStore((s) => s.startDirector)
  const stopDirector = useGameStore((s) => s.stopDirector)
  const toggleControls = useGameStore((s) => s.toggleControls)
  const state = useGameStore((s) => s.state)

  // Auto-start director on mount — single entry point, no double-start
  useEffect(() => {
    startDirector()
    return () => stopDirector()
  }, [startDirector, stopDirector])

  // D key toggle for hidden controls
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'd' || e.key === 'D') {
        if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return
        toggleControls()
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [toggleControls])

  return (
    <div className="min-h-screen w-full bg-black relative">
      {/* Phase Banner (replaces old header) */}
      <PhaseBanner />

      {/* Stock Ticker */}
      <StockTicker />

      {/* Main Content */}
      <main className="max-w-[1920px] mx-auto px-4 py-6 space-y-6">
        {/* Row 1: Intel Feed + Boardroom + Event Log — FIXED height so panels scroll, boardroom stays compact */}
        <div className="grid grid-cols-[280px_1fr_280px] gap-4" style={{ height: 620 }}>
          <div className="h-full overflow-hidden">
            <EmailInbox />
          </div>
          <div className="h-full overflow-hidden">
            <Boardroom />
          </div>
          <div className="h-full overflow-hidden">
            <EventLog />
          </div>
        </div>

        {/* Row 2: Stock Chart */}
        <div style={{ height: 300 }}>
          <StockChart />
        </div>

        {/* Row 3: Company Cards */}
        <div>
          <div className="flex items-center gap-3 mb-4 px-2">
            <div className="w-1 h-6 bg-hud-royal" />
            <h2 className="font-display text-3xl tracking-[0.15em] text-hud-royal">PORTFOLIO</h2>
            <span className="font-mono text-sm text-hud-bone/20 tracking-wider">
              {state.companies.filter(c => c.alive).length}/{state.companies.length} ACTIVE
            </span>
            <div className="flex-1 h-px bg-gradient-to-r from-hud-royal/20 to-transparent ml-4" />
          </div>
          <div className="grid grid-cols-4 gap-3">
            {state.companies.map((company, i) => (
              <CompanyCard key={company.id} company={company} index={i} />
            ))}
          </div>
        </div>

        {/* Row 4: Press Wire */}
        <HUDFrame color="#FFB800" className="w-full">
          <PressWire />
        </HUDFrame>

        {/* Footer spacer for comms log */}
        <div className="h-16" />
      </main>

      {/* Comms Log Ticker — fixed at bottom */}
      <CommsLog />

      {/* Demo Controls — hidden behind D key */}
      <DemoControls />
    </div>
  )
}

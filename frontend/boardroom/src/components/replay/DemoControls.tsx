'use client'

import { useGameStore } from '@/store/gameStore'

export default function DemoControls() {
  const showControls = useGameStore((s) => s.showControls)
  const isRunning = useGameStore((s) => s.isRunning)
  const turn = useGameStore((s) => s.state.turn)
  const phase = useGameStore((s) => s.phase)
  const mode = useGameStore((s) => s.mode)
  const startDirector = useGameStore((s) => s.startDirector)
  const stopDirector = useGameStore((s) => s.stopDirector)

  if (!showControls) return null

  return (
    <div className="fixed bottom-10 left-0 right-0 z-50 pointer-events-none">
      <div className="max-w-[600px] mx-auto bg-black/95 backdrop-blur-sm border border-hud-electric/20 rounded-lg p-4 pointer-events-auto">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-3">
            <span className="font-mono text-[10px] text-hud-electric/60 tracking-[0.15em] uppercase">
              Director Controls
            </span>
            <span className="font-mono text-[9px] text-hud-bone/20">
              Press D to hide
            </span>
          </div>
          <div className="flex items-center gap-2">
            <span className="font-mono text-[10px] text-hud-bone/40">
              {mode.toUpperCase()} | T{turn} | {phase}
            </span>
          </div>
        </div>

        <div className="flex items-center justify-center gap-4">
          {/* Play / Stop */}
          <button
            onClick={isRunning ? stopDirector : startDirector}
            className="w-12 h-12 rounded-full border-2 flex items-center justify-center transition-all hover:scale-105"
            style={{
              borderColor: isRunning ? '#FF2E4D' : '#00E5FF',
              color: isRunning ? '#FF2E4D' : '#00E5FF',
              boxShadow: isRunning ? '0 0 16px rgba(255,46,77,0.3)' : '0 0 16px rgba(0,229,255,0.2)',
            }}
          >
            {isRunning ? (
              <span className="font-mono text-lg font-bold">&#9632;</span>
            ) : (
              <span className="font-mono text-lg font-bold ml-0.5">&#9654;</span>
            )}
          </button>

          {/* Status */}
          <div className="flex items-center gap-2">
            <div className={`w-2 h-2 rounded-full ${isRunning ? 'bg-hud-success animate-pulse' : 'bg-hud-bone/20'}`} />
            <span className="font-mono text-xs text-hud-bone/50">
              {isRunning ? 'Director running' : 'Director stopped'}
            </span>
          </div>
        </div>
      </div>
    </div>
  )
}

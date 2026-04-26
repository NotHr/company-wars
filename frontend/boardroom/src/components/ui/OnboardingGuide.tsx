'use client'

import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'motion/react'

const GUIDE_STEPS = [
  {
    title: 'WELCOME TO BOARDROOM',
    description: '7 AI CEOs wage corporate warfare. Watch betrayals, hostile takeovers, and market manipulation unfold in real-time.',
    hint: 'Use the controls at the bottom to step through turns, or press play to watch it unfold.',
  },
  {
    title: 'THE BOARDROOM',
    description: 'The central arena. CEOs are arranged in a ring. Watch for glowing projectiles — those are attacks between companies.',
    hint: 'Partnership lines connect allied CEOs. Flashing rings highlight the active CEO.',
  },
  {
    title: 'INTEL & EVENTS',
    description: 'Left panel: intercepted emails between CEOs. Right panel: event log tracking every betrayal, bankruptcy, and action.',
    hint: 'Events are color-coded by company. Scroll to see history.',
  },
  {
    title: 'MARKET & PORTFOLIO',
    description: 'Stock chart tracks each company\'s price. Company cards show financials. Watch prices react to events.',
    hint: 'Hover the chart to compare prices. Dead companies show as dashed lines.',
  },
]

export default function OnboardingGuide() {
  const [visible, setVisible] = useState(false)
  const [step, setStep] = useState(0)

  useEffect(() => {
    const seen = localStorage.getItem('boardroom-onboarding-seen')
    if (!seen) setVisible(true)
  }, [])

  const dismiss = () => {
    setVisible(false)
    localStorage.setItem('boardroom-onboarding-seen', 'true')
  }

  const next = () => {
    if (step < GUIDE_STEPS.length - 1) {
      setStep(step + 1)
    } else {
      dismiss()
    }
  }

  const current = GUIDE_STEPS[step]

  return (
    <AnimatePresence>
      {visible && (
        <motion.div
          className="fixed inset-0 z-[60] flex items-center justify-center"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
        >
          {/* Backdrop */}
          <div className="absolute inset-0 bg-black/80 backdrop-blur-sm" onClick={dismiss} />

          {/* Card */}
          <motion.div
            className="relative z-10 max-w-lg w-full mx-4"
            initial={{ y: 30, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: -20, opacity: 0 }}
            transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
            key={step}
          >
            <div className="bg-hud-ink border border-hud-royal/20 p-8 relative overflow-hidden">
              {/* Corner accents */}
              <div className="absolute top-0 left-0 w-4 h-4 border-t-2 border-l-2 border-hud-royal/40" />
              <div className="absolute top-0 right-0 w-4 h-4 border-t-2 border-r-2 border-hud-royal/40" />
              <div className="absolute bottom-0 left-0 w-4 h-4 border-b-2 border-l-2 border-hud-royal/40" />
              <div className="absolute bottom-0 right-0 w-4 h-4 border-b-2 border-r-2 border-hud-royal/40" />

              {/* Step indicator */}
              <div className="flex items-center gap-2 mb-6">
                {GUIDE_STEPS.map((_, i) => (
                  <div
                    key={i}
                    className="h-1 flex-1 rounded-full transition-colors"
                    style={{
                      backgroundColor: i <= step ? '#FFD700' : 'rgba(255,255,255,0.06)',
                    }}
                  />
                ))}
              </div>

              {/* Content */}
              <h2 className="font-display text-3xl tracking-[0.12em] text-hud-royal mb-3">
                {current.title}
              </h2>
              <p className="font-sans text-sm text-hud-bone/70 leading-relaxed mb-4">
                {current.description}
              </p>
              <p className="font-mono text-xs text-hud-electric/50 leading-relaxed">
                {current.hint}
              </p>

              {/* Actions */}
              <div className="flex items-center justify-between mt-8">
                <button
                  onClick={dismiss}
                  className="font-mono text-xs text-hud-bone/25 hover:text-hud-bone/50 transition-colors tracking-wider"
                >
                  SKIP
                </button>
                <button
                  onClick={next}
                  className="font-display text-lg tracking-[0.15em] px-6 py-2 border border-hud-royal/40 text-hud-royal hover:bg-hud-royal/10 transition-colors"
                >
                  {step < GUIDE_STEPS.length - 1 ? 'NEXT' : 'START'}
                </button>
              </div>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}

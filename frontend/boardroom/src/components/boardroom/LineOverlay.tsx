'use client'

import { useRef, useEffect, useCallback } from 'react'
import { useGameStore } from '@/store/gameStore'
import { COMPANY_MAP } from '@/lib/constants'
import type { CEOId } from '@/lib/types'

interface LineOverlayProps {
  positions: Record<CEOId, { x: number; y: number }>
}

// Animated dash offset for "data flow" effect
let animFrame = 0

export default function LineOverlay({ positions }: LineOverlayProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const rafRef = useRef<number>(0)

  const activeCeo = useGameStore((s) => s.state.current_active_ceo)
  const partnerships = useGameStore((s) => s.state.active_partnerships)
  const connectionLines = useGameStore((s) => s.connectionLines)

  const draw = useCallback(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const parent = canvas.parentElement
    if (!parent) return

    const rect = parent.getBoundingClientRect()
    const w = rect.width
    const h = rect.height
    const dpr = window.devicePixelRatio || 1

    canvas.width = w * dpr
    canvas.height = h * dpr
    canvas.style.width = `${w}px`
    canvas.style.height = `${h}px`

    const ctx = canvas.getContext('2d')
    if (!ctx) return
    ctx.scale(dpr, dpr)
    ctx.clearRect(0, 0, w, h)

    const px = (id: CEOId) => ({
      x: (positions[id].x / 100) * w,
      y: (positions[id].y / 100) * h,
    })

    const centerX = w / 2
    const centerY = h / 2

    animFrame += 0.5

    // ── 1. Active CEO beam (center → active CEO) — subtle, thin ──
    if (activeCeo && positions[activeCeo]) {
      const to = px(activeCeo)
      const color = COMPANY_MAP[activeCeo]?.color ?? '#FFD700'

      // Soft glow line
      ctx.save()
      ctx.strokeStyle = color
      ctx.lineWidth = 6
      ctx.globalAlpha = 0.06
      ctx.beginPath()
      ctx.moveTo(centerX, centerY)
      ctx.lineTo(to.x, to.y)
      ctx.stroke()
      ctx.restore()

      // Main thin line
      ctx.save()
      ctx.strokeStyle = color
      ctx.lineWidth = 1
      ctx.globalAlpha = 0.4
      ctx.beginPath()
      ctx.moveTo(centerX, centerY)
      ctx.lineTo(to.x, to.y)
      ctx.stroke()
      ctx.restore()
    }

    // ── 2. Partnership lines — solid, subtle ──
    const activePartnerships = partnerships.filter(p => p.active)
    for (const p of activePartnerships) {
      if (!positions[p.ceo_a] || !positions[p.ceo_b]) continue
      const a = px(p.ceo_a)
      const b = px(p.ceo_b)
      const colorA = COMPANY_MAP[p.ceo_a]?.color ?? '#FFD700'
      const colorB = COMPANY_MAP[p.ceo_b]?.color ?? '#FFD700'

      // Gradient line
      const grad = ctx.createLinearGradient(a.x, a.y, b.x, b.y)
      grad.addColorStop(0, colorA)
      grad.addColorStop(1, colorB)

      // Glow
      ctx.save()
      ctx.strokeStyle = grad
      ctx.lineWidth = 4
      ctx.globalAlpha = 0.08
      ctx.beginPath()
      ctx.moveTo(a.x, a.y)
      ctx.lineTo(b.x, b.y)
      ctx.stroke()
      ctx.restore()

      // Main line
      ctx.save()
      ctx.strokeStyle = grad
      ctx.lineWidth = 1
      ctx.globalAlpha = 0.3
      ctx.beginPath()
      ctx.moveTo(a.x, a.y)
      ctx.lineTo(b.x, b.y)
      ctx.stroke()
      ctx.restore()

      // Small dots at endpoints
      ctx.save()
      ctx.globalAlpha = 0.4
      ctx.fillStyle = colorA
      ctx.beginPath()
      ctx.arc(a.x, a.y, 2, 0, Math.PI * 2)
      ctx.fill()
      ctx.fillStyle = colorB
      ctx.beginPath()
      ctx.arc(b.x, b.y, 2, 0, Math.PI * 2)
      ctx.fill()
      ctx.restore()
    }

    // ── 3. Director connection lines — dashed with flowing animation ──
    for (const line of connectionLines) {
      if (!positions[line.from] || !positions[line.to]) continue
      const from = px(line.from)
      const to = px(line.to)

      // Glow
      ctx.save()
      ctx.strokeStyle = line.color
      ctx.lineWidth = 4
      ctx.globalAlpha = 0.08
      ctx.beginPath()
      ctx.moveTo(from.x, from.y)
      ctx.lineTo(to.x, to.y)
      ctx.stroke()
      ctx.restore()

      // Main line with animated dash
      ctx.save()
      ctx.strokeStyle = line.color
      ctx.lineWidth = 1.5
      ctx.globalAlpha = 0.5

      if (line.style === 'dash' || line.style === 'broken') {
        const dashLen = line.style === 'dash' ? 10 : 5
        const gapLen = line.style === 'dash' ? 6 : 5
        ctx.setLineDash([dashLen, gapLen])
        ctx.lineDashOffset = -animFrame // Animated flow
      }

      ctx.beginPath()
      ctx.moveTo(from.x, from.y)
      ctx.lineTo(to.x, to.y)
      ctx.stroke()
      ctx.restore()

      // Dots at endpoints
      ctx.save()
      ctx.fillStyle = line.color
      ctx.globalAlpha = 0.7
      ctx.beginPath()
      ctx.arc(from.x, from.y, 2.5, 0, Math.PI * 2)
      ctx.fill()
      ctx.beginPath()
      ctx.arc(to.x, to.y, 2.5, 0, Math.PI * 2)
      ctx.fill()
      ctx.restore()
    }
  }, [activeCeo, partnerships, connectionLines, positions])

  // Animation loop — redraws every frame for dash animation
  useEffect(() => {
    let running = true
    const hasAnimated = () => connectionLines.length > 0

    const loop = () => {
      if (!running) return
      draw()
      if (hasAnimated()) {
        rafRef.current = requestAnimationFrame(loop)
      }
    }

    // Always draw at least once
    draw()

    // Only start animation loop if we have dashed lines
    if (hasAnimated()) {
      rafRef.current = requestAnimationFrame(loop)
    }

    return () => {
      running = false
      cancelAnimationFrame(rafRef.current)
    }
  }, [draw, connectionLines.length])

  // Redraw on resize
  useEffect(() => {
    const handleResize = () => draw()
    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [draw])

  return (
    <canvas
      ref={canvasRef}
      className="absolute inset-0 pointer-events-none"
      style={{ zIndex: 3 }}
    />
  )
}

'use client'

import { useRef, useEffect, useState, useCallback } from 'react'
import { motion } from 'motion/react'
import { COMPANY_MAP } from '@/lib/constants'
import type { Partnership, CEOId } from '@/lib/types'

interface PartnershipLineProps {
  partnership: Partnership
  positions: Record<CEOId, { x: number; y: number }>
}

function blendColors(a: string, b: string): string {
  const pa = parseInt(a.slice(1), 16)
  const pb = parseInt(b.slice(1), 16)
  const r = ((pa >> 16) + (pb >> 16)) >> 1
  const g = (((pa >> 8) & 0xff) + ((pb >> 8) & 0xff)) >> 1
  const bl = ((pa & 0xff) + (pb & 0xff)) >> 1
  return `#${((r << 16) | (g << 8) | bl).toString(16).padStart(6, '0')}`
}

export default function PartnershipLine({ partnership, positions }: PartnershipLineProps) {
  const a = positions[partnership.ceo_a]
  const b = positions[partnership.ceo_b]
  const containerRef = useRef<SVGSVGElement>(null)
  const [size, setSize] = useState({ w: 1, h: 1 })

  const measure = useCallback(() => {
    const parent = containerRef.current?.parentElement
    if (parent) {
      const rect = parent.getBoundingClientRect()
      setSize({ w: rect.width, h: rect.height })
    }
  }, [])

  useEffect(() => {
    measure()
    window.addEventListener('resize', measure)
    return () => window.removeEventListener('resize', measure)
  }, [measure])

  if (!a || !b) return null

  const colorA = COMPANY_MAP[partnership.ceo_a].color
  const colorB = COMPANY_MAP[partnership.ceo_b].color
  const blended = blendColors(colorA, colorB)
  const id = `p-${partnership.ceo_a}-${partnership.ceo_b}`

  // Convert percentage positions to pixel coordinates
  const ax = (a.x / 100) * size.w
  const ay = (a.y / 100) * size.h
  const bx = (b.x / 100) * size.w
  const by = (b.y / 100) * size.h

  // Bezier control point: offset toward center in PIXEL space (aspect-ratio correct)
  const midX = (ax + bx) / 2
  const midY = (ay + by) / 2
  const centerX = size.w / 2
  const centerY = size.h / 2
  const toCenterX = centerX - midX
  const toCenterY = centerY - midY
  const len = Math.sqrt(toCenterX * toCenterX + toCenterY * toCenterY) || 1
  const curveStrength = 40 // pixels
  const cpX = midX + (toCenterX / len) * curveStrength
  const cpY = midY + (toCenterY / len) * curveStrength

  const pathD = `M ${ax} ${ay} Q ${cpX} ${cpY} ${bx} ${by}`

  return (
    <svg
      ref={containerRef}
      className="absolute inset-0 w-full h-full pointer-events-none"
      viewBox={`0 0 ${size.w} ${size.h}`}
      style={{ zIndex: 0 }}
    >
      <defs>
        <linearGradient id={id} x1={`${a.x}%`} y1={`${a.y}%`} x2={`${b.x}%`} y2={`${b.y}%`}>
          <stop offset="0%" stopColor={colorA} stopOpacity={0.7} />
          <stop offset="50%" stopColor="#D4AF37" stopOpacity={0.3} />
          <stop offset="100%" stopColor={colorB} stopOpacity={0.7} />
        </linearGradient>
        <filter id={`${id}-glow`}>
          <feGaussianBlur stdDeviation="2" result="blur" />
          <feMerge>
            <feMergeNode in="blur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>

      {/* Glow arc */}
      <motion.path
        d={pathD}
        fill="none"
        stroke={blended}
        strokeWidth={3}
        strokeOpacity={0.15}
        filter={`url(#${id}-glow)`}
        initial={{ pathLength: 0 }}
        animate={{ pathLength: 1 }}
        transition={{ duration: 1.2, ease: [0.25, 0.1, 0.25, 1] }}
      />

      {/* Main arc */}
      <motion.path
        d={pathD}
        fill="none"
        stroke={`url(#${id})`}
        strokeWidth={1.5}
        strokeOpacity={0.5}
        initial={{ pathLength: 0 }}
        animate={{ pathLength: 1 }}
        transition={{ duration: 1.2, ease: [0.25, 0.1, 0.25, 1] }}
      />

      {/* Traveling pulse dot */}
      <circle r="3" fill={blended} opacity="0.7" filter={`url(#${id}-glow)`}>
        <animateMotion dur="2.5s" repeatCount="indefinite" path={pathD} />
      </circle>
    </svg>
  )
}

'use client'

import type { CEOId } from '@/lib/types'

// Bold geometric SVG sigils for each company
const SIGILS: Record<CEOId, React.ReactNode> = {
  // CRIMSON & CO (Finance) — aggressive bull horns
  vermillion: (
    <g>
      <path d="M20 38 L30 12 L35 22 L40 12 L50 38" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
      <line x1="25" y1="28" x2="45" y2="28" stroke="currentColor" strokeWidth="1.5" />
    </g>
  ),
  // HELIOS LABS (Tech) — circuit spire
  goldspire: (
    <g>
      <path d="M35 10 L35 22 L25 32 L25 42 M35 10 L35 22 L45 32 L45 42" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
      <circle cx="35" cy="10" r="2" fill="currentColor" />
      <circle cx="25" cy="42" r="2" fill="currentColor" />
      <circle cx="45" cy="42" r="2" fill="currentColor" />
      <line x1="28" y1="22" x2="42" y2="22" stroke="currentColor" strokeWidth="1.5" />
    </g>
  ),
  // OBSIDIAN MEDIA (Media) — broadcast rays
  sablemark: (
    <g>
      <circle cx="35" cy="35" r="4" fill="currentColor" />
      <path d="M35 10 L35 20" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
      <path d="M35 50 L35 40" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
      <path d="M15 25 L23 30" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
      <path d="M55 25 L47 30" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
      <path d="M15 45 L23 40" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
      <path d="M55 45 L47 40" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    </g>
  ),
  // ATLAS FREIGHT (Shipping) — shield / anchor
  ironhold: (
    <g>
      <path d="M35 10 L50 20 L50 35 L35 48 L20 35 L20 20 Z" fill="none" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" />
      <line x1="35" y1="18" x2="35" y2="40" stroke="currentColor" strokeWidth="1.5" />
      <line x1="28" y1="30" x2="42" y2="30" stroke="currentColor" strokeWidth="1.5" />
    </g>
  ),
  // DRACO PETROLEUM (Oil) — flame
  ashen: (
    <g>
      <path d="M35 10 C35 10 25 25 25 32 C25 40 30 45 35 48 C40 45 45 40 45 32 C45 25 35 10 35 10 Z" fill="none" stroke="currentColor" strokeWidth="2" />
      <path d="M35 25 C35 25 30 32 30 35 C30 38 32 40 35 42 C38 40 40 38 40 35 C40 32 35 25 35 25 Z" fill="currentColor" opacity="0.4" />
    </g>
  ),
  // AZURE WIRELESS (Telecom) — connected nodes
  cobalt: (
    <g>
      <circle cx="35" cy="15" r="3" fill="currentColor" />
      <circle cx="20" cy="35" r="3" fill="currentColor" />
      <circle cx="50" cy="35" r="3" fill="currentColor" />
      <circle cx="35" cy="48" r="3" fill="currentColor" />
      <line x1="35" y1="18" x2="20" y2="32" stroke="currentColor" strokeWidth="1.5" />
      <line x1="35" y1="18" x2="50" y2="32" stroke="currentColor" strokeWidth="1.5" />
      <line x1="20" y1="38" x2="35" y2="45" stroke="currentColor" strokeWidth="1.5" />
      <line x1="50" y1="38" x2="35" y2="45" stroke="currentColor" strokeWidth="1.5" />
      <line x1="20" y1="35" x2="50" y2="35" stroke="currentColor" strokeWidth="1" opacity="0.4" />
    </g>
  ),
  // SERAPHIM BIOTECH (Biotech) — DNA helix
  verdant: (
    <g>
      <path d="M28 10 C28 10 42 18 42 26 C42 34 28 42 28 50" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
      <path d="M42 10 C42 10 28 18 28 26 C28 34 42 42 42 50" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
      <line x1="30" y1="18" x2="40" y2="18" stroke="currentColor" strokeWidth="1" opacity="0.5" />
      <line x1="29" y1="30" x2="41" y2="30" stroke="currentColor" strokeWidth="1" opacity="0.5" />
      <line x1="30" y1="42" x2="40" y2="42" stroke="currentColor" strokeWidth="1" opacity="0.5" />
    </g>
  ),
}

interface CEOSigilProps {
  ceoId: CEOId
  size?: number
  color?: string
  className?: string
}

export default function CEOSigil({ ceoId, size = 70, color = 'currentColor', className = '' }: CEOSigilProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 70 60"
      className={className}
      style={{ color }}
    >
      {SIGILS[ceoId]}
    </svg>
  )
}

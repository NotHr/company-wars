'use client'

interface HUDFrameProps {
  children: React.ReactNode
  color?: string
  label?: string
  className?: string
}

export default function HUDFrame({ children, color = '#00E5FF', label, className = '' }: HUDFrameProps) {
  return (
    <div className={`relative ${className}`}>
      {/* Corner brackets */}
      <div className="absolute top-0 left-0 w-5 h-5 border-t-2 border-l-2 pointer-events-none z-20" style={{ borderColor: color }} />
      <div className="absolute top-0 right-0 w-5 h-5 border-t-2 border-r-2 pointer-events-none z-20" style={{ borderColor: color }} />
      <div className="absolute bottom-0 left-0 w-5 h-5 border-b-2 border-l-2 pointer-events-none z-20" style={{ borderColor: color }} />
      <div className="absolute bottom-0 right-0 w-5 h-5 border-b-2 border-r-2 pointer-events-none z-20" style={{ borderColor: color }} />

      {/* Optional label badge */}
      {label && (
        <div className="absolute -top-3 left-6 z-20 pointer-events-none">
          <span
            className="font-display text-sm tracking-[0.2em] uppercase px-3 py-0.5"
            style={{ color, backgroundColor: '#000', border: `1px solid ${color}30` }}
          >
            {label}
          </span>
        </div>
      )}

      {children}
    </div>
  )
}

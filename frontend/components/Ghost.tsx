/** GhostKey's ghost, drawn in the brutalist style (theme-aware: panel fill, ink outline). Static: no animation. */
export default function Ghost({ size = 40, mood = 'idle', className = '' }: { size?: number; mood?: 'idle' | 'hi' | 'boo'; className?: string }) {
  return (
    <svg viewBox="0 0 64 72" width={size} height={size * 1.125} className={className} aria-hidden="true" style={{ overflow: 'visible' }}>
      <path
        d="M8 32 C8 15 19 4 32 4 C45 4 56 15 56 32 V60 Q52 67 48 60 Q44 53 40 60 Q36 67 32 60 Q28 53 24 60 Q20 67 16 60 Q12 53 8 60 Z"
        fill="var(--panel)"
        stroke="var(--ink)"
        strokeWidth="3.5"
        strokeLinejoin="round"
      />
      <ellipse cx="24" cy="27" rx="4" ry="5.5" fill="var(--ink)" />
      <ellipse cx="40" cy="27" rx="4" ry="5.5" fill="var(--ink)" />
      <circle cx="25.4" cy="25" r="1.4" fill="var(--panel)" />
      <circle cx="41.4" cy="25" r="1.4" fill="var(--panel)" />
      {mood === 'boo' ? (
        <ellipse cx="32" cy="40" rx="3.4" ry="4.2" fill="var(--ink)" />
      ) : mood === 'hi' ? (
        <path d="M26 37 Q32 45 38 37 Z" fill="var(--ink)" stroke="var(--ink)" strokeWidth="2" strokeLinejoin="round" />
      ) : (
        <path d="M27 38 Q32 42 37 38" fill="none" stroke="var(--ink)" strokeWidth="2.6" strokeLinecap="round" />
      )}
      <circle cx="17.5" cy="35" r="3" fill="var(--hi)" />
      <circle cx="46.5" cy="35" r="3" fill="var(--hi)" />
    </svg>
  );
}

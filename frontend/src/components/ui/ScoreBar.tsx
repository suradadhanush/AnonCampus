'use client'
interface Props { value: number; max?: number; color?: string; label?: string }
export function ScoreBar({ value, max = 1, color = '#00D4FF', label }: Props) {
  const pct = Math.round((value / max) * 100)
  return (
    <div>
      {label && <div className="flex justify-between text-xs text-slate-500 mb-1"><span>{label}</span><span>{pct}%</span></div>}
      <div className="score-bar">
        <div className="score-bar-fill" style={{ width: `${pct}%`, background: color }} />
      </div>
    </div>
  )
}

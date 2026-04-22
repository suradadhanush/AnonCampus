import { type ClassValue, clsx } from 'clsx'
export function cn(...inputs: ClassValue[]) { return clsx(inputs) }
export function fmtDate(d: string) {
  return new Date(d).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })
}
export function fmtRelative(d: string) {
  const diff = Date.now() - new Date(d).getTime()
  const h = Math.floor(diff / 3_600_000)
  if (h < 1) return `${Math.floor(diff / 60000)}m ago`
  if (h < 24) return `${h}h ago`
  return `${Math.floor(h / 24)}d ago`
}
export function severityColor(s: number) {
  if (s >= 0.8) return '#FF4444'
  if (s >= 0.6) return '#FFB800'
  return '#00FF88'
}
export function confidenceColor(c: number) {
  if (c >= 0.7) return '#00FF88'
  if (c >= 0.4) return '#FFB800'
  return '#FF4444'
}

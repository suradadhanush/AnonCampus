'use client'
import { cn } from '@/lib/utils'
const MAP: Record<string, string> = {
  new: 'badge-new', active: 'badge-active', dormant: 'badge-dormant',
  archived: 'badge-archived', resolved: 'badge-resolved', reopened: 'badge-escalated',
}
export function StatusBadge({ status }: { status: string }) {
  return <span className={cn('badge', MAP[status] ?? 'badge-dormant')}>{status.toUpperCase()}</span>
}

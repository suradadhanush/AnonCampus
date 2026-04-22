'use client'
import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import {
  AlertTriangle, Clock, ChevronRight, CheckCircle,
  XCircle, RotateCcw, Loader2,
} from 'lucide-react'
import { adminApi } from '@/lib/api'
import { Cluster } from '@/types'
import { StatusBadge } from '@/components/ui/StatusBadge'
import { ScoreBar } from '@/components/ui/ScoreBar'
import { fmtDate, severityColor, confidenceColor } from '@/lib/utils'
import toast from 'react-hot-toast'
import Link from 'next/link'

// Predefined rejection reasons — only these are accepted
const REJECTION_REASONS = [
  { value: 'insufficient_evidence', label: 'Insufficient evidence' },
  { value: 'out_of_scope', label: 'Out of scope' },
  { value: 'duplicate_issue', label: 'Duplicate issue' },
  { value: 'invalid_content', label: 'Invalid content' },
]

// Valid transitions from each state
const VALID_TRANSITIONS: Record<string, { value: string; label: string; icon: any; color: string }[]> = {
  new:      [{ value: 'active', label: 'Activate', icon: CheckCircle, color: '#00FF88' }],
  active:   [
    { value: 'resolved', label: 'Resolve', icon: CheckCircle, color: '#00FF88' },
    { value: 'dormant',  label: 'Mark dormant', icon: RotateCcw, color: '#94A3B8' },
  ],
  dormant:  [
    { value: 'active',   label: 'Reactivate', icon: RotateCcw, color: '#00D4FF' },
    { value: 'archived', label: 'Archive', icon: XCircle, color: '#475569' },
  ],
  resolved: [{ value: 'reopened', label: 'Reopen', icon: RotateCcw, color: '#FFB800' }],
  reopened: [{ value: 'active',   label: 'Activate', icon: CheckCircle, color: '#00FF88' }],
  archived: [],
}

function SlaCountdown({ deadline, slaStatus }: { deadline?: string; slaStatus?: string }) {
  if (!deadline) return <span className="text-slate-600 text-xs">—</span>
  const diff = new Date(deadline).getTime() - Date.now()
  const breached = diff < 0 || slaStatus === 'breached'
  const hours = Math.abs(Math.floor(diff / 3_600_000))
  const mins = Math.abs(Math.floor((diff % 3_600_000) / 60_000))
  const urgent = !breached && hours < 12

  return (
    <div className={`flex items-center gap-1.5 font-mono text-xs ${breached ? 'text-signal-red' : urgent ? 'text-signal-amber' : 'text-slate-400'}`}>
      <Clock size={10} className={breached ? 'animate-pulse' : ''} />
      {breached ? `${hours}h ${mins}m OVERDUE` : `${hours}h ${mins}m`}
    </div>
  )
}

function ActionCell({ cluster, onUpdate }: { cluster: Cluster; onUpdate: () => void }) {
  const [showRejectModal, setShowRejectModal] = useState(false)
  const [selectedReason, setSelectedReason] = useState(REJECTION_REASONS[0].value)
  const qc = useQueryClient()

  const updateMut = useMutation({
    mutationFn: ({ status, reason }: { status: string; reason?: string }) =>
      adminApi.updateStatus(cluster.id, status, reason),
    onMutate: async ({ status }) => {
      // Optimistic update
      await qc.cancelQueries({ queryKey: ['admin-clusters'] })
      const prev = qc.getQueryData(['admin-clusters'])
      qc.setQueryData(['admin-clusters'], (old: any) => {
        if (!old) return old
        return {
          ...old,
          items: old.items.map((c: Cluster) =>
            c.id === cluster.id ? { ...c, status } : c
          ),
        }
      })
      return { prev }
    },
    onError: (err: any, _, ctx: any) => {
      qc.setQueryData(['admin-clusters'], ctx?.prev)
      const detail = err?.response?.data?.detail
      if (typeof detail === 'object' && detail?.error === 'invalid_transition') {
        toast.error(`Invalid: ${detail.current} → ${detail.requested}`)
      } else {
        toast.error('Status update failed')
      }
    },
    onSuccess: (_, { status }) => {
      toast.success(`Cluster marked as ${status}`)
      onUpdate()
      setShowRejectModal(false)
    },
  })

  const transitions = VALID_TRANSITIONS[cluster.status] ?? []
  if (transitions.length === 0) return <span className="text-slate-600 text-xs">Terminal</span>

  return (
    <div className="flex items-center gap-2 flex-wrap">
      {transitions.map(({ value, label, icon: Icon, color }) => {
        const isReject = value === 'archived' || value === 'dormant'
        return (
          <button
            key={value}
            onClick={() => {
              if (isReject && value === 'archived') {
                setShowRejectModal(true)
              } else {
                updateMut.mutate({ status: value })
              }
            }}
            disabled={updateMut.isPending}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border transition-all disabled:opacity-40"
            style={{
              background: `${color}10`,
              borderColor: `${color}30`,
              color,
            }}
          >
            {updateMut.isPending ? <Loader2 size={10} className="animate-spin" /> : <Icon size={10} />}
            {label}
          </button>
        )
      })}

      {/* Reject/Archive modal */}
      {showRejectModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={() => setShowRejectModal(false)} />
          <div className="relative z-10 card p-6 w-full max-w-sm animate-slide-up">
            <h3 className="font-semibold mb-1">Archive cluster</h3>
            <p className="text-xs text-slate-500 mb-4">Select a reason (required)</p>

            <div className="space-y-2 mb-5">
              {REJECTION_REASONS.map(r => (
                <label key={r.value} className="flex items-center gap-2.5 cursor-pointer group">
                  <div className={`w-4 h-4 rounded-full border flex items-center justify-center transition-all ${
                    selectedReason === r.value
                      ? 'border-signal-cyan bg-signal-cyan/20'
                      : 'border-white/20 group-hover:border-white/40'
                  }`}>
                    {selectedReason === r.value && <div className="w-1.5 h-1.5 rounded-full bg-signal-cyan" />}
                  </div>
                  <input
                    type="radio" value={r.value} name="reason"
                    checked={selectedReason === r.value}
                    onChange={() => setSelectedReason(r.value)}
                    className="sr-only"
                  />
                  <span className="text-sm text-slate-300">{r.label}</span>
                </label>
              ))}
            </div>

            <div className="flex gap-2">
              <button onClick={() => setShowRejectModal(false)} className="btn-ghost flex-1 text-sm">Cancel</button>
              <button
                onClick={() => updateMut.mutate({ status: 'archived', reason: selectedReason })}
                disabled={updateMut.isPending}
                className="btn-danger flex-1 text-sm"
              >
                {updateMut.isPending ? 'Archiving…' : 'Archive'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export function AdminTable({ clusters, onUpdate }: { clusters: Cluster[]; onUpdate: () => void }) {
  return (
    <div className="card overflow-hidden">
      {/* Desktop table */}
      <div className="hidden lg:block overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-white/[0.06]">
              {['Issue cluster', 'Status', 'Confidence', 'Severity', 'SLA', 'Signals', 'Actions'].map(h => (
                <th key={h} className="text-left px-5 py-3 text-xs text-slate-500 font-medium whitespace-nowrap">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-white/[0.04]">
            {clusters.map(cluster => (
              <tr key={cluster.id} className="hover:bg-white/[0.02] transition-colors group">
                <td className="px-5 py-4 max-w-xs">
                  <div className="flex items-start gap-2">
                    {cluster.is_escalated && (
                      <AlertTriangle size={12} className="text-signal-amber mt-0.5 shrink-0" />
                    )}
                    <div>
                      <Link href={`/issues/${cluster.id}`} className="font-medium text-sm leading-snug hover:text-signal-cyan transition-colors line-clamp-2">
                        {cluster.title}
                      </Link>
                      <div className="flex items-center gap-2 mt-1">
                        <span className="font-mono text-xs px-1.5 py-0.5 rounded bg-carbon-700 text-slate-400">
                          {cluster.category}
                        </span>
                        {cluster.escalation_type === 'override' && (
                          <span className="text-xs text-signal-red font-mono">OVERRIDE</span>
                        )}
                      </div>
                    </div>
                  </div>
                </td>

                <td className="px-5 py-4 whitespace-nowrap">
                  <StatusBadge status={cluster.status} />
                </td>

                <td className="px-5 py-4 w-32">
                  <div className="font-mono text-sm font-bold mb-1.5" style={{ color: confidenceColor(cluster.confidence_score) }}>
                    {Math.round(cluster.confidence_score * 100)}%
                  </div>
                  <ScoreBar value={cluster.confidence_score} color={confidenceColor(cluster.confidence_score)} />
                </td>

                <td className="px-5 py-4 w-32">
                  <div className="font-mono text-sm mb-1.5" style={{ color: severityColor(cluster.severity) }}>
                    {(cluster.severity * 100).toFixed(0)}%
                  </div>
                  <ScoreBar value={cluster.severity} color={severityColor(cluster.severity)} />
                </td>

                <td className="px-5 py-4 whitespace-nowrap">
                  <SlaCountdown deadline={cluster.sla_deadline} slaStatus={(cluster as any).sla_status} />
                  {cluster.sla_deadline && (
                    <div className="text-xs text-slate-600 mt-0.5">{fmtDate(cluster.sla_deadline)}</div>
                  )}
                </td>

                <td className="px-5 py-4 whitespace-nowrap">
                  <div className="space-y-0.5 text-xs text-slate-400">
                    <div>{cluster.report_count} reports</div>
                    <div>{cluster.support_count} supports</div>
                    <div className={cluster.diversity_valid ? 'text-signal-green' : 'text-signal-amber'}>
                      {cluster.diversity_valid ? '✓ diversity valid' : '⚠ diversity pending'}
                    </div>
                  </div>
                </td>

                <td className="px-5 py-4">
                  <ActionCell cluster={cluster} onUpdate={onUpdate} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Mobile cards */}
      <div className="lg:hidden divide-y divide-white/[0.04]">
        {clusters.map(cluster => (
          <div key={cluster.id} className="p-4">
            <div className="flex items-start justify-between gap-2 mb-3">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1.5 flex-wrap">
                  <StatusBadge status={cluster.status} />
                  {cluster.is_escalated && <AlertTriangle size={12} className="text-signal-amber" />}
                </div>
                <Link href={`/issues/${cluster.id}`} className="font-medium text-sm leading-snug hover:text-signal-cyan">
                  {cluster.title}
                </Link>
              </div>
              <div className="font-mono text-lg font-bold shrink-0" style={{ color: confidenceColor(cluster.confidence_score) }}>
                {Math.round(cluster.confidence_score * 100)}%
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3 mb-3">
              <ScoreBar value={cluster.confidence_score} label="Confidence" color={confidenceColor(cluster.confidence_score)} />
              <ScoreBar value={cluster.severity} label="Severity" color={severityColor(cluster.severity)} />
            </div>

            <div className="flex items-center justify-between mb-3">
              <SlaCountdown deadline={cluster.sla_deadline} slaStatus={(cluster as any).sla_status} />
              <span className="text-xs text-slate-500">{cluster.report_count}R · {cluster.support_count}S</span>
            </div>

            <ActionCell cluster={cluster} onUpdate={onUpdate} />
          </div>
        ))}
      </div>
    </div>
  )
}

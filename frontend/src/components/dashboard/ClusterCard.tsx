'use client'
import { Cluster } from '@/types'
import { StatusBadge } from '@/components/ui/StatusBadge'
import { ScoreBar } from '@/components/ui/ScoreBar'
import { fmtRelative, severityColor, confidenceColor } from '@/lib/utils'
import { AlertTriangle, Users, MessageSquare, ThumbsUp, Clock } from 'lucide-react'
import Link from 'next/link'

export function ClusterCard({ cluster }: { cluster: Cluster }) {
  const slaOverdue = cluster.sla_deadline && new Date(cluster.sla_deadline) < new Date()

  return (
    <Link href={`/issues/${cluster.id}`}>
      <div className="card card-hover p-5 cursor-pointer animate-slide-up">
        {/* Header */}
        <div className="flex items-start justify-between gap-3 mb-4">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-2 flex-wrap">
              <StatusBadge status={cluster.status} />
              {cluster.is_escalated && (
                <span className="badge badge-escalated">
                  <AlertTriangle size={9} />
                  {cluster.escalation_type === 'override' ? 'OVERRIDE' : 'ESCALATED'}
                </span>
              )}
              {slaOverdue && (
                <span className="badge bg-signal-red/10 text-signal-red border border-signal-red/20">
                  <Clock size={9} /> SLA BREACH
                </span>
              )}
            </div>
            <h3 className="font-semibold text-sm leading-snug line-clamp-2">{cluster.title}</h3>
          </div>
          <div className="text-right shrink-0">
            <div className="font-mono text-lg font-bold" style={{ color: confidenceColor(cluster.confidence_score) }}>
              {Math.round(cluster.confidence_score * 100)}%
            </div>
            <div className="text-xs text-slate-500">confidence</div>
          </div>
        </div>

        {/* Scores */}
        <div className="space-y-2 mb-4">
          <ScoreBar value={cluster.confidence_score} label="Confidence" color={confidenceColor(cluster.confidence_score)} />
          <ScoreBar value={cluster.severity} label="Severity" color={severityColor(cluster.severity)} />
        </div>

        {/* Signals row */}
        <div className="flex items-center gap-4 text-xs text-slate-500 mb-3">
          <span className="flex items-center gap-1"><MessageSquare size={11}/>{cluster.report_count} reports</span>
          <span className="flex items-center gap-1"><ThumbsUp size={11}/>{cluster.support_count} supports</span>
          <span className="flex items-center gap-1"><Users size={11}/>{cluster.departments_involved.length} depts</span>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between text-xs text-slate-600">
          <span className="font-mono text-xs px-2 py-0.5 rounded bg-carbon-700">{cluster.category}</span>
          <span>{fmtRelative(cluster.last_activity_at)}</span>
        </div>

        {/* Diversity invalid warning */}
        {!cluster.diversity_valid && cluster.report_count > 0 && (
          <div className="mt-3 px-3 py-2 rounded-lg bg-signal-amber/5 border border-signal-amber/20 text-xs text-signal-amber">
            ⚠ Diversity check pending — confidence gated
          </div>
        )}
      </div>
    </Link>
  )
}

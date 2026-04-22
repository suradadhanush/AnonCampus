'use client'
import { useParams } from 'next/navigation'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { issuesApi, adminApi } from '@/lib/api'
import { useAuthStore } from '@/lib/store'
import { useRequireAuth } from '@/hooks/useAuth'
import { StatusBadge } from '@/components/ui/StatusBadge'
import { ScoreBar } from '@/components/ui/ScoreBar'
import { fmtDate, severityColor, confidenceColor } from '@/lib/utils'
import { AlertTriangle, Clock, Users, MessageSquare, ThumbsUp, ArrowLeft, CheckCircle } from 'lucide-react'
import Link from 'next/link'
import toast from 'react-hot-toast'
import { useState } from 'react'

export default function IssueDetailPage() {
  const { id } = useParams()
  const { user } = useRequireAuth()
  const qc = useQueryClient()
  const [feedbackSent, setFeedbackSent] = useState(false)

  const { data: clusterData } = useQuery({
    queryKey: ['issue-cluster', id],
    queryFn: () => issuesApi.getCluster(Number(id)).then(r => r.data),
    enabled: !!id && !!user,
  })

  const cluster = clusterData?.cluster

  const { data: adminDetail } = useQuery({
    queryKey: ['admin-cluster', id],
    queryFn: () => adminApi.clusterDetail(Number(id)).then(r => r.data),
    enabled: !!id && !!user && user.role !== 'student',
  })

  const supportMut = useMutation({
    mutationFn: () => issuesApi.support(Number(id)),
    onSuccess: () => { toast.success('Support recorded'); qc.invalidateQueries({ queryKey: ['issue-cluster', id] }) },
    onError: () => toast.error('Already supported'),
  })

  const feedbackMut = useMutation({
    mutationFn: (sentiment: string) => issuesApi.feedback(Number(id), { sentiment }),
    onSuccess: () => { toast.success('Feedback submitted'); setFeedbackSent(true) },
  })

  if (!cluster) return (
    <div className="min-h-screen bg-[#080A0F] flex items-center justify-center text-[#64748B]">
      Loading...
    </div>
  )

  const explanation = adminDetail?.explanation
  const timeline = adminDetail?.timeline ?? []
  const slaOverdue = cluster.sla_deadline && new Date(cluster.sla_deadline) < new Date()

  return (
    <div className="min-h-screen bg-[#080A0F] text-white">
      <div className="fixed inset-0 bg-grid-pattern bg-grid opacity-100 pointer-events-none" />
      <div className="relative z-10 max-w-4xl mx-auto px-6 py-8">

        <Link href="/dashboard" className="inline-flex items-center gap-1.5 text-[#64748B] hover:text-white text-sm mb-6 transition-colors">
          <ArrowLeft size={13} /> Back to feed
        </Link>

        <div className="card p-6 mb-5">
          <div className="flex items-start justify-between gap-4 mb-4">
            <div className="flex-1">
              <div className="flex flex-wrap gap-2 mb-3">
                <StatusBadge status={cluster.status} />
                {cluster.is_escalated && (
                  <span className="badge badge-escalated">
                    <AlertTriangle size={9} />{cluster.escalation_type?.toUpperCase()}
                  </span>
                )}
                {slaOverdue && (
                  <span className="badge bg-[#FF4444]/10 text-[#FF4444] border border-[#FF4444]/20">
                    <Clock size={9} /> SLA BREACHED
                  </span>
                )}
              </div>
              <h1 className="text-xl font-bold leading-snug">{cluster.title}</h1>
              {cluster.summary && <p className="text-[#94A3B8] text-sm mt-2 leading-relaxed">{cluster.summary}</p>}
            </div>
            <div className="text-right shrink-0">
              <div className="text-3xl font-bold font-mono" style={{ color: confidenceColor(cluster.confidence_score) }}>
                {Math.round(cluster.confidence_score * 100)}%
              </div>
              <div className="text-xs text-[#64748B]">confidence</div>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4 mb-4">
            <ScoreBar value={cluster.confidence_score} label="Confidence" color={confidenceColor(cluster.confidence_score)} />
            <ScoreBar value={cluster.severity} label="Severity" color={severityColor(cluster.severity)} />
            <ScoreBar value={cluster.diversity_score} label="Diversity" color="#B44FFF" />
            <ScoreBar value={cluster.scope} label="Scope" color="#00D4FF" />
          </div>

          <div className="flex items-center gap-6 text-sm text-[#94A3B8] mb-4">
            <span className="flex items-center gap-1.5"><MessageSquare size={13}/>{cluster.report_count} reports</span>
            <span className="flex items-center gap-1.5"><ThumbsUp size={13}/>{cluster.support_count} supports</span>
            <span className="flex items-center gap-1.5"><Users size={13}/>{cluster.departments_involved.length} departments</span>
          </div>

          <div className="flex flex-wrap gap-2 mb-4">
            {cluster.departments_involved.map((d: string) => (
              <span key={d} className="font-mono text-xs px-2 py-0.5 rounded bg-[#1C2333] text-[#94A3B8]">{d}</span>
            ))}
            {cluster.years_involved.map((y: number) => (
              <span key={y} className="font-mono text-xs px-2 py-0.5 rounded bg-[#1C2333] text-[#94A3B8]">Year {y}</span>
            ))}
          </div>

          {cluster.sla_deadline && (
            <div className={`text-xs flex items-center gap-1.5 ${slaOverdue ? 'text-[#FF4444]' : 'text-[#64748B]'}`}>
              <Clock size={11} />SLA: {fmtDate(cluster.sla_deadline)}{slaOverdue && ' — OVERDUE'}
            </div>
          )}

          {user?.role === 'student' && (
            <div className="mt-4">
              <button onClick={() => supportMut.mutate()} disabled={supportMut.isPending}
                className="btn-ghost flex items-center gap-1.5 text-sm">
                <ThumbsUp size={13} /> Support this issue
              </button>
            </div>
          )}
        </div>

        {explanation && (
          <div className="card p-5 mb-5">
            <p className="section-label mb-4">Why this score?</p>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
              {Object.entries(explanation.reason).map(([k, v]) => (
                <div key={k} className="bg-[#1C2333] rounded-lg p-3">
                  <div className="text-xs text-[#64748B] capitalize mb-1">{k.replace('_', ' ')}</div>
                  <div className="font-mono text-sm text-white">{String(v)}</div>
                </div>
              ))}
            </div>
            {!explanation.diversity_valid && (
              <div className="mt-3 px-3 py-2 rounded-lg bg-[#FFB800]/5 border border-[#FFB800]/20 text-xs text-[#FFB800]">
                Confidence is 0 — diversity requirements not met
              </div>
            )}
          </div>
        )}

        {timeline.length > 0 && (
          <div className="card p-5 mb-5">
            <p className="section-label mb-4">Event timeline</p>
            <div className="space-y-3">
              {timeline.map((e: any, i: number) => (
                <div key={i} className="flex items-start gap-3">
                  <div className="w-2 h-2 rounded-full bg-[#00D4FF] mt-1.5 shrink-0" />
                  <div>
                    <div className="font-mono text-xs text-[#00D4FF]">{e.event_type}</div>
                    <div className="text-xs text-[#64748B] mt-0.5">{fmtDate(e.created_at)}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {!feedbackSent && cluster.status === 'resolved' && user?.role === 'student' && (
          <div className="card p-5">
            <p className="section-label mb-3">Was this resolved?</p>
            <div className="flex gap-3">
              {['resolved', 'partial', 'unresolved'].map(s => (
                <button key={s} onClick={() => feedbackMut.mutate(s)}
                  className="btn-ghost text-sm capitalize flex-1">{s}</button>
              ))}
            </div>
          </div>
        )}

        {feedbackSent && (
          <div className="card p-4 flex items-center gap-2 text-[#00FF88] text-sm">
            <CheckCircle size={14} /> Feedback recorded. Thank you.
          </div>
        )}
      </div>
    </div>
  )
}

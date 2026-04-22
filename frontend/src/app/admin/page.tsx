'use client'
import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Shield, LogOut, AlertTriangle, Clock, BarChart3,
  ChevronUp, ChevronDown, Filter, RefreshCw, CheckCircle,
} from 'lucide-react'
import { useAuthStore } from '@/lib/store'
import { useRequireAuth, useAutoRefresh } from '@/hooks/useAuth'
import { adminApi } from '@/lib/api'
import { AdminTable } from '@/components/admin/AdminTable'
import { StatusBadge } from '@/components/ui/StatusBadge'
import { Cluster, AdminStats } from '@/types'
import toast from 'react-hot-toast'
import Link from 'next/link'

const STATUS_OPTIONS = ['', 'new', 'active', 'dormant', 'resolved', 'archived']
const SORT_OPTIONS = [
  { key: 'confidence', label: 'Confidence ↓' },
  { key: 'sla', label: 'SLA Urgency' },
  { key: 'severity', label: 'Severity ↓' },
]

function StatCard({ label, value, color, icon: Icon }: any) {
  return (
    <div className="card p-5">
      <div className="flex items-start justify-between">
        <div>
          <p className="section-label mb-2">{label}</p>
          <p className="text-3xl font-bold font-mono" style={{ color }}>{value}</p>
        </div>
        <div className="w-9 h-9 rounded-lg flex items-center justify-center" style={{ background: `${color}15` }}>
          <Icon size={16} style={{ color }} />
        </div>
      </div>
    </div>
  )
}

function SlaTimer({ deadline }: { deadline?: string }) {
  if (!deadline) return <span className="text-slate-600 text-xs">No SLA</span>
  const diff = new Date(deadline).getTime() - Date.now()
  const breached = diff < 0
  const hours = Math.abs(Math.floor(diff / 3_600_000))
  const mins = Math.abs(Math.floor((diff % 3_600_000) / 60_000))

  return (
    <span className={`font-mono text-xs flex items-center gap-1 ${breached ? 'text-signal-red' : hours < 12 ? 'text-signal-amber' : 'text-slate-400'}`}>
      <Clock size={10} />
      {breached ? '-' : ''}{hours}h {mins}m {breached ? 'OVERDUE' : ''}
    </span>
  )
}

export default function AdminDashboardPage() {
  useAutoRefresh()
  const { user, isAuthenticated } = useRequireAuth('admin')
  const { logout } = useAuthStore()
  const qc = useQueryClient()

  const [statusFilter, setStatusFilter] = useState('')
  const [sortBy, setSortBy] = useState('confidence')
  const [escalatedOnly, setEscalatedOnly] = useState(true)
  const [severityMin, setSeverityMin] = useState(0)
  const [page, setPage] = useState(1)

  const { data: stats } = useQuery<AdminStats>({
    queryKey: ['admin-stats'],
    queryFn: () => adminApi.stats().then(r => r.data),
    enabled: !!user,
    refetchInterval: 30_000,
  })

  const { data: clustersData, isLoading } = useQuery({
    queryKey: ['admin-clusters', statusFilter, escalatedOnly, page],
    queryFn: () => adminApi.listClusters({
      page,
      status_filter: statusFilter || undefined,
      escalated_only: escalatedOnly,
    }).then(r => r.data),
    enabled: !!user,
    refetchInterval: 15_000,
  })

  const clusters: Cluster[] = (clustersData?.items ?? [])
    .filter((c: Cluster) => c.severity >= severityMin)
    .sort((a: Cluster, b: Cluster) => {
      if (sortBy === 'confidence') return b.confidence_score - a.confidence_score
      if (sortBy === 'severity') return b.severity - a.severity
      if (sortBy === 'sla') {
        const aT = a.sla_deadline ? new Date(a.sla_deadline).getTime() : Infinity
        const bT = b.sla_deadline ? new Date(b.sla_deadline).getTime() : Infinity
        return aT - bT
      }
      return 0
    })

  if (!isAuthenticated) return null

  return (
    <div className="min-h-screen bg-carbon-950 text-white">
      <div className="fixed inset-0 bg-grid-pattern bg-grid opacity-100 pointer-events-none" />

      {/* Nav */}
      <nav className="relative z-10 sticky top-0 bg-carbon-950/95 backdrop-blur border-b border-white/[0.06] px-6 py-4">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Shield size={16} className="text-signal-cyan" />
            <span className="font-bold">AnonCampus</span>
            <span className="text-xs px-2 py-0.5 rounded bg-signal-amber/10 text-signal-amber border border-signal-amber/20">
              Admin
            </span>
          </div>
          <div className="flex items-center gap-3">
            <Link href="/dashboard" className="text-slate-500 hover:text-white text-sm transition-colors">
              Student view
            </Link>
            <span className="text-slate-600">·</span>
            <span className="text-xs text-slate-500">{user?.email}</span>
            <button onClick={logout} className="text-slate-500 hover:text-signal-red transition-colors">
              <LogOut size={15} />
            </button>
          </div>
        </div>
      </nav>

      <div className="relative z-10 max-w-7xl mx-auto px-6 py-8">
        {/* Stats row */}
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-8">
          <StatCard label="Total Clusters" value={stats?.total_clusters ?? '—'} color="#00D4FF" icon={BarChart3} />
          <StatCard label="Escalated" value={stats?.escalated ?? '—'} color="#FFB800" icon={AlertTriangle} />
          <StatCard label="Active" value={stats?.active ?? '—'} color="#00FF88" icon={RefreshCw} />
          <StatCard label="Resolved" value={stats?.resolved ?? '—'} color="#B44FFF" icon={CheckCircle} />
          <StatCard label="SLA Breached" value={stats?.overdue_sla ?? '—'} color="#FF4444" icon={Clock} />
        </div>

        {/* Filters */}
        <div className="card p-4 mb-6">
          <div className="flex flex-wrap items-center gap-3">
            <span className="section-label">Filters</span>

            <button
              onClick={() => setEscalatedOnly(!escalatedOnly)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-all ${
                escalatedOnly
                  ? 'bg-signal-amber/10 text-signal-amber border-signal-amber/30'
                  : 'text-slate-500 border-white/10 hover:border-white/20'
              }`}
            >
              <AlertTriangle size={10} className="inline mr-1" />
              Escalated only
            </button>

            <select
              value={statusFilter}
              onChange={e => { setStatusFilter(e.target.value); setPage(1) }}
              className="input py-1.5 text-xs w-36"
            >
              {STATUS_OPTIONS.map(s => (
                <option key={s} value={s}>{s ? s.charAt(0).toUpperCase() + s.slice(1) : 'All statuses'}</option>
              ))}
            </select>

            <select
              value={severityMin}
              onChange={e => setSeverityMin(Number(e.target.value))}
              className="input py-1.5 text-xs w-40"
            >
              <option value={0}>Any severity</option>
              <option value={0.5}>≥ 0.5 Medium</option>
              <option value={0.7}>≥ 0.7 High</option>
              <option value={0.85}>≥ 0.85 Critical</option>
            </select>

            <select
              value={sortBy}
              onChange={e => setSortBy(e.target.value)}
              className="input py-1.5 text-xs w-44"
            >
              {SORT_OPTIONS.map(s => (
                <option key={s.key} value={s.key}>{s.label}</option>
              ))}
            </select>

            <button
              onClick={() => qc.invalidateQueries({ queryKey: ['admin-clusters'] })}
              className="ml-auto text-slate-500 hover:text-white transition-colors"
            >
              <RefreshCw size={14} />
            </button>
          </div>
        </div>

        {/* Table */}
        {isLoading ? (
          <div className="card p-8 text-center text-slate-500">
            <RefreshCw size={20} className="mx-auto mb-2 animate-spin" />
            Loading clusters…
          </div>
        ) : clusters.length === 0 ? (
          <div className="card p-12 text-center">
            <CheckCircle size={28} className="mx-auto mb-3 text-signal-green opacity-50" />
            <p className="font-medium text-slate-400">No clusters match current filters</p>
          </div>
        ) : (
          <AdminTable clusters={clusters} onUpdate={() => qc.invalidateQueries({ queryKey: ['admin-clusters', 'admin-stats'] })} />
        )}

        {/* Pagination */}
        {clustersData && clustersData.total > 20 && (
          <div className="flex items-center justify-between mt-4 text-sm text-slate-500">
            <span>Page {page} · {clustersData.total} total</span>
            <div className="flex gap-2">
              <button
                onClick={() => setPage(p => Math.max(1, p - 1))}
                disabled={page === 1}
                className="btn-ghost py-1.5 px-3 text-xs disabled:opacity-30"
              >
                Previous
              </button>
              <button
                onClick={() => setPage(p => p + 1)}
                disabled={!clustersData.has_next}
                className="btn-ghost py-1.5 px-3 text-xs disabled:opacity-30"
              >
                Next
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

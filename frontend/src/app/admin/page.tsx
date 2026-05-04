'use client'
import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Shield, LogOut, AlertTriangle, Clock, BarChart3,
  RefreshCw, CheckCircle, TrendingUp, Users, Zap, FileText,
} from 'lucide-react'
import { useAuthStore } from '@/lib/store'
import { useRequireAuth, useAutoRefresh } from '@/hooks/useAuth'
import { adminApi } from '@/lib/api'
import { AdminTable } from '@/components/admin/AdminTable'
import { Cluster, AdminStats } from '@/types'
import Link from 'next/link'

const STATUS_OPTIONS = ['', 'new', 'active', 'dormant', 'resolved', 'archived']
const SORT_OPTIONS = [
  { key: 'confidence', label: 'Confidence ↓' },
  { key: 'sla', label: 'SLA Urgency' },
  { key: 'severity', label: 'Severity ↓' },
]

function MetricCard({ label, value, color, icon: Icon, sub }: any) {
  return (
    <div className="card p-5">
      <div className="flex items-start justify-between mb-3">
        <p className="text-xs font-mono text-[#64748B] uppercase tracking-widest">{label}</p>
        <div className="w-8 h-8 rounded-lg flex items-center justify-center"
          style={{ background: `${color}15` }}>
          <Icon size={14} style={{ color }} />
        </div>
      </div>
      <p className="text-3xl font-bold font-mono" style={{ color }}>{value ?? '—'}</p>
      {sub && <p className="text-xs text-[#64748B] mt-1">{sub}</p>}
    </div>
  )
}

export default function AdminDashboardPage() {
  useAutoRefresh()
  const { user, isAuthenticated } = useRequireAuth('admin')
  const { logout } = useAuthStore()
  const qc = useQueryClient()

  const [statusFilter, setStatusFilter] = useState('')
  const [sortBy, setSortBy] = useState('confidence')
  const [escalatedOnly, setEscalatedOnly] = useState(false)
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
      page, page_size: 20,
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

  const slaBreachPct = stats?.total_clusters
    ? Math.round(((stats.overdue_sla || 0) / stats.total_clusters) * 100)
    : 0

  return (
    <div className="min-h-screen bg-[#080A0F] text-white">
      <div className="fixed inset-0 bg-grid-pattern bg-grid opacity-100 pointer-events-none" />

      {/* Nav */}
      <nav className="relative z-10 sticky top-0 bg-[#080A0F]/95 backdrop-blur border-b border-white/[0.06] px-6 py-4">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Shield size={16} className="text-[#00D4FF]" />
            <span className="font-bold">AnonCampus</span>
            <span className="text-xs px-2 py-0.5 rounded bg-[#FFB800]/10 text-[#FFB800] border border-[#FFB800]/20">
              Admin
            </span>
          </div>
          <div className="flex items-center gap-3">
            <Link href="/dashboard" className="text-[#64748B] hover:text-white text-sm transition-colors">
              Student view
            </Link>
            <span className="text-[#475569]">·</span>
            <span className="text-xs text-[#64748B] hidden sm:block">{user?.email}</span>
            <button onClick={logout} className="text-[#64748B] hover:text-[#FF4444] transition-colors">
              <LogOut size={15} />
            </button>
          </div>
        </div>
      </nav>

      <div className="relative z-10 max-w-7xl mx-auto px-6 py-8">

        {/* Header */}
        <div className="mb-8">
          <h1 className="text-2xl font-bold">Grievance Intelligence Dashboard</h1>
          <p className="text-[#64748B] text-sm mt-1">
            NSRIT · Real-time signal processing · {new Date().toLocaleDateString('en-IN', { weekday: 'long', day: 'numeric', month: 'long' })}
          </p>
        </div>

        {/* Metrics */}
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4 mb-8">
          <MetricCard label="Total Clusters" value={stats?.total_clusters} color="#00D4FF" icon={BarChart3} sub="All time" />
          <MetricCard label="Active" value={stats?.active} color="#00FF88" icon={TrendingUp} sub="In progress" />
          <MetricCard label="Escalated" value={stats?.escalated} color="#FFB800" icon={AlertTriangle} sub="Needs action" />
          <MetricCard label="Resolved" value={stats?.resolved} color="#B44FFF" icon={CheckCircle} sub="Closed" />
          <MetricCard label="SLA Breached" value={stats?.overdue_sla} color="#FF4444" icon={Clock} sub={`${slaBreachPct}% of total`} />
          <MetricCard label="Issues" value={clustersData?.total} color="#64748B" icon={FileText} sub="Across clusters" />
        </div>

        {/* Filters */}
        <div className="card p-4 mb-6">
          <div className="flex flex-wrap items-center gap-3">
            <span className="text-xs font-mono text-[#64748B] uppercase tracking-widest">Filters</span>

            <button
              onClick={() => setEscalatedOnly(!escalatedOnly)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-all ${
                escalatedOnly
                  ? 'bg-[#FFB800]/10 text-[#FFB800] border-[#FFB800]/30'
                  : 'text-[#64748B] border-white/10 hover:border-white/20'
              }`}
            >
              <AlertTriangle size={10} className="inline mr-1" />
              Escalated only
            </button>

            <select value={statusFilter} onChange={e => { setStatusFilter(e.target.value); setPage(1) }}
              className="input py-1.5 text-xs w-36">
              {STATUS_OPTIONS.map(s => (
                <option key={s} value={s}>{s ? s.charAt(0).toUpperCase() + s.slice(1) : 'All statuses'}</option>
              ))}
            </select>

            <select value={severityMin} onChange={e => setSeverityMin(Number(e.target.value))}
              className="input py-1.5 text-xs w-40">
              <option value={0}>Any severity</option>
              <option value={0.5}>≥ 0.5 Medium</option>
              <option value={0.7}>≥ 0.7 High</option>
              <option value={0.85}>≥ 0.85 Critical</option>
            </select>

            <select value={sortBy} onChange={e => setSortBy(e.target.value)}
              className="input py-1.5 text-xs w-44">
              {SORT_OPTIONS.map(s => <option key={s.key} value={s.key}>{s.label}</option>)}
            </select>

            <button onClick={() => qc.invalidateQueries({ queryKey: ['admin-clusters', 'admin-stats'] })}
              className="ml-auto text-[#64748B] hover:text-white transition-colors">
              <RefreshCw size={14} />
            </button>
          </div>
        </div>

        {/* Table */}
        {isLoading ? (
          <div className="card p-8 text-center text-[#64748B]">
            <RefreshCw size={20} className="mx-auto mb-2 animate-spin" />
            Loading clusters…
          </div>
        ) : clusters.length === 0 ? (
          <div className="card p-12 text-center">
            <CheckCircle size={28} className="mx-auto mb-3 text-[#00FF88] opacity-50" />
            <p className="font-medium text-[#94A3B8]">No clusters match current filters</p>
            <button onClick={() => { setStatusFilter(''); setEscalatedOnly(false); setSeverityMin(0) }}
              className="mt-3 text-xs text-[#00D4FF] hover:underline">Clear filters</button>
          </div>
        ) : (
          <AdminTable
            clusters={clusters}
            onUpdate={() => qc.invalidateQueries({ queryKey: ['admin-clusters', 'admin-stats'] })}
          />
        )}

        {/* Pagination */}
        {clustersData && clustersData.total > 20 && (
          <div className="flex items-center justify-between mt-4 text-sm text-[#64748B]">
            <span>Page {page} · {clustersData.total} total</span>
            <div className="flex gap-2">
              <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}
                className="btn-ghost py-1.5 px-3 text-xs disabled:opacity-30">Previous</button>
              <button onClick={() => setPage(p => p + 1)} disabled={!clustersData.has_next}
                className="btn-ghost py-1.5 px-3 text-xs disabled:opacity-30">Next</button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

'use client'
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Shield, Plus, LogOut, TrendingUp, Zap, Clock, Filter } from 'lucide-react'
import { useAuthStore } from '@/lib/store'
import { useRequireAuth, useAutoRefresh } from '@/hooks/useAuth'
import { issuesApi } from '@/lib/api'
import { ClusterCard } from '@/components/dashboard/ClusterCard'
import { SubmitModal } from '@/components/dashboard/SubmitModal'
import { Cluster } from '@/types'

const FEEDS = [
  { key: undefined,    label: 'All',      icon: TrendingUp },
  { key: 'new',        label: 'New',      icon: Zap },
  { key: 'active',     label: 'Active',   icon: TrendingUp },
  { key: 'trending',   label: 'Trending', icon: TrendingUp },
]

export default function DashboardPage() {
  useAutoRefresh()
  const { user } = useRequireAuth()
  const { logout } = useAuthStore()
  const [feed, setFeed] = useState<string | undefined>(undefined)
  const [showModal, setShowModal] = useState(false)

  const { data, isLoading } = useQuery({
    queryKey: ['clusters', feed],
    queryFn: () => issuesApi.listClusters({ feed_type: feed, page_size: 30 }).then(r => r.data),
    enabled: !!user,
  })

  const clusters: Cluster[] = data?.items ?? []

  return (
    <div className="min-h-screen bg-carbon-950 text-white">
      <div className="fixed inset-0 bg-grid-pattern bg-grid opacity-100 pointer-events-none" />

      {/* Nav */}
      <nav className="relative z-10 sticky top-0 bg-carbon-950/90 backdrop-blur border-b border-white/[0.06] px-6 py-4">
        <div className="max-w-5xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <Shield size={16} className="text-signal-cyan" />
            <span className="font-bold">AnonCampus</span>
          </div>
          <div className="flex items-center gap-3">
            <div className="text-xs text-slate-500 hidden sm:block">
              {user?.department} · Year {user?.academic_year}
            </div>
            <div className="text-xs font-mono px-2 py-1 rounded bg-carbon-700 text-slate-400">
              Trust: {user?.trust_score?.toFixed(2)}
            </div>
            <button onClick={logout} className="text-slate-500 hover:text-signal-red transition-colors">
              <LogOut size={15} />
            </button>
          </div>
        </div>
      </nav>

      <div className="relative z-10 max-w-5xl mx-auto px-6 py-8">
        {/* Hero row */}
        <div className="flex items-start justify-between mb-8">
          <div>
            <h1 className="text-2xl font-bold">Issue feed</h1>
            <p className="text-slate-500 text-sm mt-1">
              {data?.total ?? 0} active clusters · ranked by visibility score
            </p>
          </div>
          <button onClick={() => setShowModal(true)} className="btn-primary flex items-center gap-2">
            <Plus size={14} /> Submit issue
          </button>
        </div>

        {/* Feed tabs */}
        <div className="flex gap-2 mb-6">
          {FEEDS.map(({ key, label }) => (
            <button
              key={label}
              onClick={() => setFeed(key)}
              className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-all ${
                feed === key
                  ? 'bg-signal-cyan/10 text-signal-cyan border border-signal-cyan/30'
                  : 'text-slate-500 hover:text-white border border-transparent'
              }`}
            >
              {label}
            </button>
          ))}
        </div>

        {/* Grid */}
        {isLoading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {[...Array(6)].map((_, i) => (
              <div key={i} className="card p-5 h-48 animate-pulse">
                <div className="h-4 bg-carbon-700 rounded w-3/4 mb-3" />
                <div className="h-3 bg-carbon-700 rounded w-1/2 mb-2" />
                <div className="h-1.5 bg-carbon-700 rounded mb-1" />
                <div className="h-1.5 bg-carbon-700 rounded w-4/5" />
              </div>
            ))}
          </div>
        ) : clusters.length === 0 ? (
          <div className="text-center py-20 text-slate-600">
            <Shield size={32} className="mx-auto mb-3 opacity-30" />
            <p className="font-medium">No issues yet</p>
            <p className="text-sm mt-1">Be the first to submit one anonymously</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {clusters.map(c => <ClusterCard key={c.id} cluster={c} />)}
          </div>
        )}
      </div>

      {showModal && <SubmitModal onClose={() => setShowModal(false)} />}
    </div>
  )
}

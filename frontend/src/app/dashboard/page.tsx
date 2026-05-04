'use client'
import { useState, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Shield, Plus, LogOut, TrendingUp, Zap, Clock, BarChart3, Settings } from 'lucide-react'
import { useAuthStore } from '@/lib/store'
import { useRequireAuth, useAutoRefresh } from '@/hooks/useAuth'
import { issuesApi } from '@/lib/api'
import { ClusterCard } from '@/components/dashboard/ClusterCard'
import { SubmitModal } from '@/components/dashboard/SubmitModal'
import { Cluster } from '@/types'
import Link from 'next/link'
import { useRouter } from 'next/navigation'

const FEEDS = [
  { key: undefined,  label: 'All' },
  { key: 'new',      label: 'New' },
  { key: 'active',   label: 'Active' },
  { key: 'trending', label: 'Trending' },
]

export default function DashboardPage() {
  useAutoRefresh()
  const { user } = useRequireAuth()
  const { logout } = useAuthStore()
  const router = useRouter()
  const [feed, setFeed] = useState<string | undefined>(undefined)
  const [showModal, setShowModal] = useState(false)

  // Redirect admins to admin dashboard
  useEffect(() => {
    if (user?.role === 'admin' || user?.role === 'super_admin') {
      router.push('/admin')
    }
  }, [user, router])

  const { data, isLoading, refetch } = useQuery({
    queryKey: ['clusters', feed],
    queryFn: () => issuesApi.listClusters({ feed_type: feed, page_size: 30 }).then(r => r.data),
    enabled: !!user,
  })

  const clusters: Cluster[] = data?.items ?? []

  return (
    <div className="min-h-screen bg-[#080A0F] text-white">
      <div className="fixed inset-0 bg-grid-pattern bg-grid opacity-100 pointer-events-none" />

      {/* Nav */}
      <nav className="relative z-10 sticky top-0 bg-[#080A0F]/90 backdrop-blur border-b border-white/[0.06] px-6 py-4">
        <div className="max-w-5xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <Shield size={16} className="text-[#00D4FF]" />
            <span className="font-bold">AnonCampus</span>
          </div>
          <div className="flex items-center gap-3">
            <div className="text-xs text-[#64748B] hidden sm:block">
              {user?.department} · Year {user?.academic_year}
            </div>
            <div className="text-xs font-mono px-2 py-1 rounded bg-[#1C2333] text-[#94A3B8]">
              Trust: {user?.trust_score?.toFixed(2)}
            </div>
            {(user?.role === 'admin' || user?.role === 'super_admin') && (
              <Link href="/admin" className="text-[#FFB800] hover:text-[#FFB800]/80 transition-colors">
                <Settings size={15} />
              </Link>
            )}
            <button onClick={logout} className="text-[#64748B] hover:text-[#FF4444] transition-colors">
              <LogOut size={15} />
            </button>
          </div>
        </div>
      </nav>

      <div className="relative z-10 max-w-5xl mx-auto px-6 py-8">
        {/* Header */}
        <div className="flex items-start justify-between mb-8">
          <div>
            <h1 className="text-2xl font-bold">Issue Feed</h1>
            <p className="text-[#64748B] text-sm mt-1">
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
            <button key={label} onClick={() => setFeed(key)}
              className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-all ${
                feed === key
                  ? 'bg-[#00D4FF]/10 text-[#00D4FF] border border-[#00D4FF]/30'
                  : 'text-[#64748B] hover:text-white border border-transparent'
              }`}>
              {label}
            </button>
          ))}
        </div>

        {/* Grid */}
        {isLoading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {[...Array(6)].map((_, i) => (
              <div key={i} className="card p-5 h-48 animate-pulse">
                <div className="h-4 bg-[#1C2333] rounded w-3/4 mb-3" />
                <div className="h-3 bg-[#1C2333] rounded w-1/2 mb-4" />
                <div className="h-1.5 bg-[#1C2333] rounded mb-2" />
                <div className="h-1.5 bg-[#1C2333] rounded w-4/5" />
              </div>
            ))}
          </div>
        ) : clusters.length === 0 ? (
          <div className="text-center py-20 text-[#475569]">
            <Shield size={32} className="mx-auto mb-3 opacity-30" />
            <p className="font-medium text-[#64748B]">No issues yet</p>
            <p className="text-sm mt-1">Be the first to submit one anonymously</p>
            <button onClick={() => setShowModal(true)}
              className="mt-4 btn-primary text-sm px-4 py-2">
              Submit first issue
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {clusters.map(c => <ClusterCard key={c.id} cluster={c} />)}
          </div>
        )}
      </div>

      {showModal && (
        <SubmitModal onClose={() => { setShowModal(false); refetch() }} />
      )}
    </div>
  )
}

'use client'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { Shield, Signal, Users, ArrowRight, Zap, Lock, BarChart3, ChevronRight } from 'lucide-react'
import { useState } from 'react'
import { authApi } from '@/lib/api'
import { useAuthStore } from '@/lib/store'
import toast from 'react-hot-toast'

const FEATURES = [
  { icon: Lock, label: 'Fully Anonymous', desc: 'No names, no IDs exposed. Ever.' },
  { icon: Signal, label: 'Signal Processing', desc: 'Raw complaints become structured evidence.' },
  { icon: Users, label: 'Diversity-Gated', desc: 'Cross-department validation prevents abuse.' },
  { icon: BarChart3, label: 'Confidence Scoring', desc: 'Every issue ranked by mathematical certainty.' },
]

const STEPS = [
  { n: '01', title: 'Student submits', desc: 'Anonymous, moderated, categorised automatically.' },
  { n: '02', title: 'System clusters', desc: 'Similar issues merge. Signals accumulate.' },
  { n: '03', title: 'Governance validates', desc: 'Diversity + threshold rules gate escalation.' },
  { n: '04', title: 'Admin acts', desc: 'Ranked, timed, explainable decisions.' },
]

export default function LandingPage() {
  const [showDemo, setShowDemo] = useState(false)
  const [loading, setLoading] = useState<string | null>(null)
  const router = useRouter()
  const { setAuth } = useAuthStore()

  const loginAs = async (role: 'student' | 'admin') => {
    setLoading(role)
    const credentials = {
      student: { email: 'student@nsrit.edu.in', password: 'Admin1234' },
      admin:   { email: 'admin@nsrit.edu.in',   password: 'Admin1234' },
    }
    try {
      const res = await authApi.login(credentials[role])
      const { access_token, refresh_token } = res.data
      const meRes = await authApi.me()
      setAuth(meRes.data, access_token, refresh_token)
      toast.success(`Logged in as demo ${role}`)
      router.push(role === 'admin' ? '/admin' : '/dashboard')
    } catch {
      toast.error('Demo login failed — please try again')
    } finally {
      setLoading(null)
    }
  }

  return (
    <div className="min-h-screen bg-[#080A0F] text-white overflow-hidden">
      <div className="fixed inset-0 bg-grid-pattern bg-grid opacity-100 pointer-events-none" />
      <div className="fixed inset-0 bg-glow-cyan pointer-events-none" />

      {/* Nav */}
      <nav className="relative z-10 flex items-center justify-between px-8 py-5 border-b border-white/[0.06]">
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded-lg bg-[#00D4FF] flex items-center justify-center">
            <Shield size={14} className="text-[#080A0F]" />
          </div>
          <span className="font-bold text-lg tracking-tight">AnonCampus</span>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => setShowDemo(true)}
            className="px-4 py-2 rounded-lg bg-[#00FF88]/10 border border-[#00FF88]/30 text-[#00FF88] text-sm font-medium hover:bg-[#00FF88]/20 transition-all"
          >
            ⚡ Try Demo
          </button>
          <Link href="/auth/login" className="btn-ghost text-sm py-2 px-4">Sign in</Link>
          <Link href="/auth/register" className="btn-primary text-sm py-2 px-4">Get started</Link>
        </div>
      </nav>

      {/* Hero */}
      <section className="relative z-10 max-w-5xl mx-auto px-8 pt-24 pb-20 text-center">
        <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-[#00D4FF]/10 border border-[#00D4FF]/20 text-[#00D4FF] text-xs font-mono mb-8">
          <span className="w-1.5 h-1.5 rounded-full bg-[#00D4FF] animate-pulse" />
          Signal processing platform for institutions
        </div>
        <h1 className="text-5xl md:text-6xl font-bold leading-[1.1] tracking-tight mb-6">
          Turn anonymous complaints<br />
          into <span className="text-gradient-cyan">actionable intelligence</span>
        </h1>
        <p className="text-[#94A3B8] text-xl max-w-2xl mx-auto mb-10 leading-relaxed">
          AnonCampus converts raw student grievances into structured, diversity-validated,
          scored signals — so institutions act on evidence, not noise.
        </p>
        <div className="flex items-center justify-center gap-4 flex-wrap">
          <button
            onClick={() => setShowDemo(true)}
            className="flex items-center gap-2 text-base py-3 px-6 rounded-lg bg-[#00FF88] text-[#080A0F] font-bold hover:bg-[#00FF88]/90 transition-all"
          >
            ⚡ Try Demo — No signup needed
          </button>
          <Link href="/auth/register" className="btn-ghost flex items-center gap-2 text-base py-3 px-6">
            Create account <ChevronRight size={16} />
          </Link>
        </div>

        {/* Stats */}
        <div className="mt-20 grid grid-cols-3 gap-6 max-w-lg mx-auto">
          {[['≥80%', 'Signal accuracy'], ['72h', 'SLA on escalations'], ['0', 'Identity exposed']].map(([v, l]) => (
            <div key={l} className="text-center">
              <div className="text-2xl font-bold text-[#00D4FF]">{v}</div>
              <div className="text-xs text-[#64748B] mt-1">{l}</div>
            </div>
          ))}
        </div>
      </section>

      {/* Features */}
      <section className="relative z-10 max-w-5xl mx-auto px-8 py-20">
        <p className="text-xs font-mono text-[#64748B] uppercase tracking-widest text-center mb-12">Core capabilities</p>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {FEATURES.map(({ icon: Icon, label, desc }) => (
            <div key={label} className="card p-5">
              <div className="w-9 h-9 rounded-lg bg-[#00D4FF]/10 flex items-center justify-center mb-4">
                <Icon size={16} className="text-[#00D4FF]" />
              </div>
              <div className="font-semibold text-sm mb-1">{label}</div>
              <div className="text-xs text-[#64748B] leading-relaxed">{desc}</div>
            </div>
          ))}
        </div>
      </section>

      {/* Pipeline */}
      <section className="relative z-10 max-w-4xl mx-auto px-8 py-20">
        <p className="text-xs font-mono text-[#64748B] uppercase tracking-widest text-center mb-3">How it works</p>
        <h2 className="text-3xl font-bold text-center mb-14">Four steps from complaint to decision</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
          {STEPS.map(({ n, title, desc }) => (
            <div key={n} className="card p-5">
              <div className="font-mono text-[#00D4FF]/60 text-xs mb-3">{n}</div>
              <div className="font-semibold text-sm mb-2">{title}</div>
              <div className="text-xs text-[#64748B] leading-relaxed">{desc}</div>
            </div>
          ))}
        </div>
      </section>

      {/* CTA */}
      <section className="relative z-10 max-w-2xl mx-auto px-8 py-20 text-center">
        <div className="card p-10 border-[#00D4FF]/20">
          <Zap size={28} className="text-[#00D4FF] mx-auto mb-4" />
          <h2 className="text-2xl font-bold mb-3">Ready to transform campus feedback?</h2>
          <p className="text-[#64748B] text-sm mb-6">Use your college email to get started instantly.</p>
          <button
            onClick={() => setShowDemo(true)}
            className="btn-primary inline-flex items-center gap-2"
          >
            ⚡ Try the live demo <ArrowRight size={14} />
          </button>
        </div>
      </section>

      <footer className="relative z-10 border-t border-white/[0.06] px-8 py-6 text-center text-xs text-[#475569]">
        AnonCampus — Anonymous Grievance Intelligence Platform
      </footer>

      {/* Demo Modal */}
      {showDemo && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={() => setShowDemo(false)} />
          <div className="relative z-10 w-full max-w-sm card p-7">
            <div className="text-center mb-6">
              <div className="w-12 h-12 rounded-xl bg-[#00FF88]/10 border border-[#00FF88]/20 flex items-center justify-center mx-auto mb-3">
                <Zap size={20} className="text-[#00FF88]" />
              </div>
              <h2 className="text-lg font-bold">Try Demo</h2>
              <p className="text-sm text-[#64748B] mt-1">Choose your role — no signup needed</p>
            </div>

            <div className="space-y-3">
              <button
                onClick={() => loginAs('student')}
                disabled={!!loading}
                className="w-full p-4 rounded-xl border border-[#00D4FF]/20 bg-[#00D4FF]/5 hover:bg-[#00D4FF]/10 transition-all text-left"
              >
                <div className="flex items-center justify-between">
                  <div>
                    <div className="font-semibold text-sm">🎓 Student View</div>
                    <div className="text-xs text-[#64748B] mt-0.5">Submit grievances, view feed, support issues</div>
                  </div>
                  {loading === 'student'
                    ? <div className="w-4 h-4 border-2 border-[#00D4FF] border-t-transparent rounded-full animate-spin" />
                    : <ArrowRight size={14} className="text-[#64748B]" />
                  }
                </div>
              </button>

              <button
                onClick={() => loginAs('admin')}
                disabled={!!loading}
                className="w-full p-4 rounded-xl border border-[#FFB800]/20 bg-[#FFB800]/5 hover:bg-[#FFB800]/10 transition-all text-left"
              >
                <div className="flex items-center justify-between">
                  <div>
                    <div className="font-semibold text-sm">⚡ Admin View</div>
                    <div className="text-xs text-[#64748B] mt-0.5">See escalated issues, manage status, view scores</div>
                  </div>
                  {loading === 'admin'
                    ? <div className="w-4 h-4 border-2 border-[#FFB800] border-t-transparent rounded-full animate-spin" />
                    : <ArrowRight size={14} className="text-[#64748B]" />
                  }
                </div>
              </button>
            </div>

            <p className="text-xs text-[#475569] text-center mt-4">
              Demo data is preloaded. No real data is affected.
            </p>
          </div>
        </div>
      )}
    </div>
  )
}

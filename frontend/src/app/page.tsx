'use client'
import Link from 'next/link'
import { Shield, Signal, Users, ArrowRight, Zap, Lock, BarChart3, ChevronRight } from 'lucide-react'
import { motion } from 'framer-motion'

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
  return (
    <div className="min-h-screen bg-carbon-950 text-white overflow-hidden">
      {/* Grid background */}
      <div className="fixed inset-0 bg-grid-pattern bg-grid opacity-100 pointer-events-none" />
      <div className="fixed inset-0 bg-glow-cyan pointer-events-none" />

      {/* Nav */}
      <nav className="relative z-10 flex items-center justify-between px-8 py-5 border-b border-white/[0.06]">
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded-lg bg-signal-cyan flex items-center justify-center">
            <Shield size={14} className="text-carbon-950" />
          </div>
          <span className="font-bold text-lg tracking-tight">AnonCampus</span>
        </div>
        <div className="flex items-center gap-3">
          <Link href="/auth/login" className="btn-ghost text-sm py-2 px-4">Sign in</Link>
          <Link href="/auth/register" className="btn-primary text-sm py-2 px-4">Get started</Link>
        </div>
      </nav>

      {/* Hero */}
      <section className="relative z-10 max-w-5xl mx-auto px-8 pt-24 pb-20 text-center">
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6 }}>
          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-signal-cyan/10 border border-signal-cyan/20 text-signal-cyan text-xs font-mono mb-8">
            <span className="w-1.5 h-1.5 rounded-full bg-signal-cyan animate-pulse-slow" />
            Signal processing platform for institutions
          </div>
          <h1 className="text-6xl font-bold leading-[1.1] tracking-tight mb-6">
            Turn anonymous complaints<br />
            into <span className="text-gradient-cyan">actionable intelligence</span>
          </h1>
          <p className="text-slate-400 text-xl max-w-2xl mx-auto mb-10 leading-relaxed">
            AnonCampus converts raw student grievances into structured, 
            diversity-validated, scored signals — so institutions act on evidence, not noise.
          </p>
          <div className="flex items-center justify-center gap-4">
            <Link href="/auth/register" className="btn-primary flex items-center gap-2 text-base py-3 px-6">
              Start for free <ArrowRight size={16} />
            </Link>
            <Link href="/auth/login" className="btn-ghost flex items-center gap-2 text-base py-3 px-6">
              Sign in <ChevronRight size={16} />
            </Link>
          </div>
        </motion.div>

        {/* Stats row */}
        <motion.div
          initial={{ opacity: 0, y: 30 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3, duration: 0.6 }}
          className="mt-20 grid grid-cols-3 gap-6 max-w-lg mx-auto"
        >
          {[['≥80%', 'Signal accuracy'], ['72h', 'SLA on escalations'], ['0', 'Identity exposed']].map(([v, l]) => (
            <div key={l} className="text-center">
              <div className="text-2xl font-bold text-signal-cyan">{v}</div>
              <div className="text-xs text-slate-500 mt-1">{l}</div>
            </div>
          ))}
        </motion.div>
      </section>

      {/* Features */}
      <section className="relative z-10 max-w-5xl mx-auto px-8 py-20">
        <p className="section-label text-center mb-12">Core capabilities</p>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {FEATURES.map(({ icon: Icon, label, desc }, i) => (
            <motion.div
              key={label}
              initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.1 * i, duration: 0.5 }}
              className="card card-hover p-5"
            >
              <div className="w-9 h-9 rounded-lg bg-signal-cyan/10 flex items-center justify-center mb-4">
                <Icon size={16} className="text-signal-cyan" />
              </div>
              <div className="font-semibold text-sm mb-1">{label}</div>
              <div className="text-xs text-slate-500 leading-relaxed">{desc}</div>
            </motion.div>
          ))}
        </div>
      </section>

      {/* Pipeline */}
      <section className="relative z-10 max-w-4xl mx-auto px-8 py-20">
        <p className="section-label text-center mb-3">How it works</p>
        <h2 className="text-3xl font-bold text-center mb-14">Four steps from complaint to decision</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
          {STEPS.map(({ n, title, desc }, i) => (
            <div key={n} className="relative">
              {i < STEPS.length - 1 && (
                <div className="hidden md:block absolute top-5 left-full w-full h-px bg-gradient-to-r from-signal-cyan/30 to-transparent z-10" />
              )}
              <div className="card p-5">
                <div className="font-mono text-signal-cyan/60 text-xs mb-3">{n}</div>
                <div className="font-semibold text-sm mb-2">{title}</div>
                <div className="text-xs text-slate-500 leading-relaxed">{desc}</div>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* CTA */}
      <section className="relative z-10 max-w-2xl mx-auto px-8 py-20 text-center">
        <div className="card p-10 border-signal-cyan/20">
          <Zap size={28} className="text-signal-cyan mx-auto mb-4" />
          <h2 className="text-2xl font-bold mb-3">Ready to transform campus feedback?</h2>
          <p className="text-slate-400 text-sm mb-6">Use your college email to get started instantly.</p>
          <Link href="/auth/register" className="btn-primary inline-flex items-center gap-2">
            Register with college email <ArrowRight size={14} />
          </Link>
        </div>
      </section>

      <footer className="relative z-10 border-t border-white/[0.06] px-8 py-6 text-center text-xs text-slate-600">
        AnonCampus — Anonymous Grievance Intelligence Platform
      </footer>
    </div>
  )
}

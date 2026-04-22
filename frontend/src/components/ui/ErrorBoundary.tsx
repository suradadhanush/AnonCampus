'use client'
import React from 'react'
import { AlertTriangle, RefreshCw } from 'lucide-react'

interface State { hasError: boolean; error?: Error }

export class ErrorBoundary extends React.Component<
  { children: React.ReactNode; fallback?: React.ReactNode },
  State
> {
  constructor(props: any) {
    super(props)
    this.state = { hasError: false }
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    // Log to observability in production
    console.error('[ErrorBoundary]', error, info)
  }

  render() {
    if (this.state.hasError) {
      return this.props.fallback ?? (
        <div className="min-h-screen bg-carbon-950 flex items-center justify-center p-6">
          <div className="card p-8 max-w-sm w-full text-center">
            <div className="w-12 h-12 rounded-xl bg-signal-red/10 border border-signal-red/20 flex items-center justify-center mx-auto mb-4">
              <AlertTriangle size={20} className="text-signal-red" />
            </div>
            <h2 className="font-bold text-lg mb-2">Something went wrong</h2>
            <p className="text-slate-500 text-sm mb-6 leading-relaxed">
              {this.state.error?.message || 'An unexpected error occurred.'}
            </p>
            <button
              onClick={() => { this.setState({ hasError: false }); window.location.reload() }}
              className="btn-primary w-full flex items-center justify-center gap-2"
            >
              <RefreshCw size={14} /> Reload page
            </button>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}

'use client'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { Shield, Eye, EyeOff, AlertCircle } from 'lucide-react'
import toast from 'react-hot-toast'
import { authApi } from '@/lib/api'
import { useAuthStore } from '@/lib/store'

const schema = z.object({
  email: z.string().email('Valid email required'),
  password: z.string().min(1, 'Password required'),
})
type FormData = z.infer<typeof schema>

export default function LoginPage() {
  const [showPass, setShowPass] = useState(false)
  const [loading, setLoading] = useState(false)
  const router = useRouter()
  const { setAuth } = useAuthStore()

  const { register, handleSubmit, formState: { errors } } = useForm<FormData>({
    resolver: zodResolver(schema),
  })

  const onSubmit = async (data: FormData) => {
    setLoading(true)
    try {
      const res = await authApi.login(data)
      const { access_token, refresh_token, role } = res.data
      const meRes = await authApi.me()
      setAuth(meRes.data, access_token, refresh_token)
      toast.success('Welcome back')
      router.push(role === 'student' ? '/dashboard' : '/admin')
    } catch (err: any) {
      const detail = err?.response?.data?.detail
      let msg = 'Invalid credentials'
      if (typeof detail === 'string') {
        msg = detail
      } else if (detail?.error === 'account_locked') {
        msg = `Account locked. Retry in ${detail.retry_after_seconds}s`
      } else if (detail?.error === 'rate_limit_exceeded') {
        msg = 'Too many attempts. Please wait.'
      }
      toast.error(msg)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-[#080A0F] flex items-center justify-center p-4">
      <div className="fixed inset-0 bg-glow-cyan pointer-events-none" />
      <div className="relative z-10 w-full max-w-sm">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-10 h-10 rounded-xl bg-[#00D4FF]/10 border border-[#00D4FF]/20 mb-4">
            <Shield size={18} className="text-[#00D4FF]" />
          </div>
          <h1 className="text-xl font-bold">Sign in to AnonCampus</h1>
          <p className="text-[#64748B] text-sm mt-1">Use your college email</p>
        </div>

        <div className="card p-6">
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <div>
              <label className="text-xs text-[#94A3B8] block mb-1.5">College email</label>
              <input {...register('email')} type="email" className="input" placeholder="you@college.edu.in" />
              {errors.email && (
                <p className="text-[#FF4444] text-xs mt-1 flex items-center gap-1">
                  <AlertCircle size={11} />{errors.email.message}
                </p>
              )}
            </div>
            <div>
              <label className="text-xs text-[#94A3B8] block mb-1.5">Password</label>
              <div className="relative">
                <input {...register('password')} type={showPass ? 'text' : 'password'} className="input pr-10" placeholder="••••••••" />
                <button type="button" onClick={() => setShowPass(!showPass)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-[#64748B] hover:text-white">
                  {showPass ? <EyeOff size={14} /> : <Eye size={14} />}
                </button>
              </div>
              {errors.password && (
                <p className="text-[#FF4444] text-xs mt-1 flex items-center gap-1">
                  <AlertCircle size={11} />{errors.password.message}
                </p>
              )}
            </div>
            <button type="submit" disabled={loading} className="btn-primary w-full mt-2">
              {loading ? 'Signing in…' : 'Sign in'}
            </button>
          </form>
        </div>

        <p className="text-center text-sm text-[#64748B] mt-4">
          No account?{' '}
          <Link href="/auth/register" className="text-[#00D4FF] hover:underline">Register here</Link>
        </p>
      </div>
    </div>
  )
}

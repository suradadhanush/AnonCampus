'use client'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { Shield, AlertCircle, Eye, EyeOff } from 'lucide-react'
import toast from 'react-hot-toast'
import { authApi } from '@/lib/api'
import { useAuthStore } from '@/lib/store'
import { CATEGORIES } from '@/types'

const DEPARTMENTS = ['CSE','ECE','EEE','MECH','CIVIL','IT','AIDS','AIML','CSD','MBA','MCA']
const YEARS = [1, 2, 3, 4]

const schema = z.object({
  email:         z.string().email('Valid college email required'),
  password:      z.string().min(8).regex(/[A-Z]/, 'Need uppercase').regex(/\d/, 'Need number'),
  student_id:    z.string().min(3).max(50).regex(/^[A-Za-z0-9_-]+$/, 'Alphanumeric only'),
  department:    z.string().min(1, 'Select department'),
  academic_year: z.coerce.number().int().min(1).max(4),
})
type FormData = z.infer<typeof schema>

export default function RegisterPage() {
  const [showPass, setShowPass] = useState(false)
  const [loading, setLoading] = useState(false)
  const router = useRouter()
  const { setAuth } = useAuthStore()

  const { register, handleSubmit, formState: { errors } } = useForm<FormData>({
    resolver: zodResolver(schema),
    defaultValues: { academic_year: 1 },
  })

  const onSubmit = async (data: FormData) => {
    setLoading(true)
    try {
      await authApi.register(data)
      const loginRes = await authApi.login({ email: data.email, password: data.password })
      const { access_token, refresh_token } = loginRes.data
      const meRes = await authApi.me()
      setAuth(meRes.data, access_token, refresh_token)
      toast.success('Account created. Welcome!')
      router.push('/dashboard')
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || 'Registration failed')
    } finally {
      setLoading(false)
    }
  }

  const Field = ({ label, error, children }: any) => (
    <div>
      <label className="text-xs text-slate-400 block mb-1.5">{label}</label>
      {children}
      {error && <p className="text-signal-red text-xs mt-1 flex items-center gap-1"><AlertCircle size={11}/>{error.message}</p>}
    </div>
  )

  return (
    <div className="min-h-screen bg-carbon-950 flex items-center justify-center p-4">
      <div className="fixed inset-0 bg-glow-cyan pointer-events-none" />
      <div className="relative z-10 w-full max-w-sm">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-10 h-10 rounded-xl bg-signal-cyan/10 border border-signal-cyan/20 mb-4">
            <Shield size={18} className="text-signal-cyan" />
          </div>
          <h1 className="text-xl font-bold">Create your account</h1>
          <p className="text-slate-500 text-sm mt-1">Use your institution email</p>
        </div>

        <div className="card p-6">
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <Field label="College email" error={errors.email}>
              <input {...register('email')} type="email" className="input" placeholder="you@college.edu.in" />
            </Field>
            <Field label="Student / Roll number" error={errors.student_id}>
              <input {...register('student_id')} className="input font-mono uppercase" placeholder="22NU1A0401" />
            </Field>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Department" error={errors.department}>
                <select {...register('department')} className="input">
                  <option value="">Select…</option>
                  {DEPARTMENTS.map(d => <option key={d} value={d}>{d}</option>)}
                </select>
              </Field>
              <Field label="Year" error={errors.academic_year}>
                <select {...register('academic_year')} className="input">
                  {YEARS.map(y => <option key={y} value={y}>Year {y}</option>)}
                </select>
              </Field>
            </div>
            <Field label="Password" error={errors.password}>
              <div className="relative">
                <input {...register('password')} type={showPass ? 'text' : 'password'} className="input pr-10" placeholder="Min 8 chars, 1 uppercase, 1 number" />
                <button type="button" onClick={() => setShowPass(!showPass)} className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-white">
                  {showPass ? <EyeOff size={14} /> : <Eye size={14} />}
                </button>
              </div>
            </Field>
            <button type="submit" disabled={loading} className="btn-primary w-full mt-2">
              {loading ? 'Creating account…' : 'Create account'}
            </button>
          </form>
        </div>

        <p className="text-center text-sm text-slate-500 mt-4">
          Already registered?{' '}
          <Link href="/auth/login" className="text-signal-cyan hover:underline">Sign in</Link>
        </p>
      </div>
    </div>
  )
}

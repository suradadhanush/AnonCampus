'use client'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { X, AlertCircle, Send } from 'lucide-react'
import toast from 'react-hot-toast'
import { issuesApi } from '@/lib/api'
import { CATEGORIES } from '@/types'
import { useQueryClient } from '@tanstack/react-query'

const schema = z.object({
  title:    z.string().min(10, 'Min 10 chars').max(500),
  body:     z.string().min(20, 'Min 20 chars').max(5000),
  category: z.string().default('general'),
  severity: z.coerce.number().min(0).max(1).optional(),
})
type FormData = z.infer<typeof schema>

export function SubmitModal({ onClose }: { onClose: () => void }) {
  const [loading, setLoading] = useState(false)
  const qc = useQueryClient()
  const { register, handleSubmit, watch, formState: { errors } } = useForm<FormData>({
    resolver: zodResolver(schema),
    defaultValues: { category: 'general' },
  })
  const bodyLen = watch('body', '').length

  const onSubmit = async (data: FormData) => {
    setLoading(true)
    try {
      await issuesApi.create(data)
      toast.success('Issue submitted anonymously')
      qc.invalidateQueries({ queryKey: ['clusters'] })
      onClose()
    } catch (err: any) {
      const detail = err?.response?.data?.detail
      if (detail?.flags) toast.error(`Moderation: ${detail.flags.join(', ')}`)
      else toast.error('Submission failed')
    } finally { setLoading(false) }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />
      <div className="relative z-10 w-full max-w-lg card p-6 animate-slide-up">
        <div className="flex items-center justify-between mb-5">
          <div>
            <h2 className="font-semibold text-base">Submit anonymous issue</h2>
            <p className="text-xs text-slate-500 mt-0.5">Your identity is never stored or exposed</p>
          </div>
          <button onClick={onClose} className="text-slate-500 hover:text-white"><X size={16}/></button>
        </div>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div>
            <label className="text-xs text-slate-400 block mb-1.5">Issue title</label>
            <input {...register('title')} className="input" placeholder="Brief description of the problem…" />
            {errors.title && <p className="text-signal-red text-xs mt-1 flex items-center gap-1"><AlertCircle size={11}/>{errors.title.message}</p>}
          </div>

          <div>
            <label className="text-xs text-slate-400 block mb-1.5">Details</label>
            <textarea {...register('body')} rows={5} className="input resize-none"
              placeholder="Describe the issue in detail. Do not include names or personal identifiers." />
            <div className="flex justify-between mt-1">
              {errors.body ? <p className="text-signal-red text-xs flex items-center gap-1"><AlertCircle size={11}/>{errors.body.message}</p> : <span/>}
              <span className="text-xs text-slate-600">{bodyLen}/5000</span>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-slate-400 block mb-1.5">Category</label>
              <select {...register('category')} className="input">
                {CATEGORIES.map(c => <option key={c} value={c}>{c.charAt(0).toUpperCase() + c.slice(1)}</option>)}
              </select>
            </div>
            <div>
              <label className="text-xs text-slate-400 block mb-1.5">Severity (optional)</label>
              <select {...register('severity')} className="input">
                <option value="">Auto-detect</option>
                <option value="0.3">Low</option>
                <option value="0.6">Medium</option>
                <option value="0.85">High</option>
                <option value="1.0">Critical</option>
              </select>
            </div>
          </div>

          <div className="flex gap-3 pt-1">
            <button type="button" onClick={onClose} className="btn-ghost flex-1">Cancel</button>
            <button type="submit" disabled={loading} className="btn-primary flex-1 flex items-center justify-center gap-2">
              {loading ? 'Submitting…' : <><Send size={13}/>Submit anonymously</>}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

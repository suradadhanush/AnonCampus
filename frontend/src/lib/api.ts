import axios from 'axios'

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export const api = axios.create({
  baseURL: `${API_BASE}/api`,
  headers: { 'Content-Type': 'application/json' },
})

// Attach JWT on every request
api.interceptors.request.use((config) => {
  if (typeof window !== 'undefined') {
    const token = localStorage.getItem('access_token')
    if (token) config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Auto-logout on 401
api.interceptors.response.use(
  (res) => res,
  (error) => {
    if (error.response?.status === 401 && typeof window !== 'undefined') {
      localStorage.removeItem('access_token')
      localStorage.removeItem('refresh_token')
      window.location.href = '/auth/login'
    }
    return Promise.reject(error)
  }
)

// ─── Auth ────────────────────────────────────────────────────────────────────
export const authApi = {
  register: (data: { email: string; password: string; department?: string; year_of_study?: number }) =>
    api.post('/auth/register', data),
  login: (data: { email: string; password: string }) =>
    api.post('/auth/login', data),
  me: () => api.get('/auth/me'),
}

// ─── Issues ──────────────────────────────────────────────────────────────────
export const issuesApi = {
  list: (params?: { page?: number; page_size?: number; status_filter?: string; sort_by?: string }) =>
    api.get('/issues', { params }),
  listClusters: (params?: { page?: number; page_size?: number; feed_type?: string; status_filter?: string }) =>
    api.get('/issues/clusters', { params }),
  get: (id: number) => api.get(`/issues/${id}`),
  create: (data: { title: string; body: string; category?: string; severity?: number }) =>
    api.post('/issues', data),
  support: (id: number) => api.post(`/issues/${id}/support`),
  addContext: (id: number, context_text: string) =>
    api.post(`/issues/${id}/context`, { context_text }),
  feedback: (id: number, data: { sentiment: string; rating?: number; comment?: string }) =>
    api.post(`/issues/${id}/feedback`, data),
  getCluster: (id: number) => api.get(`/issues/${id}/cluster`),
}

// ─── Admin ───────────────────────────────────────────────────────────────────
export const adminApi = {
  listClusters: (params?: { page?: number; escalated_only?: boolean; status_filter?: string }) =>
    api.get('/admin/issues', { params }),
  updateStatus: (cluster_id: number, new_status: string, reason?: string) =>
    api.post('/admin/update-status', { cluster_id, new_status, reason }),
  stats: () => api.get('/admin/stats'),
  auditLog: (params?: { page?: number }) => api.get('/admin/audit-log', { params }),
  clusterDetail: (id: number) => api.get(`/admin/clusters/${id}`),
}

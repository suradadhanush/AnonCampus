import axios from 'axios'

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export const api = axios.create({
  baseURL: `${API_BASE}/api`,
  headers: { 'Content-Type': 'application/json' },
})

api.interceptors.request.use((config) => {
  if (typeof window !== 'undefined') {
    const token = localStorage.getItem('access_token')
    if (token) config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

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

export const authApi = {
  register: (data: { email: string; password: string; student_id: string; department: string; academic_year: number }) =>
    api.post('/auth/register', data),

  login: async (data: { email: string; password: string }) => {
    const res = await api.post('/auth/login', data)
    // Set token immediately so subsequent calls use it
    if (typeof window !== 'undefined' && res.data.access_token) {
      localStorage.setItem('access_token', res.data.access_token)
      localStorage.setItem('refresh_token', res.data.refresh_token)
    }
    return res
  },

  me: () => api.get('/auth/me'),

  logout: (refresh_token: string) =>
    api.post('/auth/logout', { refresh_token }),

  refresh: (refresh_token: string) =>
    api.post('/auth/refresh', { refresh_token }),
}

export const issuesApi = {
  list: (params?: any) => api.get('/issues', { params }),
  listClusters: (params?: any) => api.get('/issues/clusters', { params }),
  get: (id: number) => api.get(`/issues/${id}`),
  create: (data: any) => api.post('/issues', data),
  support: (id: number) => api.post(`/issues/${id}/support`),
  addContext: (id: number, context_text: string) =>
    api.post(`/issues/${id}/context`, { context_text }),
  feedback: (id: number, data: any) =>
    api.post(`/issues/${id}/feedback`, data),
  getCluster: (id: number) => api.get(`/issues/${id}/cluster`),
}

export const adminApi = {
  listClusters: (params?: any) => api.get('/admin/issues', { params }),
  updateStatus: (cluster_id: number, new_status: string, reason?: string) =>
    api.post('/admin/update-status', { cluster_id, new_status, reason }),
  stats: () => api.get('/admin/stats'),
  auditLog: (params?: any) => api.get('/admin/audit-log', { params }),
  clusterDetail: (id: number) => api.get(`/admin/clusters/${id}`),
}

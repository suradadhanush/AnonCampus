export interface Issue {
  id: number
  title: string
  body?: string
  category: string
  status: ClusterStatus
  severity: number
  cluster_id?: number
  submitter_department?: string
  submitter_year?: number
  is_moderated?: boolean
  moderation_flags?: string[]
  created_at: string
  updated_at?: string
}

export type ClusterStatus = 'new' | 'active' | 'dormant' | 'archived' | 'resolved' | 'reopened'

export interface Cluster {
  id: number
  title: string
  summary?: string
  category: string
  status: ClusterStatus
  severity: number
  confidence_score: number
  visibility_score: number
  diversity_score: number
  diversity_valid: boolean
  is_escalated: boolean
  escalation_type?: string
  report_count: number
  support_count: number
  context_count: number
  scope: number
  departments_involved: string[]
  years_involved: number[]
  sla_deadline?: string
  sla_status?: 'pending' | 'met' | 'breached'
  sla_breached_at?: string
  created_at: string
  updated_at: string
  last_activity_at: string
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  page_size: number
  has_next: boolean
}

export interface AdminStats {
  total_clusters: number
  escalated: number
  active: number
  resolved: number
  overdue_sla: number
}

export const CATEGORIES = [
  'general', 'infrastructure', 'academics', 'administration',
  'safety', 'transport', 'sports',
] as const

export type Category = typeof CATEGORIES[number]

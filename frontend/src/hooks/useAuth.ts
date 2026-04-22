import { useAuthStore } from '@/lib/store'
import { useRouter } from 'next/navigation'
import { useEffect } from 'react'

export function useRequireAuth(role?: string) {
  const { isAuthenticated, user } = useAuthStore()
  const router = useRouter()

  useEffect(() => {
    if (!isAuthenticated) { router.push('/auth/login'); return }
    if (role && user?.role !== role && user?.role !== 'super_admin') {
      router.push('/dashboard')
    }
  }, [isAuthenticated, user, role, router])

  return { user, isAuthenticated }
}

export function useAutoRefresh() {
  const { accessToken, refreshToken, setAuth, logout } = useAuthStore()

  useEffect(() => {
    if (!accessToken) return
    // Decode exp from JWT (no library needed for this)
    try {
      const payload = JSON.parse(atob(accessToken.split('.')[1]))
      const expiresIn = payload.exp * 1000 - Date.now() - 60_000 // 1 min before expiry
      if (expiresIn <= 0) { logout(); return }
      const timer = setTimeout(async () => {
        try {
          const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/auth/refresh`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ refresh_token: refreshToken }),
          })
          if (!res.ok) { logout(); return }
          const data = await res.json()
          const { useAuthStore: store } = await import('@/lib/store')
          const { user } = store.getState()
          if (user) store.getState().setAuth(user, data.access_token, data.refresh_token)
        } catch { logout() }
      }, expiresIn)
      return () => clearTimeout(timer)
    } catch { logout() }
  }, [accessToken, refreshToken, logout, setAuth])
}

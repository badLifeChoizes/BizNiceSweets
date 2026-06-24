/**
 * Axios instance with:
 * - withCredentials: true so the httpOnly refresh cookie is sent automatically
 * - Request interceptor: attaches Authorization: Bearer <token> when present
 * - Response interceptor: silent-refresh on 401 with single-flight queuing
 *   (RESEARCH.md Pattern 5; Pitfall 4 race-condition guard)
 *
 * Threat mitigations:
 *   T-02-19: withCredentials + same-origin Vite proxy keeps the refresh cookie
 *            httpOnly; the token is never handed to JS.
 *   T-02-21: single isRefreshing flag + failedQueue prevents concurrent-refresh
 *            race conditions that would self-logout the user.
 */

import axios from 'axios'
import { clearAccessToken, getAccessToken, setAccessToken } from '@/auth/token'

export const apiClient = axios.create({
  withCredentials: true, // sends the httpOnly refresh_token cookie automatically
})

// ──────────────────────────────────────────────────────────────────────────────
// Request interceptor — attach Bearer token when available
// ──────────────────────────────────────────────────────────────────────────────
apiClient.interceptors.request.use((config) => {
  const token = getAccessToken()
  if (token) {
    config.headers['Authorization'] = `Bearer ${token}`
  }
  return config
})

// ──────────────────────────────────────────────────────────────────────────────
// Response interceptor — silent refresh on 401
// ──────────────────────────────────────────────────────────────────────────────
type QueueEntry = {
  resolve: (token: string) => void
  reject: (err: unknown) => void
}

let isRefreshing = false
let failedQueue: QueueEntry[] = []

function processQueue(error: unknown, token?: string): void {
  failedQueue.forEach((entry) => {
    if (error) {
      entry.reject(error)
    } else {
      entry.resolve(token!)
    }
  })
  failedQueue = []
}

apiClient.interceptors.response.use(
  (response) => response,
  async (err: unknown) => {
    // Narrow to an axios error with a config
    if (!axios.isAxiosError(err) || !err.config) {
      return Promise.reject(err)
    }

    const original = err.config as typeof err.config & { _retry?: boolean }

    if (err.response?.status !== 401 || original._retry) {
      return Promise.reject(err)
    }

    // Another refresh is already in flight — queue this request
    if (isRefreshing) {
      return new Promise<string>((resolve, reject) => {
        failedQueue.push({ resolve, reject })
      }).then((newToken) => {
        original.headers!['Authorization'] = `Bearer ${newToken}`
        return apiClient(original)
      })
    }

    original._retry = true
    isRefreshing = true

    try {
      // POST to the refresh endpoint — the httpOnly cookie is sent automatically
      const { data } = await axios.post(
        '/api/v1/auth/refresh',
        {},
        { withCredentials: true },
      )
      const newToken: string = data.access_token
      setAccessToken(newToken)
      original.headers!['Authorization'] = `Bearer ${newToken}`
      processQueue(null, newToken)
      return apiClient(original)
    } catch (refreshErr) {
      processQueue(refreshErr)
      clearAccessToken()
      // Redirect to login; user will re-authenticate
      window.location.href = '/login'
      return Promise.reject(refreshErr)
    } finally {
      isRefreshing = false
    }
  },
)

export default apiClient

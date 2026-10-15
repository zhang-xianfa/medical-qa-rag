import { apiClient } from './client'
import type { Session } from '@/types/session'
import type { ListResponse } from '@/types/api'

export const sessionsApi = {
  createSession() {
    return apiClient.request<Session>('POST', '/sessions')
  },

  listSessions(status?: string, limit = 50) {
    const params = new URLSearchParams({ limit: String(limit) })
    if (status) params.set('status', status)
    return apiClient.request<ListResponse<Session>>('GET', `/sessions?${params}`)
  },

  getSession(id: string) {
    return apiClient.request<Session>('GET', `/sessions/${id}`)
  },

  deleteSession(id: string) {
    return apiClient.request<void>('DELETE', `/sessions/${id}`)
  },
}

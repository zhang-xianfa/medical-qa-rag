import { apiClient } from './client'

interface AuthResponse {
  access_token: string
  token_type?: string
  user?: { id: string; phone: string; nickname: string }
}

export const authApi = {
  login(phone: string, password: string) {
    return apiClient.request<AuthResponse>('POST', '/auth/login', { phone, password })
  },

  register(phone: string, password: string, nickname: string) {
    return apiClient.request<AuthResponse>('POST', '/auth/register', { phone, password, nickname })
  },
}

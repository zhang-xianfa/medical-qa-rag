import { apiClient } from './client'

export interface UserProfile {
  id?: string
  phone?: string
  nickname?: string
  gender?: string
  birth_date?: string
  height?: number
  weight?: number
  blood_type?: string
  medical_info?: {
    allergies?: string[]
    chronic_diseases?: string[]
    surgeries?: string[]
    family_history?: string[]
  }
}

export const profileApi = {
  getProfile() {
    return apiClient.request<UserProfile>('GET', '/profile')
  },

  updateProfile(data: Partial<UserProfile>) {
    return apiClient.request<UserProfile>('PATCH', '/profile', data)
  },
}

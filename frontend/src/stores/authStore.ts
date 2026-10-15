import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { apiClient } from '@/api/client'
import { authApi } from '@/api/auth'
import { profileApi, type UserProfile } from '@/api/profile'

export const useAuthStore = defineStore('auth', () => {
  // 尝试从 sessionStorage 恢复 token（页面刷新不丢失）
  const restored = apiClient.restoreToken()
  const token = ref<string | null>(apiClient.token)
  const user = ref<UserProfile | null>(null)

  // 注册 401 拦截回调
  apiClient.onUnauthorized(() => {
    logout()
  })

  const isAuthenticated = computed(() => !!token.value)

  /** 登录 */
  async function login(phone: string, password: string) {
    const res = await authApi.login(phone, password)
    token.value = res.access_token
    apiClient.setToken(res.access_token)
    await fetchProfile()
  }

  /** 注册 */
  async function register(phone: string, password: string, nickname: string) {
    const res = await authApi.register(phone, password, nickname)
    token.value = res.access_token
    apiClient.setToken(res.access_token)
    await fetchProfile()
  }

  /** 登出 */
  function logout() {
    token.value = null
    user.value = null
    apiClient.clearToken()
  }

  /** 加载用户资料 */
  async function fetchProfile() {
    try {
      user.value = await profileApi.getProfile()
    } catch (e) {
      console.error('fetchProfile failed:', e)
    }
  }

  /** 更新用户资料 */
  async function updateProfile(data: Partial<UserProfile>) {
    user.value = await profileApi.updateProfile(data)
  }

  return {
    token,
    user,
    isAuthenticated,
    login,
    register,
    logout,
    fetchProfile,
    updateProfile,
  }
})

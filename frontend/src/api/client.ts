import type { ApiErrorResponse } from '@/types/api'

const API_BASE = '/api/v1'
const DEFAULT_TIMEOUT_MS = 120_000

/** 通用 API 错误 */
export class ApiError extends Error {
  status: number
  code: string
  details?: Record<string, unknown>

  constructor(status: number, body: ApiErrorResponse) {
    super(body.message || '请求失败')
    this.name = 'ApiError'
    this.status = status
    this.code = body.error || 'UNKNOWN'
    this.details = body.details
  }
}

type LogoutHandler = () => void

/** API 客户端 */
class ApiClient {
  private _token: string | null = null
  private _onUnauthorized: LogoutHandler | null = null

  get token(): string | null { return this._token }
  get isAuthenticated(): boolean { return !!this._token }

  /** 注册 401 回调（由 authStore 在初始化时调用） */
  onUnauthorized(handler: LogoutHandler) {
    this._onUnauthorized = handler
  }

  setToken(token: string) {
    this._token = token
    // 持久化到 sessionStorage（页面刷新不丢失）
    try { sessionStorage.setItem('_auth_token', token) } catch { /* noop */ }
  }

  clearToken() {
    this._token = null
    try { sessionStorage.removeItem('_auth_token') } catch { /* noop */ }
  }

  /** 从 sessionStorage 恢复 token */
  restoreToken(): boolean {
    try {
      const stored = sessionStorage.getItem('_auth_token')
      if (stored) { this._token = stored; return true }
    } catch { /* noop */ }
    return false
  }

  /** 通用请求方法 */
  async request<T>(
    method: string,
    path: string,
    body?: unknown,
    signal?: AbortSignal,
  ): Promise<T> {
    // 超时控制
    const timeoutController = new AbortController()
    const timeoutId = setTimeout(() => timeoutController.abort(), DEFAULT_TIMEOUT_MS)

    // 合并外部 signal + 超时 signal
    const combinedSignal = signal
      ? AbortSignal.any([signal, timeoutController.signal])
      : timeoutController.signal

    const opts: RequestInit = {
      method,
      headers: { 'Content-Type': 'application/json' },
      signal: combinedSignal,
    }
    if (this._token) {
      ;(opts.headers as Record<string, string>)['Authorization'] = `Bearer ${this._token}`
    }
    if (body !== undefined) {
      opts.body = JSON.stringify(body)
    }

    try {
      const res = await fetch(`${API_BASE}${path}`, opts)

      // 401 拦截：自动触发登出
      if (res.status === 401 && this._onUnauthorized) {
        this.clearToken()
        this._onUnauthorized()
        throw new ApiError(401, {
          error: 'UNAUTHORIZED',
          code: 401,
          message: '登录已过期，请重新登录',
        })
      }

      if (res.status === 204) {
        return undefined as T
      }

      const data = await res.json().catch(() => ({} as T))

      if (!res.ok) {
        throw new ApiError(res.status, data as ApiErrorResponse)
      }

      return data as T
    } catch (e) {
      // 超时 → 友好错误
      if (e instanceof DOMException && e.name === 'TimeoutError') {
        throw new ApiError(408, {
          error: 'TIMEOUT',
          code: 408,
          message: '请求超时，AI 服务响应较慢，请稍后重试',
        })
      }
      throw e
    } finally {
      clearTimeout(timeoutId)
    }
  }
}

export const apiClient = new ApiClient()

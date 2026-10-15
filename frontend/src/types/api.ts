/** 通用分页信息 */
export interface Pagination {
  total: number
  limit: number
  offset: number
  has_more: boolean
}

/** API 错误响应 */
export interface ApiErrorResponse {
  error: string
  code: number
  message: string
  details?: Record<string, unknown>
  timestamp?: string
}

/** 列表响应包装 */
export interface ListResponse<T> {
  data: T[]
  pagination: Pagination
}

/** 检测 session_id 是否有效（排除 undefined/null 等序列化残留） */
export function isValidSessionId(sid: string | null | undefined): sid is string {
  return !!sid && sid !== 'undefined' && sid !== 'null'
}

/** 生成 UUID v4，兼容非安全上下文（HTTP 公网 IP 无法使用 crypto.randomUUID） */
export function generateUUID(): string {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    try { return crypto.randomUUID() } catch { /* fall through */ }
  }
  // Fallback: 手动生成 UUID v4
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
    const r = (Math.random() * 16) | 0
    return (c === 'x' ? r : (r & 0x3 | 0x8)).toString(16)
  })
}

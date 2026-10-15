import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { messagesApi } from '@/api/messages'
import { generateUUID } from '@/utils/validate'
import type { Message, NextAction } from '@/types/message'

export const useMessageStore = defineStore('message', () => {
  const messages = ref<Message[]>([])
  const nextAction = ref<NextAction | null>(null)

  // 竞态保护：AbortController + 请求所属会话 ID
  // _abortCtrl 用 ref → 驱动 isLoading computed（响应式）
  // requestSessionId 用普通变量 → 仅做快照比对，无需响应式
  const _abortCtrl = ref<AbortController | null>(null)
  let requestSessionId: string | null = null

  /** AI 思考中（从活跃的 AbortController 派生，无需手动 toggle） */
  const isLoading = computed(() => _abortCtrl.value !== null)

  /** 诊断是否已完成（用后端 next_action 权威信号 + 历史消息启发式兜底） */
  const isDiagnosisDone = computed(() => {
    if (nextAction.value === 'diagnosis_ready' || nextAction.value === 'emergency_interrupted') {
      return true
    }
    const msgs = messages.value
    for (let i = msgs.length - 1; i >= 0; i--) {
      if (msgs[i].role === 'assistant') {
        const m = msgs[i]
        return !m.options?.length && (m.content?.length ?? 0) > 150
      }
    }
    return false
  })

  /** 加载会话历史消息 */
  async function loadMessages(sid: string) {
    cancelRequest()
    try {
      const res = await messagesApi.listMessages(sid)
      messages.value = res.data || []
    } catch (e) {
      console.error('loadMessages:', e)
      messages.value = []
      throw e
    }
  }

  /** 发送消息（文本输入或选项选择） */
  async function sendMessage(
    text: string,
    sessionId: string,
  ) {
    // 取消前一个请求
    cancelRequest()

    // 快照会话 ID
    const sessionIdForThisRequest = sessionId

    // 创建 AbortController
    const controller = new AbortController()
    _abortCtrl.value = controller
    requestSessionId = sessionIdForThisRequest

    try {
      const res = await messagesApi.sendMessage(sessionId, text, 'text', controller.signal)

      // 校验：仅当用户仍在该会话时才应用响应
      if (requestSessionId === sessionIdForThisRequest) {
        // 记录后端权威诊断信号
        nextAction.value = res.next_action

        // 将 AI 回复追加到消息列表
        const aiMsg: Message = {
          id: res.message.id + '_ai',
          session_id: sessionIdForThisRequest,
          round_number: res.round_count,
          role: 'assistant',
          content: res.response_content,
          content_type: 'text',
          agent_source: 'system',
          token_count: null,
          options: res.options || [],
          created_at: new Date().toISOString(),
        }
        if (aiMsg.content) {
          messages.value.push(aiMsg)
        }
      }
    } catch (e: unknown) {
      if (e instanceof Error && e.name === 'AbortError') {
        // AbortError is normal flow when switching sessions — no need to log in production
        return
      }
      console.error('sendMessage:', e)
      throw e
    } finally {
      if (requestSessionId === sessionIdForThisRequest) {
        _abortCtrl.value = null
        requestSessionId = null
      }
    }
  }

  /** 发送选项选择 */
  async function sendChoice(
    value: string,
    label: string,
    sessionId: string,
  ) {
    addUserMessage(label, sessionId)
    await sendMessage(label, sessionId)
  }

  /** 取消当前请求 */
  function cancelRequest() {
    if (_abortCtrl.value) {
      _abortCtrl.value.abort()
      _abortCtrl.value = null
      requestSessionId = null
    }
  }

  /** 追加用户消息到列表（在 sendMessage 调用前手动加） */
  function addUserMessage(content: string, sessionId: string) {
    messages.value.push({
      id: generateUUID(),
      session_id: sessionId,
      round_number: messages.value.length > 0
        ? messages.value[messages.value.length - 1].round_number
        : 0,
      role: 'user',
      content,
      content_type: 'text',
      agent_source: null,
      token_count: null,
      created_at: new Date().toISOString(),
    })
  }

  /** 清空消息 */
  function clearMessages() {
    messages.value = []
    nextAction.value = null
  }

  return {
    messages,
    isLoading,
    isDiagnosisDone,
    nextAction,
    loadMessages,
    sendMessage,
    sendChoice,
    addUserMessage,
    cancelRequest,
    clearMessages,
  }
})

import { apiClient } from './client'
import type { Message, SendMessageResponse } from '@/types/message'
import type { ListResponse } from '@/types/api'

export const messagesApi = {
  sendMessage(
    sessionId: string,
    content: string,
    contentType: 'text' = 'text',
    signal?: AbortSignal,
  ) {
    return apiClient.request<SendMessageResponse>(
      'POST',
      `/sessions/${sessionId}/messages`,
      { content, content_type: contentType },
      signal,
    )
  },

  listMessages(sessionId: string, limit = 200) {
    return apiClient.request<ListResponse<Message>>(
      'GET',
      `/sessions/${sessionId}/messages?limit=${limit}`,
    )
  },
}

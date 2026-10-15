import type { WorkflowStage, SessionStatus } from './session'

/** 消息角色 */
export type MessageRole = 'user' | 'assistant' | 'system'

/** 内容类型 */
export type ContentType = 'text' | 'question' | 'diagnosis_report' | 'emergency_guide' | 'status_report'

/** Agent 来源 */
export type AgentSource = 'master' | 'interview' | 'search' | 'diagnosis' | 'emergency' | 'system'

/** 下一步动作指引 */
export type NextAction = 'continue' | 'diagnosis_ready' | 'emergency_interrupted' | 'completed'

/** 单条消息 */
export interface Message {
  id: string
  session_id: string
  round_number: number
  role: MessageRole
  content: string
  content_type: ContentType
  agent_source: AgentSource | null
  token_count: number | null
  options?: OptionCard[]
  created_at?: string
}

/** 选择题选项 */
export interface OptionCard {
  index: number
  label: string
  value: string
}

/** 发送消息请求 */
export interface SendMessageRequest {
  content: string
  content_type?: 'text'
}

/** 发送消息响应 */
export interface SendMessageResponse {
  message: Message
  session_status: SessionStatus
  current_stage: WorkflowStage
  red_flag_raised: boolean
  round_count: number
  collected_fields_summary?: Record<string, unknown>
  next_action: NextAction
  response_content: string
  options: OptionCard[]
  scenario?: string
}

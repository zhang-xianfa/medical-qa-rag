/** 会话状态 */
export type SessionStatus = 'active' | 'paused' | 'completed' | 'emergency_terminated' | 'closed_timeout'

/** 工作流阶段 */
export type WorkflowStage = 'init' | 'collect' | 'diagnose' | 'done' | 'emergency'

/** 会话意图 */
export type SessionIntent = 'diagnosis' | 'question' | 'emergency' | 'greeting' | 'status' | 'follow_up'

/** 会话基本信息（列表项） */
export interface Session {
  id: string
  session_id: string
  user_id?: string
  title?: string
  status: SessionStatus | WorkflowStage
  current_stage: WorkflowStage
  intent?: SessionIntent
  red_flag_raised: boolean
  round_count: number
  max_rounds: number
  close_reason?: string | null
  closed_at?: string | null
  created_at?: string
  updated_at?: string
}

/** 会话详情 */
export interface SessionDetail extends Session {
  medical_record_summary?: MedicalRecordSummary
  message_count?: number
}

/** 问诊记录摘要 */
export interface MedicalRecordSummary {
  session_id: string
  version: number
  completion_level: 'partial' | 'core_complete' | 'full'
  chief_complaint?: string
  duration?: string
  location?: string
  severity?: number
  accompanying_symptoms?: string[]
  collected_fields?: string[]
  missing_core_fields?: string[]
}

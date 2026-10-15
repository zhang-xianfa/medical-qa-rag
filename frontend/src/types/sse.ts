import type { DiagnosisReport } from './diagnosis'

/** SSE 消息事件 */
export interface SSEMessageEvent {
  type: 'message'
  role: 'assistant' | 'system'
  content: string
  content_type?: 'text' | 'question' | 'diagnosis_report' | 'emergency_guide' | 'status_report'
  agent_source?: 'master' | 'interview' | 'search' | 'diagnosis' | 'emergency'
  round_number?: number
}

/** SSE 诊断进度事件 */
export interface SSEDiagnosisProgressEvent {
  type: 'diagnosis_progress'
  stage: 'evidence_matching' | 'differential_gen' | 'risk_assessment' | 'recommendation' | 'schema_validate'
  progress: number
  stage_description?: string
}

/** SSE 诊断完成事件 */
export interface SSEDiagnosisCompleteEvent {
  type: 'diagnosis_complete'
  result: DiagnosisReport
}

/** SSE 紧急事件 */
export interface SSEEmergencyEvent {
  type: 'emergency'
  action: 'call_120' | 'immediate_er' | 'urgent_appointment'
  guidance: string
  red_flags: string[]
  disclaimer?: string
}

/** SSE 错误事件 */
export interface SSEErrorEvent {
  type: 'error'
  code: string
  message: string
}

/** SSE 心跳事件 */
export interface SSEHeartbeatEvent {
  type: 'heartbeat'
  timestamp: string
}

/** SSE 事件联合类型 */
export type SSEEvent =
  | SSEMessageEvent
  | SSEDiagnosisProgressEvent
  | SSEDiagnosisCompleteEvent
  | SSEEmergencyEvent
  | SSEErrorEvent
  | SSEHeartbeatEvent

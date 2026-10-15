/** 诊断报告 */
export interface DiagnosisReport {
  primary_diagnosis: {
    name: string
    probability: string
    rationale: string
    certainty_level: 'low' | 'medium' | 'high'
  }
  differential_diagnosis: Array<{
    name: string
    probability: string
    key_evidence: string
    exclusion_criteria?: string
  }>
  risk_assessment: {
    severity: '轻度' | '中度' | '重度' | '危及生命'
    urgency: '可居家观察' | '建议门诊' | '尽快就医' | '立即急诊'
    warning_signs: string[]
  }
  recommendations: Array<{
    category: '居家护理' | '用药建议' | '就医建议' | '生活方式' | '监测建议'
    content: string
    priority: number
  }>
  red_flags: Array<{
    symptom: string
    action: string
  }>
  references: DiagnosisReference[]
  disclaimer: string
}

/** 诊断引用来源 */
export interface DiagnosisReference {
  knowledge_entry_id: string
  title: string
  source: string
  year: number
  url?: string | null
  relevance_score: number
}

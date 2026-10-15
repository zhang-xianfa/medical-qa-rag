export interface SSEMessageEvent {
  type: "message";
  role: "assistant" | "system";
  content: string;
  content_type?: "text" | "question" | "diagnosis_report" | "emergency_guide" | "status_report";
  agent_source?: "master" | "interview" | "search" | "diagnosis" | "emergency";
  round_number?: number;
}

export interface SSEDiagnosisProgressEvent {
  type: "diagnosis_progress";
  stage: "evidence_matching" | "differential_gen" | "risk_assessment" | "recommendation" | "schema_validate";
  progress: number;
  stage_description?: string;
}

export interface SSEDiagnosisCompleteEvent {
  type: "diagnosis_complete";
  result: DiagnosisReport;
}

export interface SSEEmergencyEvent {
  type: "emergency";
  action: "call_120" | "immediate_er" | "urgent_appointment";
  guidance: string;
  red_flags: string[];
  disclaimer?: string;
}

export interface SSEErrorEvent {
  type: "error";
  code: string;
  message: string;
}

export interface SSEHeartbeatEvent {
  type: "heartbeat";
  timestamp: string;
}

export type SSEEvent =
  | SSEMessageEvent
  | SSEDiagnosisProgressEvent
  | SSEDiagnosisCompleteEvent
  | SSEEmergencyEvent
  | SSEErrorEvent
  | SSEHeartbeatEvent;

export interface DiagnosisReport {
  primary_diagnosis: {
    name: string;
    probability: string;
    rationale: string;
    certainty_level: "low" | "medium" | "high";
  };
  differential_diagnosis: Array<{
    name: string;
    probability: string;
    key_evidence: string;
    exclusion_criteria?: string;
  }>;
  risk_assessment: {
    severity: "轻度" | "中度" | "重度" | "危及生命";
    urgency: "可居家观察" | "建议门诊" | "尽快就医" | "立即急诊";
    warning_signs: string[];
  };
  recommendations: Array<{
    category: "居家护理" | "用药建议" | "就医建议" | "生活方式" | "监测建议";
    content: string;
    priority: number;
  }>;
  red_flags: Array<{
    symptom: string;
    action: string;
  }>;
  references: Array<{
    knowledge_entry_id: string;
    title: string;
    source: string;
    year: number;
    url?: string;
    relevance_score: number;
  }>;
  disclaimer: string;
}

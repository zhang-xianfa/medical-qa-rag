# =============================================================================
# API 数据模型定义文件（Pydantic Models）
#
# 这个文件定义了前后端交互时所有数据的"标准形状"。
#
# 包含三类模型：
# 1. 请求模型：客户端发给服务端的消息格式
# 2. 响应模型：服务端返回给客户端的完整结果
# 3. SSE事件模型：流式传输中每种事件的固定结构
# =============================================================================

from pydantic import BaseModel
from typing import Optional, List
from uuid import UUID
from datetime import datetime


# --------------------- 请求与响应模型 ---------------------

class SendMessageRequest(BaseModel):
    """用户发送消息的请求体"""
    content: str                    # 消息正文内容
    content_type: str = "text"      # 内容类型，默认纯文本，后续可扩展为 image/audio


class MessageResponse(BaseModel):
    """单条消息的完整数据结构（用于持久化存储和历史记录回显）"""
    id: UUID                        # 消息唯一ID
    session_id: UUID                # 所属会话ID
    round_number: int               # 当前对话轮次编号
    role: str                       # 角色标识：user / assistant / system
    content: str                    # 消息正文
    content_type: str               # 内容类型
    agent_source: Optional[str]     # 产生该消息的AI代理名称（可选）
    token_count: Optional[int]      # 消耗的token数，用于计费/限流（可选）
    created_at: datetime            # 消息创建时间


class OptionCard(BaseModel):
    index: int = 0
    label: str = ""
    value: str = ""


class SendMessageResponse(BaseModel):
    """发送消息后的完整响应（包含消息本身 + 当前问诊状态快照）"""
    message: MessageResponse        # 本次生成的消息详情
    session_status: str             # 会话状态：active / completed / suspended
    current_stage: str              # 当前问诊阶段：triage / history / diagnosis 等
    red_flag_raised: bool           # ⚠️ 是否触发了危急重症标志
    round_count: int                # 累计对话轮数
    collected_fields_summary: dict  # 已收集到的患者信息摘要（如主诉、症状等）
    next_action: str                # 提示前端下一步操作：continue / redirect / finish
    response_content: str = ""      # AI回复的完整文本内容
    options: list[OptionCard] = []  # 选择题选项卡片
    scenario: Optional[str] = None   # 当前问诊模板名称


# --------------------- SSE 流式事件模型 ---------------------
# SSE(Server-Sent Events) 是单向流式推送协议
# 每个事件都有 type 字段区分类型，前端根据 type 决定如何渲染

class SSEMessageEvent(BaseModel):
    """SSE消息事件：流式输出的对话内容片段"""
    type: str                       # 固定为 "message"
    role: str                       # 角色标识
    content: str                    # 本片段的消息内容
    content_type: Optional[str]     # 内容类型（可选）
    agent_source: Optional[str]     # AI代理来源（可选）
    round_number: Optional[int]     # 对话轮次（可选）


class SSEDiagnosisProgressEvent(BaseModel):
    """SSE进度事件：告知前端当前诊断进行到哪一步了"""
    type: str                       # 固定为 "diagnosis_progress"
    stage: str                      # 当前阶段名称
    progress: int                   # 进度百分比 0-100
    stage_description: Optional[str] # 阶段的通俗描述，如"正在分析伴随症状"


class SSEDiagnosisCompleteEvent(BaseModel):
    """SSE完成事件：诊断流程结束，推送最终结果"""
    type: str                       # 固定为 "diagnosis_complete"
    result: dict                    # 完整的诊断结果（结构化数据）


class SSEEmergencyEvent(BaseModel):
    """SSE紧急事件：⚠️ 检测到危急重症，立即中断正常流程"""
    type: str                       # 固定为 "emergency"
    action: str                     # 建议动作：如"立即拨打120"
    guidance: str                   # 急救指导说明
    red_flags: List[str]            # 触发紧急状态的具体危险信号列表
    disclaimer: Optional[str]       # 免责声明（可选）


class SSEErrorEvent(BaseModel):
    """SSE错误事件：服务端异常时推送给前端的结构化错误信息"""
    type: str                       # 固定为 "error"
    code: str                       # 错误码，便于前端做差异化处理
    message: str                    # 人类可读的错误描述


class SSEHeartbeatEvent(BaseModel):
    """SSE心跳事件：定期发送，防止长时间无消息时连接被中间件断开"""
    type: str                       # 固定为 "heartbeat"
    timestamp: datetime             # 心跳时间戳
# 选择题式问诊交互 — 实施计划

> 目标：将自由文本追问改为选择题式交互，每次一个问题 + 4-5 个选项 + 支持数字选择

## 变更范围

### 1. Schema 扩展 (`api/schemas/message.py`)

在 `SendMessageResponse` 中新增字段：

```python
class OptionCard(BaseModel):
    index: int              # 选项编号 1-5
    label: str              # 选项文本
    value: str              # 选项对应的提取值

class SendMessageResponse(BaseModel):
    ...
    options: list[OptionCard] = []   # 本次提问的选项卡片
    question_text: str = ""          # 本次提问的纯文本
```

### 2. 问题生成逻辑 (`workflow/nodes/interview_node.py`)

修改 `_try_llm_question`：

- 新返回值结构：`{"response_text": "...", "options": [...], "extracted_facts": {...}, ...}`
- 同时修改 `mock L2 adapter` 中的 `generate_question` 返回值，增加 `options` 字段

新增 `_parse_numeric_answer(user_msg, current_options)` 函数：

```python
def _parse_numeric_answer(user_msg: str, current_options: list) -> str | None:
    """将 '1' / '选2' / '第3个' 等数字输入映射到对应的选项值"""
    match = re.search(r'\d+', user_msg)
    if match:
        idx = int(match.group()) - 1
        if 0 <= idx < len(current_options):
            return current_options[idx].value
    return user_msg  # 不是数字输入，返回原文
```

在 `interview_node` 的处理流程中加入选项解析：

```
用户输入 → 如果是数字 → 映射为上一轮的选项值 → 输入到事实提取
         → 如果是文本 → 直接事实提取
```

### 3. 提示词模板 (`prompts/general_consultation.j2`)

修改输出 JSON Schema，增加 `options` 字段：

```jinja2
## 输出格式
{
  "response_text": "你的提问文本",
  "options": [
    {"index": 1, "label": "持续性钝痛", "value": "持续性钝痛"},
    {"index": 2, "label": "间歇性刺痛", "value": "间歇性刺痛"},
    {"index": 3, "label": "酸痛", "value": "酸痛"},
    {"index": 4, "label": "胀痛", "value": "胀痛"},
    {"index": 5, "label": "其他（请描述）", "value": "other"}
  ],
  "extracted_facts": {...},
  ...
}

## 选择题规则
- 每次只生成一个问题，提供4-5个选项
- 选项之间互斥，覆盖常见情况
- 第5个选项固定为"其他（请描述）"
- 问题文本简洁明了
```

### 4. API 响应 (`api/routers/messages.py`)

在 `_extract_assistant_reply` 之后，增加解析选项卡片的逻辑：

```python
options = _extract_options(result.get("messages", []))
```

### 5. 旧代码清理

- 删除 `_build_first_question`（不再需要硬编码提问）
- 删除 `_generate_next_question`（同上）
- 简化 `_extract_basic_facts`（LLM 的事实提取足够覆盖）

## 交互流程示例

```
User: "膝盖疼"
AI: "疼痛的性质是？"(options: [1.持续性钝痛, 2.间歇性刺痛, 3.酸痛, 4.胀痛, 5.其他])

User: "3"  → 解析为 "酸痛"
AI: "有无肿胀？"(options: [1.明显肿胀, 2.轻微肿胀, 3.无肿胀, 4.不确定, 5.其他])

User: "3"  → 解析为 "无肿胀"
AI: "持续多久了？"(options: [1.少于1天, 2.1-3天, 3.3-7天, 4.超过1周, 5.不确定])

User: "2"  → 解析为 "1-3天" → check_complete → 诊断
```

## 执行步骤

| # | 文件 | 预估 |
|---|------|------|
| 1 | `api/schemas/message.py` + OptionCard | 0.3h |
| 2 | `prompts/general_consultation.j2` + options 字段 | 0.3h |
| 3 | `workflow/nodes/interview_node.py` + 解析 + 生成 | 0.5h |
| 4 | `api/routers/messages.py` + options 提取 | 0.2h |
| 5 | 测试更新 | 0.5h |

## 风险评估

| 风险 | 缓解 |
|------|------|
| LLM 生成的选项质量不稳定 | 正则提取 + 后端校验选项数量 |
| 数字解析误匹配（如"3天"→选项3） | 仅当输入为纯数字或"选X"格式时解析 |
| 向后兼容：旧客户端不支持 options | `options: []` 默认空数组，客户端忽略即可 |

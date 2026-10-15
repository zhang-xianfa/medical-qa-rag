# 诊断报告 Prompt 模板化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 `DiagnosisAgent.generate()` 中硬编码的 prompt 抽取到 `prompts/diagnosis.j2` Jinja2 模板文件中，与问诊模板统一管理。

**Architecture:** 复用 `real_llm_adapter.py` 已有的 `_load_prompt_template()` 加载器，创建 `diagnosis.j2` 模板，用 `## 输出格式` 分隔 system/user 区块，诊断 Agent 调用时渲染模板传入 `patient_info_text` / `conversation` / `knowledge` 三个变量。

**Tech Stack:** Jinja2, 与现有 `general_consultation.j2` / `expert_consultation.j2` 一致

---

## 文件结构

| 操作 | 文件 | 职责 |
|------|------|------|
| 新建 | `prompts/diagnosis.j2` | 诊断报告系统提示词 + 用户输入模板 |
| 修改 | `workflow/diagnosis_agent.py:72-86` | 用模板渲染替代 f-string 拼接 |

---

### Task 1: 创建 `prompts/diagnosis.j2` 模板文件

**Files:**
- Create: `backend/prompts/diagnosis.j2`

- [ ] **Step 1: 创建模板文件**

模板内容如下（`## 输出格式` 之后是用户区块，之前是系统区块，与 `_split_system_user` 兼容）：

```jinja2
# 综合分析报告生成

## 角色
你是一名AI健康助手。请基于以下信息生成综合分析。

## 安全规则
- 必须使用不确定表达：可能、建议、倾向于考虑
- 禁止确诊：不得出现"确诊""一定是""保证"等肯定性表述
- 禁止给出具体用药剂量

## 输出格式
请生成一份包含以下结构的综合分析报告：
1. 主要考虑的诊断方向
2. 鉴别诊断（需排除的其他可能）
3. 风险评估（严重程度 + 紧急程度）
4. 建议措施（居家护理 / 门诊就医 / 急诊）
5. 需要警惕的危险信号

使用口语化的中文，避免过于专业的术语堆砌。
```

```jinja2
【患者信息】
{{ patient_info_text | default("暂无结构化患者信息") }}

【问诊对话】
{{ conversation | default("暂无对话历史") }}

【知识库参考】
{{ knowledge | default("暂无相关知识库参考") }}

请基于以上信息给出综合分析。
```

> **说明**：模板分为两部分——`## 输出格式` 之前是 system prompt，之后是 user prompt。`DiagnosisAgent` 使用 `real_llm_adapter._split_system_user()` 分割后分别传入 `messages` 的 system 和 user 角色。两部分写在一个 `.j2` 文件里，与 `general_consultation.j2` 结构一致。

---

### Task 2: 修改 `workflow/diagnosis_agent.py` 使用模板

**Files:**
- Modify: `backend/workflow/diagnosis_agent.py`

- [ ] **Step 1: 在文件顶部新增导入**

在现有 import 区域添加 `_load_prompt_template` 和 `_split_system_user` 的导入：

```python
# 在现有 import 之后添加
from llm.real_llm_adapter import RealLLMAdapter, LLMAPIError, LLMRateLimitError, LLMTimeoutError
from llm.real_llm_adapter import _load_prompt_template, _split_system_user  # ← 新增这行
```

- [ ] **Step 2: 替换 `generate()` 方法中的 prompt 构建逻辑**

找到 `generate()` 方法中第 71-86 行，将硬编码的 messages 构建替换为模板渲染：

**Before（删除）:**
```python
            # 5. 调用LLM生成综合分析
            result = await self.adapter.generate(
                messages=[
                    {"role": "system", "content": (
                        "你是一名AI健康助手。请基于以下信息生成综合分析。"
                        "必须使用不确定表达(可能、建议、倾向于考虑)。禁止确诊,禁止给出用药剂量。"
                    )},
                    {"role": "user", "content": (
                        f"【患者信息】\n{patient_info_text}\n\n" if patient_info_text else ""
                        f"【问诊对话】\n{conversation}\n\n"
                        f"【知识库参考】\n{knowledge}\n\n"
                        "请基于以上信息给出综合分析。"
                    )},
                ],
                max_tokens=1024, temperature=0.3,
            )
```

**After（新增）:**
```python
            # 5. 加载模板并渲染 prompt
            template = _load_prompt_template("diagnosis")
            prompt_str = template.render(
                patient_info_text=patient_info_text or "暂无结构化患者信息",
                conversation=conversation or "暂无对话历史",
                knowledge=knowledge or "暂无相关知识库参考",
            )
            system_prompt, user_content = _split_system_user(prompt_str)

            # 6. 调用LLM生成综合分析
            result = await self.adapter.generate(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                max_tokens=1024, temperature=0.3,
            )
```

- [ ] **Step 3: 检查 `generate()` 的后半部分不受影响**

确保以下逻辑保持不变：
- `_check_safe(content)` 调用（第 92 行）
- `return content + f"\n\n{disclaimer}"` 免责声明追加（第 95 行）
- `_format_history()` 函数（第 104 行）—— 这是 Python 逻辑，不需要动
- `_check_safe()` 函数（第 117 行）—— 同上

- [ ] **Step 4: 代码质量自查清单**

完成修改后，确认以下几点：

1. `_load_prompt_template("diagnosis")` 能正确找到 `prompts/diagnosis.j2`（模板加载器从 `llm/` 目录向上找 `../prompts/`）
2. `_split_system_user()` 按 `## 输出格式` 分割后，system 和 user 各有内容，不为空
3. 模板变量 `{{ patient_info_text }}` / `{{ conversation }}` / `{{ knowledge }}` 都有 `default(...)` 兜底，空值不会报错
4. `_check_safe()` 的行为不变（它检查 LLM 输出内容，不依赖模板）

---

### Task 3: 验证

**Files:**
- Read: `backend/prompts/diagnosis.j2`
- Read: `backend/workflow/diagnosis_agent.py`

- [ ] **Step 1: 运行现有诊断相关测试**

```bash
cd backend
python -m pytest tests/unit/test_graph.py -v
python -m pytest tests/integration/test_safety_red_lines.py -v
```

确认所有与诊断相关的测试仍然通过。

- [ ] **Step 2: 验证模板可被正确渲染**

```bash
cd backend
python -c "
from llm.real_llm_adapter import _load_prompt_template, _split_system_user
t = _load_prompt_template('diagnosis')
result = t.render(patient_info_text='主诉: 头痛', conversation='用户: 头痛\n助手: 哪里痛?', knowledge='偏头痛指南: ...')
sys_prompt, usr_prompt = _split_system_user(result)
print('=== SYSTEM ===')
print(sys_prompt[:200])
print()
print('=== USER ===')
print(usr_prompt[:200])
print()
print('OK: system长度=%d, user长度=%d' % (len(sys_prompt), len(usr_prompt)))
"
```

预期：system prompt 包含角色和安全规则，user prompt 包含患者信息、对话、知识库三个区块。

- [ ] **Step 3: 确认不受影响的部分**

以下文件无需修改，确认它们没有引用变更的签名：
- `workflow/nodes/response_node.py:48` — 调用 `DiagnosisAgent().generate(collected_info, search_results, messages, disclaimer)` 签名不变 ✓
- `tests/conftest.py` — MockLLMAdapter 的 `generate()` 签名不变 ✓

- [ ] **Step 4: Commit**

```bash
git add backend/prompts/diagnosis.j2 backend/workflow/diagnosis_agent.py
git commit -m "refactor: extract diagnosis prompt to prompts/diagnosis.j2 template"
```

---

## 自检清单

1. **覆盖度**：硬编码的 system prompt（角色 + 安全规则）→ 模板 `## 输出格式` 之前 ✓，硬编码的 user prompt（患者信息 + 对话 + 知识库）→ 模板 `## 输出格式` 之后 ✓
2. **空占位符**：已检查，无 "TBD" / "TODO" 等占位
3. **类型一致性**：`generate()` 方法签名不变（参数和返回值类型不变），`response_node.py` 中的调用点无需修改

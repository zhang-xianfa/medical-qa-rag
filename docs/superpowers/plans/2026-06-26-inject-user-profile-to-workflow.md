# 将用户个人信息注入问诊工作流计划

## 目标

问诊开始时，自动将用户已填写的个人信息（过敏史、慢性病史、性别、身高体重等）注入 `collected_info`，避免 LLM 重复询问。

## 数据流

```
POST /sessions/{id}/messages
  │
  ├─ load_state(session_id) → prev (含 user_id)
  │
  ├─ prev.round_count == 0 ?  ← 首次消息
  │     │
  │     ├─ 查询 users 表 → 取出个人信息
  │     ├─ 映射字段 → patient_profile dict
  │     └─ 合并到 collected_info.patient_info
  │
  └─ graph.ainvoke(state) → LLM 收到的 patient_info 已含用户档案
```

## 字段映射

| users 表字段 | → | collected_info.patient_info |
|-------------|---|---------------------------|
| `gender` | → | `gender` |
| `birth_date` | → | `age`（根据出生日期计算） |
| `height` | → | `height` |
| `weight` | → | `weight` |
| `blood_type` | → | `blood_type` |
| `medical_info.allergies` | → | `allergies`（列表） |
| `medical_info.chronic_diseases` | → | `chronic_diseases`（列表） |
| `medical_info.surgeries` | → | `surgeries`（列表） |
| `medical_info.family_history` | → | `family_history`（列表） |

## 注入时机

**仅在首轮消息时注入**（`round_count == 0`），后续轮次 LLM 可能已经覆盖/修正了这些字段，不应再次覆盖。

## 文件变更

### Task 1: 新增 `_load_user_profile()` 函数

在 `messages.py` 中添加一个辅助函数，根据 `user_id` 查询用户个人信息：

```python
async def _load_user_profile(user_id: str) -> dict:
    """从 users 表加载用户个人健康信息，转为 workflow 可用格式"""
    if not user_id:
        return {}
    
    engine = _get_engine()
    async with engine.connect() as conn:
        result = await conn.execute(
            text("SELECT gender, birth_date, height, weight, blood_type, medical_info FROM users WHERE id = :uid"),
            {"uid": user_id},
        )
        row = result.fetchone()
        if not row:
            return {}
    
    profile = {}
    if row[0]:  # gender
        profile["gender"] = row[0]
    if row[1]:  # birth_date → age
        today = date.today()
        age = today.year - row[1].year - ((today.month, today.day) < (row[1].month, row[1].day))
        profile["age"] = age
    if row[2]:  # height
        profile["height"] = row[2]
    if row[3]:  # weight
        profile["weight"] = row[3]
    if row[4]:  # blood_type
        profile["blood_type"] = row[4]
    if row[5]:  # medical_info (JSON)
        medical = row[5]
        if medical.get("allergies"):
            profile["allergies"] = medical["allergies"]
        if medical.get("chronic_diseases"):
            profile["chronic_diseases"] = medical["chronic_diseases"]
        if medical.get("surgeries"):
            profile["surgeries"] = medical["surgeries"]
        if medical.get("family_history"):
            profile["family_history"] = medical["family_history"]
    
    return profile
```

需要新增导入：
```python
from datetime import date
from persistence.database import _get_engine
from sqlalchemy import text
```

### Task 2: 在 `send_message` 中注入用户信息

在 `state` 组装完成后、`graph.ainvoke(state)` 执行前，注入用户档案。插入位置：`messages.py` 约第 95 行（`scenario_context` 处理之后）。

```python
    # ---- 注入用户个人健康信息（仅首轮）----
    if state["round_count"] == 0:
        user_id = prev.get("user_id", "")
        if user_id:
            user_profile = await _load_user_profile(user_id)
            if user_profile:
                patient_info = state["collected_info"].setdefault("patient_info", {})
                # 只填充用户尚未填写的字段（避免覆盖已采集数据）
                for key, value in user_profile.items():
                    if key not in patient_info or patient_info[key] is None:
                        patient_info[key] = value
                logger.info("Injected user profile: %d fields for user=%s", len(user_profile), user_id[:8])
```

## 不动的部分

| 内容 | 原因 |
|------|------|
| `POST /sessions` | 已经保存 `user_id` 到 session_state ✓ |
| `POST /profile` | 用户修改个人信息后，下次新建会话自动生效 |
| 工作流节点 | `collected_info` 通过 `dict_merge` 自动传递，节点无需感知来源 |
| `round_count > 0` 的轮次 | 不再注入，防止覆盖 LLM 已采集的信息 |

## 效果

**Before：**
```
用户: 我头痛
LLM:  您对什么药物过敏吗？     ← 重复询问已知信息
```

**After：**
```
用户: 我头痛
LLM:  您头痛持续多久了？       ← 已知道过敏史=青霉素，直接进入现病史
      （prompt 中的 collected_info 已含 allergies:["青霉素"]）
```

## 验证

```bash
cd backend
python -m pytest tests/unit/ -q --ignore=tests/unit/test_database.py
```

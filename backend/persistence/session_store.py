"""
会话状态与消息 PostgreSQL 持久化存储

替换 messages.py 中的内存 dict (_session_state / _messages_store)，
服务重启后会话数据不丢失。
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from sqlalchemy import text
from persistence.database import _get_engine

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# 建表（幂等）
# ═══════════════════════════════════════════════════════════════


async def ensure_tables() -> None:
    """确保 session_state 和 messages 表存在（幂等）"""
    engine = _get_engine()
    async with engine.begin() as conn:
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS session_state (
                session_id   TEXT PRIMARY KEY,
                state_data   JSONB NOT NULL DEFAULT '{}',
                updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """))
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS messages (
                id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                session_id    TEXT NOT NULL,
                role          TEXT NOT NULL,
                content       TEXT NOT NULL DEFAULT '',
                content_type  TEXT DEFAULT 'text',
                round_number  INT DEFAULT 0,
                agent_source  TEXT,
                token_count   INT,
                created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """))
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_messages_session
            ON messages (session_id, created_at)
        """))
        # v2 迁移：为历史消息添加 options 列（存储 AI 选择题选项）
        await conn.execute(text("""
            ALTER TABLE messages ADD COLUMN IF NOT EXISTS options JSONB DEFAULT '[]'
        """))
    logger.info("Session persistence tables ready")


# ═══════════════════════════════════════════════════════════════
# 会话状态
# ═══════════════════════════════════════════════════════════════


async def load_state(session_id: str) -> dict:
    """加载会话状态，不存在则返回空字典"""
    engine = _get_engine()
    async with engine.connect() as conn:
        result = await conn.execute(
            text("SELECT state_data FROM session_state WHERE session_id = :sid"),
            {"sid": session_id},
        )
        row = result.fetchone()
        if row is None:
            return {}
        return row[0] or {}


async def save_state(session_id: str, state: dict) -> None:
    """保存（插入或合并更新）会话状态 — 原子操作，不覆盖未传入的 key"""
    engine = _get_engine()
    async with engine.begin() as conn:
        await conn.execute(
            text("""
                INSERT INTO session_state (session_id, state_data, updated_at)
                VALUES (:sid, :data, NOW())
                ON CONFLICT (session_id) DO UPDATE
                SET state_data = session_state.state_data || EXCLUDED.state_data,
                    updated_at = NOW()
            """),
            {"sid": session_id, "data": json.dumps(state, ensure_ascii=False)},
        )


# ═══════════════════════════════════════════════════════════════
# 消息存储
# ═══════════════════════════════════════════════════════════════


async def append_message(session_id: str, msg: dict) -> None:
    """追加一条消息"""
    engine = _get_engine()
    async with engine.begin() as conn:
        await conn.execute(
            text("""
                INSERT INTO messages (id, session_id, role, content, content_type,
                                      round_number, agent_source, token_count, options, created_at)
                VALUES (:id, :sid, :role, :content, :content_type,
                        :round_number, :agent_source, :token_count, :options, :created_at)
            """),
            {
                "id": msg.get("id"),
                "sid": session_id,
                "role": msg.get("role", ""),
                "content": msg.get("content", ""),
                "content_type": msg.get("content_type", "text"),
                "round_number": msg.get("round_number", 0),
                "agent_source": msg.get("agent_source"),
                "token_count": msg.get("token_count"),
                "options": json.dumps(msg.get("options") or [], ensure_ascii=False),
                "created_at": msg.get("created_at", datetime.now(timezone.utc)),
            },
        )


async def load_messages(session_id: str,
                        limit: int = 200,
                        offset: int = 0,
                        round_number: int | None = None,
                        need_count: bool = True) -> tuple[list[dict], int]:
    """分页加载消息历史，返回 (消息列表, 总数)。need_count=False 可跳过 COUNT 查询。"""
    engine = _get_engine()
    async with engine.connect() as conn:
        total = 0
        if need_count:
            if round_number is not None:
                count_result = await conn.execute(
                    text("SELECT COUNT(*) FROM messages WHERE session_id = :sid AND round_number = :rn"),
                    {"sid": session_id, "rn": round_number},
                )
            else:
                count_result = await conn.execute(
                    text("SELECT COUNT(*) FROM messages WHERE session_id = :sid"),
                    {"sid": session_id},
                )
            total = count_result.scalar() or 0

        # 分页数据
        if round_number is not None:
            result = await conn.execute(
                text("""
                    SELECT id, session_id, role, content, content_type,
                           round_number, agent_source, token_count, options, created_at
                    FROM messages
                    WHERE session_id = :sid AND round_number = :rn
                    ORDER BY created_at
                    LIMIT :limit OFFSET :offset
                """),
                {"sid": session_id, "rn": round_number, "limit": limit, "offset": offset},
            )
        else:
            result = await conn.execute(
                text("""
                    SELECT id, session_id, role, content, content_type,
                           round_number, agent_source, token_count, options, created_at
                    FROM messages
                    WHERE session_id = :sid
                    ORDER BY created_at
                    LIMIT :limit OFFSET :offset
                """),
                {"sid": session_id, "limit": limit, "offset": offset},
            )

        rows = result.fetchall()
        messages = []
        for row in rows:
            messages.append({
                "id": str(row[0]),
                "session_id": row[1],
                "role": row[2],
                "content": row[3],
                "content_type": row[4],
                "round_number": row[5],
                "agent_source": row[6],
                "token_count": row[7],
                "options": row[8] or [],
                "created_at": row[9].isoformat() if row[9] else None,
            })

    return messages, total


# ═══════════════════════════════════════════════════════════════
# 会话管理（sessions 路由使用 session_state 表）
# ═══════════════════════════════════════════════════════════════


async def list_sessions_from_db(status: str | None = None,
                                user_id: str | None = None,
                                limit: int = 20, offset: int = 0) -> tuple[list[dict], int]:
    """从 session_state 表分页查询会话列表"""
    engine = _get_engine()
    async with engine.connect() as conn:
        # 构建查询条件
        conditions = []
        params: dict = {"limit": limit, "offset": offset}
        if status:
            conditions.append("state_data->>'current_stage' = :status")
            params["status"] = status
        if user_id:
            conditions.append("state_data->>'user_id' = :user_id")
            params["user_id"] = user_id

        where_clause = ""
        if conditions:
            where_clause = "WHERE " + " AND ".join(conditions)

        # 总数
        count_result = await conn.execute(
            text(f"SELECT COUNT(*) FROM session_state {where_clause}"),
            params,
        )
        total = count_result.scalar() or 0

        # 列表
        result = await conn.execute(
            text(f"""
                SELECT session_id, state_data, updated_at
                FROM session_state {where_clause}
                ORDER BY updated_at DESC
                LIMIT :limit OFFSET :offset
            """),
            params,
        )
        rows = result.fetchall()
        sessions = []
        for row in rows:
            state = row[1] or {}
            sessions.append({
                "id": row[0],
                "session_id": row[0],
                "title": state.get("title", "新会话"),
                "status": state.get("current_stage", "init"),
                "current_stage": state.get("current_stage", "init"),
                "round_count": state.get("round_count", 0),
                "red_flag_raised": state.get("red_flag_raised", False),
                "updated_at": row[2].isoformat() if row[2] else None,
            })

    return sessions, total


async def delete_session_from_db(session_id: str) -> bool:
    """删除会话（级联删除消息 + 状态）"""
    engine = _get_engine()
    async with engine.begin() as conn:
        await conn.execute(
            text("DELETE FROM messages WHERE session_id = :sid"),
            {"sid": session_id},
        )
        result = await conn.execute(
            text("DELETE FROM session_state WHERE session_id = :sid"),
            {"sid": session_id},
        )
        return result.rowcount > 0

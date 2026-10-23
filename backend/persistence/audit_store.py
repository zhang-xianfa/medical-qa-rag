"""
安全审计与电子病历持久化。

两张表都用 session_id TEXT 关联 session_state（本地库没有 sessions 表，
原先 ORM 模型指向 sessions.id 外键，导致建表失败、审计数据一直写不进去）。
"""

from __future__ import annotations

import json
import logging

from sqlalchemy import text

from persistence.database import _get_engine

logger = logging.getLogger(__name__)


async def ensure_audit_tables() -> None:
    """幂等建表：audit_logs（安全事件审计） + medical_records（结构化病历）"""
    engine = _get_engine()
    async with engine.begin() as conn:
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                session_id        TEXT NOT NULL,
                agent_name        TEXT NOT NULL DEFAULT '',
                event_type        TEXT NOT NULL DEFAULT '',
                input_summary     JSONB NOT NULL DEFAULT '{}',
                output_summary    JSONB NOT NULL DEFAULT '{}',
                token_usage       JSONB NOT NULL DEFAULT '{}',
                latency_ms        INT NOT NULL DEFAULT 0,
                model_name        TEXT NOT NULL DEFAULT '',
                red_flag_triggered BOOLEAN NOT NULL DEFAULT FALSE,
                safety_check      JSONB NOT NULL DEFAULT '{}',
                error_info        JSONB,
                created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """))
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_audit_logs_session_time
            ON audit_logs (session_id, created_at DESC)
        """))
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_audit_logs_event_type
            ON audit_logs (event_type)
        """))
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_audit_logs_red_flag
            ON audit_logs (red_flag_triggered)
        """))
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS medical_records (
                id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                session_id            TEXT NOT NULL UNIQUE,
                version               INT NOT NULL DEFAULT 1,
                record_data           JSONB NOT NULL DEFAULT '{}',
                completion_level      TEXT NOT NULL DEFAULT 'partial',
                missing_core_fields   TEXT[] NOT NULL DEFAULT '{}',
                created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """))
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_medical_records_session
            ON medical_records (session_id)
        """))
    logger.info("Audit and medical record tables ready")


async def append_audit(
    session_id: str,
    event_type: str,
    agent_name: str = "",
    input_summary: dict | None = None,
    output_summary: dict | None = None,
    token_usage: dict | None = None,
    latency_ms: int = 0,
    model_name: str = "",
    red_flag_triggered: bool = False,
    safety_check: dict | None = None,
    error_info: dict | None = None,
) -> None:
    """写一条审计记录。审计失败不能影响主流程，所以异常只记录日志。"""
    try:
        engine = _get_engine()
        async with engine.begin() as conn:
            await conn.execute(
                text("""
                    INSERT INTO audit_logs
                        (session_id, agent_name, event_type, input_summary, output_summary,
                         token_usage, latency_ms, model_name, red_flag_triggered,
                         safety_check, error_info)
                    VALUES
                        (:sid, :agent, :etype, CAST(:inp AS jsonb), CAST(:outp AS jsonb),
                         CAST(:tok AS jsonb), :lat, :model, :red,
                         CAST(:safety AS jsonb), CAST(:err AS jsonb))
                """),
                {
                    "sid": session_id,
                    "agent": agent_name,
                    "etype": event_type,
                    "inp": json.dumps(input_summary or {}, ensure_ascii=False),
                    "outp": json.dumps(output_summary or {}, ensure_ascii=False),
                    "tok": json.dumps(token_usage or {}, ensure_ascii=False),
                    "lat": latency_ms,
                    "model": model_name,
                    "red": red_flag_triggered,
                    "safety": json.dumps(safety_check or {}, ensure_ascii=False),
                    "err": json.dumps(error_info, ensure_ascii=False) if error_info else None,
                },
            )
    except Exception as e:
        logger.warning("Audit write failed (session=%s, event=%s): %s", session_id, event_type, e)


async def list_audit(
    session_id: str,
    category: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[dict], int]:
    """按会话查询审计事件，category 对应 event_type"""
    engine = _get_engine()
    params: dict = {"sid": session_id, "limit": limit, "offset": offset}
    where = "WHERE session_id = :sid"
    if category:
        where += " AND event_type = :cat"
        params["cat"] = category

    async with engine.connect() as conn:
        total = (await conn.execute(
            text(f"SELECT COUNT(*) FROM audit_logs {where}"), params
        )).scalar() or 0
        rows = (await conn.execute(
            text(f"""
                SELECT id::text, agent_name, event_type, input_summary, output_summary,
                       token_usage, latency_ms, model_name, red_flag_triggered,
                       safety_check, error_info, created_at
                FROM audit_logs {where}
                ORDER BY created_at DESC
                LIMIT :limit OFFSET :offset
            """),
            params,
        )).fetchall()

    events = []
    for r in rows:
        events.append({
            "id": r[0],
            "session_id": session_id,
            "agent_name": r[1],
            "event_type": r[2],
            "category": r[2],
            "input_summary": r[3] or {},
            "output_summary": r[4] or {},
            "token_usage": r[5] or {},
            "latency_ms": r[6],
            "model_name": r[7],
            "red_flag_triggered": r[8],
            "safety_check": r[9] or {},
            "error_info": r[10],
            "created_at": r[11].isoformat() if r[11] else None,
        })
    return events, total


async def summarize_audit(session_id: str) -> dict:
    """安全事件汇总，供 /safety 接口的 summary 字段使用"""
    engine = _get_engine()
    async with engine.connect() as conn:
        row = (await conn.execute(text("""
            SELECT
                COUNT(*)                                            AS total_events,
                COUNT(*) FILTER (WHERE red_flag_triggered)          AS red_flag_count,
                COUNT(*) FILTER (WHERE event_type = 'pii_masked')   AS pii_detection_count
            FROM audit_logs WHERE session_id = :sid
        """), {"sid": session_id})).fetchone()

    return {
        "total_events": row[0] if row else 0,
        "red_flag_count": row[1] if row else 0,
        "pii_detection_count": row[2] if row else 0,
    }


async def upsert_medical_record(
    session_id: str,
    record_data: dict,
    completion_level: str = "partial",
    missing_core_fields: list[str] | None = None,
) -> None:
    """诊断完成后写入/更新结构化病历（一个会话一条）"""
    try:
        engine = _get_engine()
        async with engine.begin() as conn:
            await conn.execute(
                text("""
                    INSERT INTO medical_records
                        (session_id, record_data, completion_level, missing_core_fields)
                    VALUES (:sid, CAST(:data AS jsonb), :level, :missing)
                    ON CONFLICT (session_id) DO UPDATE
                    SET record_data = EXCLUDED.record_data,
                        completion_level = EXCLUDED.completion_level,
                        missing_core_fields = EXCLUDED.missing_core_fields,
                        version = medical_records.version + 1,
                        updated_at = NOW()
                """),
                {
                    "sid": session_id,
                    "data": json.dumps(record_data, ensure_ascii=False),
                    "level": completion_level,
                    "missing": missing_core_fields or [],
                },
            )
    except Exception as e:
        logger.warning("Medical record write failed (session=%s): %s", session_id, e)


async def get_medical_record(session_id: str) -> dict | None:
    engine = _get_engine()
    async with engine.connect() as conn:
        row = (await conn.execute(text("""
            SELECT record_data, completion_level, missing_core_fields, version, updated_at
            FROM medical_records WHERE session_id = :sid
        """), {"sid": session_id})).fetchone()
    if not row:
        return None
    return {
        "record_data": row[0] or {},
        "completion_level": row[1],
        "missing_core_fields": list(row[2] or []),
        "version": row[3],
        "updated_at": row[4].isoformat() if row[4] else None,
    }

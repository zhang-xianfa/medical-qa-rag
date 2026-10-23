import pytest

import persistence.database as db
from persistence.database import Base


@pytest.mark.asyncio
async def test_check_db_connection_returns_bool_when_db_unavailable(monkeypatch):
    """数据库不可达时 check_db_connection 返回 False。

    注意：必须用 monkeypatch 设置环境变量，否则会被后续用例读到脏值
    （曾经直接写 os.environ，导致整个测试套件后面的用例连错数据库）。
    """
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+asyncpg://invalid:none@localhost:5432/nonexistent",
    )
    db._engine = None
    db._async_session_local = None

    result = await db.check_db_connection()
    assert result is False


@pytest.mark.asyncio
async def test_base_metadata_has_medical_records_table():
    table_names = Base.metadata.tables.keys()
    assert "medical_records" in table_names
    assert "audit_logs" in table_names

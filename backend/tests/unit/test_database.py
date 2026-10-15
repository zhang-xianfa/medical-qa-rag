import os
import pytest
from config.settings import Settings
from persistence.database import Base, init_db


@pytest.mark.asyncio
async def test_check_db_connection_returns_bool_when_db_unavailable():
    os.environ["DATABASE_URL"] = "postgresql+asyncpg://invalid:none@localhost:5432/nonexistent"
    from persistence.database import check_db_connection
    result = await check_db_connection()
    assert result is False


@pytest.mark.asyncio
async def test_base_metadata_has_medical_records_table():
    table_names = Base.metadata.tables.keys()
    assert "medical_records" in table_names
    assert "audit_logs" in table_names

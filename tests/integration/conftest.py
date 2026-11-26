import pytest

from src.decisionos.data.extract import get_engine


@pytest.fixture
def connection():
    with get_engine().connect() as conn:
        conn.exec_driver_sql("SET TRANSACTION READ ONLY")
        conn.exec_driver_sql("SET LOCAL statement_timeout = '5s'")
        yield conn

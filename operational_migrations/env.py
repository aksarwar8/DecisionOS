"""Separate migration history; never stamp or alter the retail migration chain."""
from alembic import context
from sqlalchemy import text

from backend.services.operational_store import migration_schema
from src.decisionos.data.extract import get_engine

if context.is_offline_mode():
    raise RuntimeError("Operational migrations require an explicit online connection.")

schema = migration_schema
schema()

def migrate(connection):
    connection.execute(text(f'SET LOCAL search_path TO "{schema()}"'))
    context.configure(connection=connection, version_table="decisionos_operational_alembic_version",
                      version_table_schema=schema(), transactional_ddl=True)
    with context.begin_transaction():
        context.run_migrations()


external = context.config.attributes.get("connection")
if external is not None:
    migrate(external)
else:
    engine = get_engine()
    try:
        with engine.begin() as connection:
            migrate(connection)
    finally:
        engine.dispose()

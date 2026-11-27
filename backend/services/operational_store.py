"""Opt-in PostgreSQL storage for existing JSON-shaped application records."""
import json
import os
import re

from sqlalchemy import text

from src.decisionos.data.extract import get_engine


def enabled():
    mode = os.environ.get("DECISIONOS_RECORD_STORE", "local")
    if mode not in {"local", "postgres"}:
        raise ValueError("DECISIONOS_RECORD_STORE must be local or postgres.")
    return mode == "postgres"


def schema():
    value = os.environ.get("DECISIONOS_OPERATIONAL_SCHEMA", "public")
    if not re.fullmatch(r"[a-z_][a-z0-9_]{0,62}", value):
        raise ValueError("Invalid operational schema name.")
    return value


def migration_schema():
    """Require a deliberately selected non-public schema for experimental migrations."""
    if not os.environ.get("DECISIONOS_OPERATIONAL_SCHEMA") or schema() == "public":
        raise ValueError("Set DECISIONOS_OPERATIONAL_SCHEMA to an existing non-public test schema.")
    return schema()


def put(kind, identifier, record, *, insert_only=False):
    payload = json.dumps(record, allow_nan=False)
    conflict = "DO NOTHING" if insert_only else (
        "DO UPDATE SET payload = EXCLUDED.payload, updated_at = now()"
    )
    engine = get_engine()
    try:
        with engine.begin() as connection:
            result = connection.execute(text(f"""
                INSERT INTO {schema()}.decisionos_records (kind, record_id, payload)
                VALUES (:kind, :identifier, CAST(:payload AS jsonb))
                ON CONFLICT (kind, record_id) {conflict}
            """), {"kind": kind, "identifier": str(identifier), "payload": payload})
            return bool(result.rowcount)
    finally:
        engine.dispose()


def get(kind, identifier):
    engine = get_engine()
    try:
        with engine.connect() as connection:
            value = connection.execute(text(f"""
                SELECT payload FROM {schema()}.decisionos_records
                WHERE kind = :kind AND record_id = :identifier
            """), {"kind": kind, "identifier": str(identifier)}).scalar_one_or_none()
        if value is None:
            raise FileNotFoundError("Record not found.")
        return value
    finally:
        engine.dispose()


def recent(kind, limit):
    engine = get_engine()
    try:
        with engine.connect() as connection:
            return list(connection.execute(text(f"""
                SELECT payload FROM {schema()}.decisionos_records WHERE kind = :kind
                ORDER BY created_at DESC, record_id DESC LIMIT :limit
            """), {"kind": kind, "limit": limit}).scalars())
    finally:
        engine.dispose()

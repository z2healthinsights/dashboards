"""Information-schema queries for the Semantic Layer browser.

Different warehouses surface their catalog metadata differently. The PBI
file ships an empty report — its job is to publish the model — so this
Dash version is a custom model browser. We use cross-warehouse-portable
information_schema tables; only DuckDB-specific table sampling uses
parameter-bound SQL.
"""

from __future__ import annotations

import logging

import pandas as pd

from tuva_dash import run_query
from tuva_dash.config import get_settings

log = logging.getLogger(__name__)

SCHEMA = "semantic_layer"


def _safe(sql: str, columns: list[str]) -> pd.DataFrame:
    try:
        return run_query(sql, columns=columns)
    except Exception as exc:
        log.warning("semantic_layer query failed (returning empty): %s", exc)
        return pd.DataFrame(columns=columns)


def load_tables() -> pd.DataFrame:
    """One row per table in the semantic_layer schema."""
    s = get_settings()
    schema = s.metadata_schema(SCHEMA)
    sql = f"""
        SELECT LOWER(table_name) AS table_name
        FROM information_schema.tables
        WHERE table_schema = {s.sql_literal(schema)}
        ORDER BY table_name
    """
    df = _safe(sql, ["table_name"])
    if df.empty:
        return df

    # Row count + last-run freshness (best-effort; tolerant of missing column)
    rows = []
    for t in df["table_name"]:
        try:
            cnt = run_query(f"SELECT COUNT(*) AS n FROM {s.qualified(SCHEMA, t)}", columns=["n"])
            n = int(cnt["n"].iloc[0]) if not cnt.empty else 0
        except Exception:
            n = 0
        last_run = None
        try:
            lr = run_query(
                f"SELECT MAX(tuva_last_run) AS last_run FROM {s.qualified(SCHEMA, t)}",
                columns=["last_run"],
            )
            if not lr.empty:
                last_run = lr["last_run"].iloc[0]
        except Exception:
            pass
        kind = "fact" if t.startswith("fact_") else "dim" if t.startswith("dim_") else "other"
        rows.append({
            "table_name": t,
            "kind": kind,
            "row_count": n,
            "last_run": last_run,
        })
    return pd.DataFrame(rows)


def load_columns() -> pd.DataFrame:
    """All columns across the semantic_layer schema."""
    s = get_settings()
    schema = s.metadata_schema(SCHEMA)
    sql = f"""
        SELECT
            LOWER(table_name) AS table_name,
            LOWER(column_name) AS column_name,
            data_type,
            ordinal_position
        FROM information_schema.columns
        WHERE table_schema = {s.sql_literal(schema)}
        ORDER BY table_name, ordinal_position
    """
    return _safe(sql, ["table_name", "column_name", "data_type", "ordinal_position"])


def load_sample(table_name: str, limit: int = 100) -> pd.DataFrame:
    """First `limit` rows of a single table — used by the table browser."""
    s = get_settings()
    # Whitelist: must be a real table name from the semantic_layer schema.
    valid = set(load_tables()["table_name"].tolist())
    if table_name not in valid:
        return pd.DataFrame()
    try:
        return run_query(f"SELECT * FROM {s.qualified(SCHEMA, table_name)} LIMIT {int(limit)}")
    except Exception as exc:
        log.warning("sample query failed: %s", exc)
        return pd.DataFrame()

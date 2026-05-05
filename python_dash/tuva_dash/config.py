"""Connection settings — mirrors the M parameters used by the PBI dashboards."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the python_dash/ root so every dashboard sees the same config.
_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_ROOT / ".env")


def _get(key: str, default: str = "") -> str:
    return os.getenv(key, default).strip()


def _get_bool(key: str, default: bool = False) -> bool:
    raw = _get(key, "true" if default else "false").lower()
    return raw in {"1", "true", "yes", "y", "on"}


def _get_int(key: str, default: int | None = None) -> int | None:
    raw = _get(key)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    """Runtime configuration for the dashboards.

    Field names intentionally track the PBI parameter names so that operators
    coming from the Power BI side can map values 1:1.
    """

    load_data: bool
    data_warehouse_type: str
    server_name: str
    database_name: str
    compute_name: str
    role_name: str
    schema_prepend: str  # "NULL" means no prefix, matching PBI convention

    # Snowflake
    snowflake_account: str
    snowflake_user: str
    snowflake_password: str
    snowflake_warehouse: str
    snowflake_database: str
    snowflake_role: str
    snowflake_authenticator: str

    # BigQuery
    google_application_credentials: str
    bigquery_project: str

    # Redshift
    redshift_user: str
    redshift_password: str
    redshift_port: int

    # ODBC / SQL Server / Fabric
    odbc_driver: str
    odbc_user: str
    odbc_password: str

    # DuckDB
    duckdb_database: str

    # Optional row cap on large fact pulls (PBI calls this `row_limit`).
    row_limit: int | None

    # Dash server
    dash_host: str
    dash_port: int
    dash_debug: bool

    def schema(self, tuva_schema: str) -> str:
        """Apply the schema prefix the same way the M code does."""
        if self.schema_prepend and self.schema_prepend.upper() != "NULL":
            return f"{self.schema_prepend}{tuva_schema}"
        return tuva_schema

    def qualified(self, tuva_schema: str, table: str) -> str:
        """Return a fully qualified table reference for the active warehouse.

        DuckDB is queried as `schema.table` because the database is the file
        itself; everything else uses `database.schema.table`.
        """
        schema = self.schema(tuva_schema)
        if self.data_warehouse_type == "duckdb":
            return f"{schema}.{table}"
        db = self.database_name or self.snowflake_database
        return f"{db}.{schema}.{table}"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(
        load_data=_get_bool("LOAD_DATA", False),
        data_warehouse_type=_get("DATA_WAREHOUSE_TYPE", "snowflake").lower(),
        server_name=_get("SERVER_NAME"),
        database_name=_get("DATABASE_NAME"),
        compute_name=_get("COMPUTE_NAME"),
        role_name=_get("ROLE_NAME"),
        schema_prepend=_get("SCHEMA_PREPEND_NAME", "NULL"),
        snowflake_account=_get("SNOWFLAKE_ACCOUNT"),
        snowflake_user=_get("SNOWFLAKE_USER"),
        snowflake_password=_get("SNOWFLAKE_PASSWORD"),
        snowflake_warehouse=_get("SNOWFLAKE_WAREHOUSE", "COMPUTE_WH"),
        snowflake_database=_get("SNOWFLAKE_DATABASE"),
        snowflake_role=_get("SNOWFLAKE_ROLE", "ACCOUNTADMIN"),
        snowflake_authenticator=_get("SNOWFLAKE_AUTHENTICATOR"),
        google_application_credentials=_get("GOOGLE_APPLICATION_CREDENTIALS"),
        bigquery_project=_get("BIGQUERY_PROJECT"),
        redshift_user=_get("REDSHIFT_USER"),
        redshift_password=_get("REDSHIFT_PASSWORD"),
        redshift_port=_get_int("REDSHIFT_PORT", 5439) or 5439,
        odbc_driver=_get("ODBC_DRIVER", "ODBC Driver 18 for SQL Server"),
        odbc_user=_get("ODBC_USER"),
        odbc_password=_get("ODBC_PASSWORD"),
        duckdb_database=_get("DUCKDB_DATABASE"),
        row_limit=_get_int("ROW_LIMIT"),
        dash_host=_get("DASH_HOST", "127.0.0.1"),
        dash_port=_get_int("DASH_PORT", 8050) or 8050,
        dash_debug=_get_bool("DASH_DEBUG", True),
    )

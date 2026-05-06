"""Multi-warehouse query runner.

Centralizes the dispatch that the PBI side handles via
`data_warehouse_type_function` (see ../power_bi/dqi_analytics/...model.bim
~line 10672). The `load_data` gate matches the M-side
`if load_data then <query> else #table(...)` pattern: when disabled, we
return an empty frame using the supplied column list so dashboards open
without credentials.
"""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

import pandas as pd

from tuva_dash.config import Settings, get_settings

_PYTHON_DASH_ROOT = Path(__file__).resolve().parent.parent


class WarehouseDriverMissing(RuntimeError):
    """Raised when the chosen warehouse type's driver isn't installed."""


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = [str(c).lower() for c in df.columns]
    return df


def run_query(
    sql: str,
    columns: Sequence[str] | None = None,
    settings: Settings | None = None,
) -> pd.DataFrame:
    """Execute `sql` against the configured warehouse.

    `columns` is the expected column list. When `LOAD_DATA=false` we skip the
    warehouse entirely and return an empty DataFrame with these columns —
    this lets every dashboard render without a live connection.
    """
    settings = settings or get_settings()

    if not settings.load_data:
        return pd.DataFrame(columns=list(columns or []))

    wh = settings.data_warehouse_type
    if wh == "duckdb":
        return _normalize_columns(_run_duckdb(sql, settings))
    if wh == "snowflake":
        return _normalize_columns(_run_snowflake(sql, settings))
    if wh == "bigquery":
        return _normalize_columns(_run_bigquery(sql, settings))
    if wh == "redshift":
        return _normalize_columns(_run_redshift(sql, settings))
    if wh in {"odbc", "sqlserver", "fabric"}:
        return _normalize_columns(_run_odbc(sql, settings))
    raise ValueError(f"Unsupported DATA_WAREHOUSE_TYPE: {wh!r}")


def _run_duckdb(sql: str, settings: Settings) -> pd.DataFrame:
    try:
        import duckdb
    except ImportError as exc:
        raise WarehouseDriverMissing(
            "duckdb is not installed. Run `pip install duckdb`."
        ) from exc

    if not settings.duckdb_database:
        raise ValueError(
            "DUCKDB_DATABASE is not set. Point it at your local Tuva DuckDB file."
        )

    db_path = Path(settings.duckdb_database).expanduser()
    if not db_path.is_absolute():
        db_path = (_PYTHON_DASH_ROOT / db_path).resolve()
    if not db_path.exists():
        raise FileNotFoundError(f"DuckDB file not found: {db_path}")

    with duckdb.connect(str(db_path), read_only=True) as conn:
        return conn.execute(sql).fetchdf()


def _run_snowflake(sql: str, settings: Settings) -> pd.DataFrame:
    try:
        import snowflake.connector
    except ImportError as exc:
        raise WarehouseDriverMissing(
            "snowflake-connector-python is not installed. "
            "Run `pip install snowflake-connector-python[pandas]`."
        ) from exc

    kwargs = dict(
        account=settings.snowflake_account,
        user=settings.snowflake_user,
        warehouse=settings.snowflake_warehouse or settings.compute_name,
        database=settings.snowflake_database or settings.database_name,
        role=settings.snowflake_role or settings.role_name,
    )
    if settings.snowflake_authenticator:
        kwargs["authenticator"] = settings.snowflake_authenticator
    if settings.snowflake_password:
        kwargs["password"] = settings.snowflake_password

    with snowflake.connector.connect(**{k: v for k, v in kwargs.items() if v}) as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            return cur.fetch_pandas_all()


def _run_bigquery(sql: str, settings: Settings) -> pd.DataFrame:
    try:
        from google.cloud import bigquery
    except ImportError as exc:
        raise WarehouseDriverMissing(
            "google-cloud-bigquery is not installed. "
            "Run `pip install google-cloud-bigquery[pandas]`."
        ) from exc

    client = bigquery.Client(project=settings.bigquery_project or None)
    return client.query(sql).result().to_dataframe()


def _run_redshift(sql: str, settings: Settings) -> pd.DataFrame:
    try:
        import redshift_connector
    except ImportError as exc:
        raise WarehouseDriverMissing(
            "redshift-connector is not installed. Run `pip install redshift-connector`."
        ) from exc

    with redshift_connector.connect(
        host=settings.server_name,
        database=settings.database_name,
        user=settings.redshift_user,
        password=settings.redshift_password,
        port=settings.redshift_port,
    ) as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            return cur.fetch_dataframe()


def _run_odbc(sql: str, settings: Settings) -> pd.DataFrame:
    try:
        import pyodbc
    except ImportError as exc:
        raise WarehouseDriverMissing(
            "pyodbc is not installed. Run `pip install pyodbc`."
        ) from exc

    conn_str = (
        f"DRIVER={{{settings.odbc_driver}}};"
        f"SERVER={settings.server_name};"
        f"DATABASE={settings.database_name};"
        f"UID={settings.odbc_user};"
        f"PWD={settings.odbc_password};"
    )
    with pyodbc.connect(conn_str) as conn:
        return pd.read_sql(sql, conn)

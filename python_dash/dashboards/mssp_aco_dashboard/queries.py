"""SQL queries for the MSSP ACO dashboard."""

from __future__ import annotations

import logging

import pandas as pd

from tuva_dash import run_query
from tuva_dash.config import get_settings

log = logging.getLogger(__name__)

SCHEMA = "semantic_layer"
AHRQ_SCHEMA = "ahrq_measures"


def _safe(sql: str, columns: list[str]) -> pd.DataFrame:
    try:
        return run_query(sql, columns=columns)
    except Exception as exc:
        log.warning("mssp_aco query failed (returning empty): %s", exc)
        return pd.DataFrame(columns=columns)


def load_member_months() -> pd.DataFrame:
    """Member-month spend joined to provider attribution from dim_member_months."""
    s = get_settings()
    sql = f"""
        SELECT
            f.person_id, f.year_month, f.year_nbr, f.member_months,
            f.total_paid, f.medical_paid, f.pharmacy_paid,
            f.normalized_risk_score,
            d.payer, d.payer_attributed_provider,
            d.payer_attributed_provider_practice
        FROM {s.qualified(SCHEMA, 'fact_member_months')} f
        LEFT JOIN {s.qualified(SCHEMA, 'dim_member_months')} d
            ON d.person_id = f.person_id AND d.year_month = f.year_month
    """
    return _safe(sql, ["person_id", "year_month", "year_nbr", "member_months",
                       "total_paid", "medical_paid", "pharmacy_paid",
                       "normalized_risk_score",
                       "payer", "payer_attributed_provider",
                       "payer_attributed_provider_practice"])


def load_dim_member_months() -> pd.DataFrame:
    s = get_settings()
    sql = f"""
        SELECT person_id, year_month, payer,
               payer_attributed_provider,
               payer_attributed_provider_practice,
               custom_attributed_provider
        FROM {s.qualified(SCHEMA, 'dim_member_months')}
    """
    return _safe(sql, ["person_id", "year_month", "payer",
                       "payer_attributed_provider",
                       "payer_attributed_provider_practice",
                       "custom_attributed_provider"])


def load_members() -> pd.DataFrame:
    s = get_settings()
    sql = f"""
        SELECT person_id, first_name, last_name, age, sex,
               birth_date, address, city, state, zip_code, race,
               data_source
        FROM {s.qualified(SCHEMA, 'dim_member')}
    """
    return _safe(sql, ["person_id", "first_name", "last_name", "age", "sex",
                       "birth_date", "address", "city", "state", "zip_code",
                       "race", "data_source"])


def load_member_conditions() -> pd.DataFrame:
    s = get_settings()
    sql = f"""
        SELECT b.person_id, c.condition
        FROM {s.qualified(SCHEMA, 'fact_member_condition_bridge')} b
        LEFT JOIN {s.qualified(SCHEMA, 'dim_condition')} c
            ON c.condition_sk = b.condition_sk
    """
    return _safe(sql, ["person_id", "condition"])


def load_hcc_gaps() -> pd.DataFrame:
    s = get_settings()
    sql = f"SELECT * FROM {s.qualified(SCHEMA, 'fact_hcc_gaps')}"
    return _safe(sql, ["person_id", "hcc_code", "hcc_description", "reason",
                       "contributing_factor", "latest_suspect_date"])


def load_encounters() -> pd.DataFrame:
    s = get_settings()
    sql = f"""
        SELECT
            e.encounter_id, e.person_id, e.year_month,
            e.encounter_start_date, e.encounter_end_date,
            e.facility_name, e.paid_amount, e.allowed_amount,
            e.primary_diagnosis_description,
            eg.encounter_group, et.encounter_type
        FROM {s.qualified(SCHEMA, 'fact_encounters')} e
        LEFT JOIN {s.qualified(SCHEMA, 'dim_encounter_group')} eg
            ON eg.encounter_group_sk = e.encounter_group_sk
        LEFT JOIN {s.qualified(SCHEMA, 'dim_encounter_type')} et
            ON et.encounter_type_sk = e.encounter_type_sk
    """
    return _safe(sql, ["encounter_id", "person_id", "year_month",
                       "encounter_start_date", "encounter_end_date",
                       "facility_name", "paid_amount", "allowed_amount",
                       "primary_diagnosis_description",
                       "encounter_group", "encounter_type"])


def load_pqi_rate() -> pd.DataFrame:
    s = get_settings()
    sql = f"SELECT * FROM {s.qualified(AHRQ_SCHEMA, 'pqi_rate')}"
    return _safe(sql, ["data_source", "year_number", "pqi_number",
                       "denom_count", "num_count", "rate_per_100_thousand"])


def load_pqi_denom() -> pd.DataFrame:
    s = get_settings()
    sql = f"SELECT * FROM {s.qualified(AHRQ_SCHEMA, 'pqi_denom_long')}"
    return _safe(sql, ["year_number", "person_id", "data_source", "pqi_number"])

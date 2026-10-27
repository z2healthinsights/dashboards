"""Member condition cohorts on the Tuva semantic layer 1.0.

Semantic layer 1.0 retired `dim_condition` and `fact_member_condition_bridge`
together with Tuva's chronic-condition definitions, and ships no replacement
grouping. The nearest person-level condition list it does ship is the CMS-HCC
disease factors in `fact_risk_factors`, so the dashboards read conditions from
there: one row per member and HCC disease category, across every payment year
and model version in the table.

This is a change of meaning, not a rename. HCC categories cover only the
conditions the CMS-HCC model pays for, after its hierarchies (a member with
diabetes with complications does not also carry diabetes without), and only
for members the model scored. Every page that shows these labels them as
CMS-HCC conditions.
"""

from __future__ import annotations

from tuva_dash.config import Settings

SCHEMA = "semantic_layer"
TABLE = "fact_risk_factors"
SOURCE_TABLE = f"{SCHEMA}.{TABLE}"
COLUMNS = ["person_id", "condition"]

# Short label for page headings and filter captions.
LABEL = "CMS-HCC conditions"


def member_conditions_sql(s: Settings) -> str:
    """One row per member and CMS-HCC disease category, as `(person_id, condition)`."""
    return f"""
        SELECT DISTINCT person_id, risk_factor_description AS condition
        FROM {s.qualified(SCHEMA, TABLE)}
        WHERE factor_type = 'Disease'
          AND risk_factor_description IS NOT NULL
    """

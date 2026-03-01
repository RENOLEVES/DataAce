import pandas as pd
import numpy as np
from models.schemas import ScanReport, ScanIssue


def scan_dataframe(df: pd.DataFrame) -> ScanReport:
    """
    Run a rule-based scan over the dataframe and return a structured report
    of detected data quality issues.
    """
    issues: list[ScanIssue] = []

    for col in df.columns:
        series = df[col]

        # ── Nulls ──────────────────────────────────────────────────────────────
        null_count = int(series.isna().sum())
        if null_count > 0:
            pct = null_count / len(df)
            severity = "critical" if pct > 0.5 else "warning" if pct > 0.1 else "info"
            issues.append(ScanIssue(
                column=col,
                issue_type="missing_values",
                severity=severity,
                description=f"{null_count} missing values ({pct:.1%} of rows)",
                affected_count=null_count,
                suggestion="fill_nulls or drop_rows_where_null",
            ))

        # ── Pseudo-nulls ───────────────────────────────────────────────────────
        if series.dtype == object:
            pseudo = ["N/A", "n/a", "NA", "na", "none", "None", "NULL", "null", "-", "?", ""]
            pseudo_count = int(series.isin(pseudo).sum())
            if pseudo_count > 0:
                issues.append(ScanIssue(
                    column=col,
                    issue_type="pseudo_nulls",
                    severity="warning",
                    description=f"{pseudo_count} pseudo-null values (e.g. 'N/A', 'none', '-')",
                    affected_count=pseudo_count,
                    suggestion="replace_pseudo_nulls",
                ))

        # ── Whitespace ─────────────────────────────────────────────────────────
        if series.dtype == object:
            stripped = series.dropna().str.strip()
            ws_count = int((series.dropna() != stripped).sum())
            if ws_count > 0:
                issues.append(ScanIssue(
                    column=col,
                    issue_type="leading_trailing_whitespace",
                    severity="info",
                    description=f"{ws_count} values have leading or trailing whitespace",
                    affected_count=ws_count,
                    suggestion="strip_whitespace",
                ))

        # ── Duplicates (whole-row, reported once under a sentinel column) ──────
        # Handled below outside the column loop.

        # ── Outliers ───────────────────────────────────────────────────────────
        if pd.api.types.is_numeric_dtype(series) and series.notna().sum() > 4:
            Q1 = series.quantile(0.25)
            Q3 = series.quantile(0.75)
            IQR = Q3 - Q1
            if IQR > 0:
                lower = Q1 - 1.5 * IQR
                upper = Q3 + 1.5 * IQR
                outlier_count = int(((series < lower) | (series > upper)).sum())
                if outlier_count > 0:
                    issues.append(ScanIssue(
                        column=col,
                        issue_type="outliers",
                        severity="warning",
                        description=f"{outlier_count} outlier values detected outside IQR bounds",
                        affected_count=outlier_count,
                        suggestion="cap_outliers",
                    ))

        # ── Mixed types / numeric stored as string ─────────────────────────────
        if series.dtype == object:
            non_null = series.dropna()
            if len(non_null) > 0:
                numeric_like = pd.to_numeric(non_null, errors="coerce").notna().sum()
                ratio = numeric_like / len(non_null)
                if 0.5 < ratio < 1.0:
                    issues.append(ScanIssue(
                        column=col,
                        issue_type="mixed_types",
                        severity="warning",
                        description=f"Column appears mostly numeric but is stored as text ({ratio:.0%} parseable)",
                        affected_count=int(len(non_null) - numeric_like),
                        suggestion="convert_to_numeric",
                    ))
                elif ratio == 1.0 and len(non_null) > 0:
                    issues.append(ScanIssue(
                        column=col,
                        issue_type="numeric_as_string",
                        severity="info",
                        description="Column contains only numeric values but is stored as text",
                        affected_count=int(len(non_null)),
                        suggestion="convert_to_numeric",
                    ))

        # ── Excel date serials ─────────────────────────────────────────────────
        if pd.api.types.is_numeric_dtype(series):
            non_null = series.dropna()
            if len(non_null) > 0 and non_null.between(20000, 60000).mean() > 0.8:
                issues.append(ScanIssue(
                    column=col,
                    issue_type="excel_date_serial",
                    severity="warning",
                    description="Column values look like Excel date serial numbers",
                    affected_count=int(len(non_null)),
                    suggestion="convert_excel_dates",
                ))

    # ── Duplicate rows (whole-dataframe check) ─────────────────────────────────
    dup_count = int(df.duplicated().sum())
    if dup_count > 0:
        issues.append(ScanIssue(
            column="ALL",
            issue_type="duplicate_rows",
            severity="warning",
            description=f"{dup_count} exact duplicate rows detected",
            affected_count=dup_count,
            suggestion="remove_duplicates",
        ))

    return ScanReport(
        total_rows=len(df),
        total_columns=len(df.columns),
        issues=issues,
    )
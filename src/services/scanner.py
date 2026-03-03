import pandas as pd
import numpy as np
from models.schemas import ScanReport, ScanIssue


# Core scanning logic to analyze the DataFrame and identify potential issues 
# This is called once at file upload time to generate the initial scan report, 
# which is cached in the session for later use during instruction parsing and clarification
def scan_dataframe(df: pd.DataFrame) -> ScanReport:

    # Create a list to hold detected issues, which will be included in the scan report
    # - column: the column name where the issue was found (or "ALL" for whole-dataframe issues)
    # - issue_type: a short code for the type of issue
    # - severity: "info", "warning", or "critical" based on how severe the issue is
    # - description: a human-readable explanation of the issue
    # - affected_count: how many rows are affected by this issue
    issues: list[ScanIssue] = []

    # Loop through each column to check for various issues, such as missing values, pseudo-nulls 
    # whitespace issues, outliers, mixed types, and Excel date serials
    for col in df.columns:

        # 2D data series
        series = df[col]

        # All nulls
        null_count = int(series.isna().sum())

        # If more than 10% of values are missing, it's a warning
        # if more than 50%, it's critical
        # Otherwise, it's just info
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

        # Pseudo-nulls (e.g. "N/A", "none", "-", etc.) that should be treated as nulls. Only for object columns
        if series.dtype == object:

            # List any common pseudo-null values and count how many there are
            # This can indicate data quality issues where missing values were not properly encoded as nulls
            pseudo = ["N/A", "n/a", "NA", "na", "none", "None", "NULL", "null", "-", "?", ""]

            # All nulls
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

        # Leading/trailing whitespace in string columns, which can cause issues with matching and grouping. Only for object columns
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
        # Handled below outside the column loop

        # Calculate outliers using the IQR method for numeric columns with enough non-null values (Only for numeric columns)
        if pd.api.types.is_numeric_dtype(series) and series.notna().sum() > 4:

            # 0.25 and 0.75 quantiles to define the IQR range
            Q1 = series.quantile(0.25)
            Q3 = series.quantile(0.75)

            # IQR interquartile range
            IQR = Q3 - Q1

            # If IQR is 0, it means all values are the same, so we skip outlier detection to avoid false positives
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

        # Mixed types in a column, which can indicate data quality issues and may require type conversion (only for object columns)
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

        # Excel date serial numbers, which are numeric but represent dates. 
        # This can cause issues if not converted to proper date format (only for numeric columns)
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

    # Duplicate rows. 
    # This can indicate data quality issues and may require deduplication
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
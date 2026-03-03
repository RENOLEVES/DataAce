import math

import pandas as pd
import numpy as np
import re
from models.schemas import Operation


class ExecutionResult:
    def __init__(self):
        self.success = True
        self.changes: list[str] = []
        self.warnings: list[str] = []
        self.errors: list[str] = []


def execute_operations(df: pd.DataFrame, operations: list[Operation]) -> tuple[pd.DataFrame, ExecutionResult]:
    result = ExecutionResult()
    df = df.copy()

    for op in operations:
        try:
            df, change = _dispatch(df, op)
            if change:
                result.changes.append(change)
        except Exception as e:
            result.warnings.append(f"Could not apply '{op.operation}' on column '{op.column}': {str(e)}")

    return df, result


def _dispatch(df: pd.DataFrame, op: Operation) -> tuple[pd.DataFrame, str]:
    handlers = {
        "fill_nulls": _fill_nulls,
        "remove_duplicates": _remove_duplicates,
        "convert_to_datetime": _convert_to_datetime,
        "convert_to_numeric": _convert_to_numeric,
        "standardize_case": _standardize_case,
        "strip_whitespace": _strip_whitespace,
        "replace_pseudo_nulls": _replace_pseudo_nulls,
        "drop_column": _drop_column,
        "drop_rows_where_null": _drop_rows_where_null,
        "rename_column": _rename_column,
        "cap_outliers": _cap_outliers,
        "convert_excel_dates": _convert_excel_dates,
        "replace_string": _replace_string,
        "custom_code": _custom_code,
    }

    handler = handlers.get(op.operation)
    if not handler:
        raise ValueError(f"Unknown operation: {op.operation}")

    return handler(df, op)


# ── Individual operation handlers ──────────────────────────────────────────────

def _fill_nulls(df: pd.DataFrame, op: Operation) -> tuple[pd.DataFrame, str]:
    columns = _resolve_columns(df, op.column)
    strategy = op.strategy or "median"
    filled = 0

    for col in columns:
        null_count = df[col].isna().sum()
        if null_count == 0:
            continue

        if strategy == "median" and pd.api.types.is_numeric_dtype(df[col]):
            df[col] = df[col].fillna(df[col].median())
            filled += null_count
        elif strategy == "mean" and pd.api.types.is_numeric_dtype(df[col]):
            df[col] = df[col].fillna(df[col].mean())
            filled += null_count
        elif strategy == "mode":
            mode_val = df[col].mode()
            if len(mode_val) > 0:
                df[col] = df[col].fillna(mode_val[0])
                filled += null_count
        elif strategy == "drop":
            before = len(df)
            df = df.dropna(subset=[col])
            filled += before - len(df)
        elif op.value is not None:
            df[col] = df[col].fillna(op.value)
            filled += null_count

    return df, f"Filled {filled} null values using strategy '{strategy}' across {len(columns)} column(s)."


def _remove_duplicates(df: pd.DataFrame, op: Operation) -> tuple[pd.DataFrame, str]:
    before = len(df)
    # scope is informational only for now; "exact" is the only supported mode.
    df = df.drop_duplicates()
    removed = before - len(df)
    return df, f"Removed {removed} duplicate rows."


def _convert_to_datetime(df: pd.DataFrame, op: Operation) -> tuple[pd.DataFrame, str]:
    col = op.column
    if col not in df.columns:
        raise ValueError(f"Column '{col}' not found.")

    fmt = op.format  # optional explicit format

    # Use pd.api.types rather than string comparison against dtype names,
    # which is unreliable across numpy versions.
    if pd.api.types.is_numeric_dtype(df[col]):
        df[col] = pd.TimedeltaIndex(df[col], unit="d") + pd.Timestamp("1899-12-30")
        return df, f"Converted Excel date serials in '{col}' to datetime."

    converted = pd.to_datetime(df[col], format=fmt, errors="coerce")
    failed = int(converted.isna().sum()) - int(df[col].isna().sum())
    df[col] = converted

    msg = f"Converted '{col}' to datetime."
    if failed > 0:
        msg += f" {failed} values could not be parsed and were set to null."

    return df, msg


def _convert_to_numeric(df: pd.DataFrame, op: Operation) -> tuple[pd.DataFrame, str]:
    col = op.column
    if col not in df.columns:
        raise ValueError(f"Column '{col}' not found.")

    converted = pd.to_numeric(df[col], errors="coerce")
    failed = int(converted.isna().sum()) - int(df[col].isna().sum())
    df[col] = converted

    msg = f"Converted '{col}' to numeric."
    if failed > 0:
        msg += f" {failed} non-numeric values were set to null."

    return df, msg


def _standardize_case(df: pd.DataFrame, op: Operation) -> tuple[pd.DataFrame, str]:
    columns = _resolve_columns(df, op.column)
    to = op.to or "lower"
    count = 0

    for col in columns:
        if df[col].dtype != object:
            continue
        if to == "lower":
            df[col] = df[col].str.lower()
        elif to == "upper":
            df[col] = df[col].str.upper()
        elif to == "title":
            df[col] = df[col].str.title()
        count += 1

    return df, f"Standardized casing to '{to}' for {count} column(s)."


def _strip_whitespace(df: pd.DataFrame, op: Operation) -> tuple[pd.DataFrame, str]:
    columns = _resolve_columns(df, op.column)
    count = 0

    for col in columns:
        if df[col].dtype == object:
            df[col] = df[col].str.strip()
            count += 1

    return df, f"Stripped leading/trailing whitespace from {count} column(s)."


def _replace_pseudo_nulls(df: pd.DataFrame, op: Operation) -> tuple[pd.DataFrame, str]:
    columns = _resolve_columns(df, op.column)
    pseudo = ["N/A", "n/a", "NA", "na", "none", "None", "NULL", "null", "-", "?", ""]
    total = 0

    for col in columns:
        if df[col].dtype == object:
            mask = df[col].isin(pseudo)
            total += mask.sum()
            df.loc[mask, col] = np.nan

    return df, f"Replaced {total} pseudo-null values (e.g. 'N/A', 'none') with actual nulls."


def _drop_column(df: pd.DataFrame, op: Operation) -> tuple[pd.DataFrame, str]:
    col = op.column
    if col not in df.columns:
        raise ValueError(f"Column '{col}' not found.")
    df = df.drop(columns=[col])
    return df, f"Dropped column '{col}'."


def _drop_rows_where_null(df: pd.DataFrame, op: Operation) -> tuple[pd.DataFrame, str]:
    col = op.column
    before = len(df)

    if col and col.lower() != "all":
        if col not in df.columns:
            raise ValueError(f"Column '{col}' not found.")
        df = df.dropna(subset=[col])
    else:
        df = df.dropna()

    removed = before - len(df)
    target = f"column '{col}'" if col and col.lower() != "all" else "any column"
    return df, f"Dropped {removed} rows with null values in {target}."


def _rename_column(df: pd.DataFrame, op: Operation) -> tuple[pd.DataFrame, str]:
    if not op.column or not op.value:
        raise ValueError("rename_column requires 'column' (old name) and 'value' (new name).")
    df = df.rename(columns={op.column: str(op.value)})
    return df, f"Renamed column '{op.column}' to '{op.value}'."


def _cap_outliers(df: pd.DataFrame, op: Operation) -> tuple[pd.DataFrame, str]:
    columns = _resolve_columns(df, op.column)
    total_capped = 0

    for col in columns:
        if not pd.api.types.is_numeric_dtype(df[col]):
            continue
        Q1 = df[col].quantile(0.25)
        Q3 = df[col].quantile(0.75)
        IQR = Q3 - Q1
        lower = Q1 - 1.5 * IQR
        upper = Q3 + 1.5 * IQR
        capped = int(((df[col] < lower) | (df[col] > upper)).sum())
        df[col] = df[col].clip(lower=lower, upper=upper)
        total_capped += capped

    return df, f"Capped {total_capped} outlier values using IQR method across {len(columns)} column(s)."


def _convert_excel_dates(df: pd.DataFrame, op: Operation) -> tuple[pd.DataFrame, str]:
    col = op.column
    if col not in df.columns:
        raise ValueError(f"Column '{col}' not found.")
    df[col] = pd.TimedeltaIndex(df[col], unit="d") + pd.Timestamp("1899-12-30")
    return df, f"Converted Excel date serials in '{col}' to datetime."


# ── Helpers ────────────────────────────────────────────────────────────────────

def _resolve_columns(df: pd.DataFrame, column: str | None) -> list[str]:
    if not column or column.lower() == "all":
        return list(df.columns)
    if column not in df.columns:
        raise ValueError(f"Column '{column}' not found.")
    return [column]

def _replace_string(df: pd.DataFrame, op: Operation) -> tuple[pd.DataFrame, str]:
    col = op.column
    if col not in df.columns:
        raise ValueError(f"Column '{col}' not found.")
    
    old_val = str(op.value) if op.value is not None else ""
    new_val = str(op.to) if op.to is not None else ""
    
    count = int(df[col].astype(str).str.contains(old_val, regex=False).sum())
    df[col] = df[col].astype(str).str.replace(old_val, new_val, regex=False)
    
    return df, f"Replaced '{old_val}' with '{new_val}' in '{col}' ({count} occurrences)."

# custom_code is handled separately since it doesn't fit the standard operation pattern
def _custom_code(df: pd.DataFrame, op: Operation) -> tuple[pd.DataFrame, str]:
    code = op.code
    if not code:
        return df, "Skipped custom_code: no code provided by model."

    print(f"[custom_code] executing: {code}")
    # Safety check — block dangerous operations
    forbidden = ["import", "open(", "exec(", "eval(", "__", "os.", "sys.", "subprocess"]
    for word in forbidden:
        if word in code:
            raise ValueError(f"Forbidden expression in code: '{word}'")

    local_vars = {
    "df": df,
    "pd": pd,
    "np": np,
    "math": math,
    "int": int,
    "float": float,
    "str": str,
    "len": len,
    "list": list,
    "dict": dict,
    "range": range,
    "enumerate": enumerate,
    "zip": zip,
    "re": re,
    }
    
    exec(code, {"__builtins__": {}}, local_vars)
    df = local_vars["df"]

    description = op.description or f"Executed custom code: {code}"
    return df, description
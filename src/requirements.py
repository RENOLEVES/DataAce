import io
import pandas as pd

def parse_file(filename: str, content: bytes) -> pd.DataFrame:
    ext = filename.rsplit(".", 1)[-1].lower()

    if ext == "csv":
        return pd.read_csv(io.BytesIO(content))
    elif ext in ["xls", "xlsx"]:
        return pd.read_excel(io.BytesIO(content))
    elif ext == "json":
        return pd.read_json(io.BytesIO(content))
    else:
        raise ValueError(f"Unsupported file type: .{ext}")


def serialize_file(df: pd.DataFrame, filename: str, extension: str) -> tuple[bytes, str]:
    buffer = io.BytesIO()

    if extension == "csv":
        df.to_csv(buffer, index=False)
        media_type = "text/csv"
    elif extension in ["xls", "xlsx"]:
        df.to_excel(buffer, index=False)
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    elif extension == "json":
        df.to_json(buffer, orient="records", indent=2)
        media_type = "application/json"
    else:
        df.to_csv(buffer, index=False)
        media_type = "text/csv"

    buffer.seek(0)
    return buffer.read(), media_type
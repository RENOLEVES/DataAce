import uuid
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse

from utils.session_manager import session_manager
from utils.file_parser import parse_file
from services.scanner import scan_dataframe

router = APIRouter(prefix="/upload", tags=["upload"])


@router.post("")
async def upload_file(file: UploadFile = File(...)):
    """
    Upload a CSV, Excel, or JSON file.
    Returns a session_id and a scan report of detected issues.
    """
    allowed_extensions = {"csv", "xls", "xlsx", "json"}
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""

    if ext not in allowed_extensions:
        raise HTTPException(status_code=400, detail=f"Unsupported file type '.{ext}'. Allowed: {allowed_extensions}")

    content = await file.read()

    try:
        df = parse_file(file.filename, content)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Could not parse file: {str(e)}")

    session = session_manager.create()
    session.df = df
    session.original_filename = file.filename
    session.file_extension = ext

    scan_report = scan_dataframe(df)

    # Summarize scan for the opening assistant message
    if scan_report.issues:
        critical = [i for i in scan_report.issues if i.severity == "critical"]
        warnings = [i for i in scan_report.issues if i.severity == "warning"]
        info = [i for i in scan_report.issues if i.severity == "info"]

        summary_lines = [
            f"I've scanned your file **{file.filename}** ({scan_report.total_rows} rows × {scan_report.total_columns} columns).",
            f"Here's what I found:",
        ]
        if critical:
            summary_lines.append(f"🔴 **Critical ({len(critical)}):** " + "; ".join(f"{i.column} — {i.description}" for i in critical[:3]))
        if warnings:
            summary_lines.append(f"🟡 **Warnings ({len(warnings)}):** " + "; ".join(f"{i.column} — {i.description}" for i in warnings[:3]))
        if info:
            summary_lines.append(f"🔵 **Info ({len(info)}):** " + "; ".join(f"{i.column} — {i.description}" for i in info[:3]))

        summary_lines.append("\nWhat would you like me to fix? You can give specific instructions like: *'fill nulls with median, remove duplicates, standardize email to lowercase'*.")
        opening_message = "\n".join(summary_lines)
    else:
        opening_message = (
            f"I've scanned **{file.filename}** ({scan_report.total_rows} rows × {scan_report.total_columns} columns) "
            f"and found no obvious issues. What cleaning would you like to apply?"
        )

    session.add_message("assistant", opening_message)

    return JSONResponse({
        "session_id": session.id,
        "filename": file.filename,
        "rows": scan_report.total_rows,
        "columns": scan_report.total_columns,
        "scan_report": {
            "total_rows": scan_report.total_rows,
            "total_columns": scan_report.total_columns,
            "issues": [i.model_dump() for i in scan_report.issues],
        },
        "opening_message": opening_message,
    })
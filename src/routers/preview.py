import math
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from utils.session_manager import session_manager

router = APIRouter(prefix="/preview", tags=["preview"])

PAGE_SIZE = 50


@router.get("/{session_id}")
async def preview(session_id: str, page: int = Query(0, ge=0)):
    session = session_manager.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    df = session.cleaned_df if session.cleaned_df is not None else session.df
    if df is None:
        raise HTTPException(status_code=400, detail="No data loaded.")

    start = page * PAGE_SIZE
    end = start + PAGE_SIZE
    page_df = df.iloc[start:end]

    # Convert to records then sanitize NaN → None for JSON compliance
    rows = page_df.to_dict(orient="records")
    rows = [
        {k: (None if isinstance(v, float) and math.isnan(v) else v) for k, v in row.items()}
        for row in rows
    ]

    return JSONResponse({
        "columns": list(df.columns),
        "rows": rows,
        "total_rows": len(df),
        "preview_rows": len(rows),
        "page": page,
        "page_size": PAGE_SIZE,
        "has_more": end < len(df),
    })
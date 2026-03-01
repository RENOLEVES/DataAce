from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from utils.session_manager import session_manager
from utils.file_parser import serialize_file

router = APIRouter(prefix="/download", tags=["download"])


@router.get("/{session_id}")
async def download_cleaned_file(session_id: str):
    """
    Download the cleaned file for a given session.
    Returns the file in the same format it was uploaded.
    """
    session = session_manager.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    if session.cleaned_df is None:
        raise HTTPException(status_code=400, detail="No cleaned file available yet. Please send cleaning instructions first.")

    file_bytes, media_type = serialize_file(
        df=session.cleaned_df,
        filename=session.original_filename,
        extension=session.file_extension,
    )

    clean_name = session.original_filename.rsplit(".", 1)
    download_name = f"{clean_name[0]}_cleaned.{session.file_extension}"

    return Response(
        content=file_bytes,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{download_name}"'},
    )
import json
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from utils.session_manager import session_manager
from services.notebook_generator import generate_notebook

router = APIRouter(prefix="/notebook", tags=["notebook"])


@router.get("/{session_id}")
async def download_notebook(session_id: str):
    """
    Generate and download a Jupyter notebook (.ipynb) that reproduces
    all cleaning operations applied in this session.
    Only available after at least one cleaning operation has been executed.
    """
    session = session_manager.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    if not session.applied_operations:
        raise HTTPException(
            status_code=400,
            detail="No operations have been applied yet. Clean your data first."
        )

    notebook = generate_notebook(
        operations=session.applied_operations,
        original_filename=session.original_filename,
        file_extension=session.file_extension,
    )

    notebook_bytes = json.dumps(notebook, indent=2).encode("utf-8")

    base_name = session.original_filename.rsplit(".", 1)[0]
    notebook_filename = f"{base_name}_cleaning_pipeline.ipynb"

    return Response(
        content=notebook_bytes,
        media_type="application/x-ipynb+json",
        headers={"Content-Disposition": f'attachment; filename="{notebook_filename}"'},
    )
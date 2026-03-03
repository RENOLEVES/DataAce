from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from utils.session_manager import session_manager

router = APIRouter(prefix="/history", tags=["history"])


# For undo/redo, we maintain a history stack of DataFrame states in the session. 
# When the user performs an operation, we save a snapshot of the current state before applying the changes. 
# The undo endpoint pops the last state from the history stack and restores it, while the redo endpoint 
# re-applies a state that was undone.
@router.post("/undo/{session_id}")
async def undo(session_id: str):
    session = session_manager.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    if not session.df_history:
        raise HTTPException(status_code=400, detail="Nothing to undo.")

    session.undo()

    return JSONResponse({
        "session_id": session_id,
        "message": "Undo successful.",
        "steps_available": len(session.df_history),
        "download_url": f"/download/{session_id}",
        "operation_history": session.operation_history,
    })


# The redo endpoint allows the user to re-apply an operation that was undone. 
# It checks if there are any future states available, and if so, it restores the next state in the redo stack.
@router.post("/redo/{session_id}")
async def redo(session_id: str):
    session = session_manager.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    # if there is no future state to redo, it means the user is already at the latest point in the history, so we can't redo anything.
    if not session.df_future:
        raise HTTPException(status_code=400, detail="Nothing to redo.")

    # If we have a future state, we can redo it by popping it from the redo stack and making it the current cleaned DataFrame.
    session.redo()

    return JSONResponse({
        "session_id": session_id,
        "message": "Redo successful.",
        "steps_available": len(session.df_history),
        "download_url": f"/download/{session_id}",
        "operation_history": session.operation_history,
    })


# Get the list of all history steps for a session, including descriptions and whether undo/redo is available.
@router.get("/steps/{session_id}")
async def get_steps(session_id: str):
    session = session_manager.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    return JSONResponse({
        "session_id": session_id,
        "steps": session.operation_history,
        "can_undo": len(session.df_history) > 0,
        "can_redo": len(session.df_future) > 0,
    })
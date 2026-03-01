from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from models.schemas import ChatRequest, ChatResponse
from utils.session_manager import session_manager
from services.scanner import scan_dataframe
from services.executor import execute_operations
from services.ai_service import parse_instructions, generate_clarifying_question, generate_summary

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Send a message in the context of an active session.
    The app will parse the instruction, ask for clarification if needed,
    or execute the operations and signal that a file is ready to download.
    """
    session = session_manager.get(request.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found. Please upload a file first.")

    if session.df is None:
        raise HTTPException(status_code=400, detail="No file loaded in this session.")

    user_message = request.message.strip()
    session.add_message("user", user_message)

    # Run local scan if not already done
    scan_report = scan_dataframe(session.df)

    # Ask Claude to parse the instruction
    parsed = parse_instructions(
        user_message=user_message,
        scan_report=scan_report,
        conversation_history=session.get_history()[:-1],  # exclude current user msg, already in system
    )

    # If there are ambiguities — ask a clarifying question
    if parsed.ambiguities and not parsed.operations:
        clarifying_q = generate_clarifying_question(parsed.ambiguities, scan_report)
        session.add_message("assistant", clarifying_q)
        return ChatResponse(
            session_id=session.id,
            reply=clarifying_q,
            download_ready=False,
        )

    # If no operations could be parsed at all
    if not parsed.operations:
        reply = (
            "I couldn't identify a specific cleaning operation from your message. "
            "Try something like: *'fill nulls with median, remove duplicates, convert date_col to datetime'*."
        )
        session.add_message("assistant", reply)
        return ChatResponse(session_id=session.id, reply=reply, download_ready=False)

    # Execute operations
    cleaned_df, exec_result = execute_operations(session.df, parsed.operations)
    session.cleaned_df = cleaned_df

    # Record what was actually applied for notebook generation
    session.applied_operations.extend([op.model_dump() for op in parsed.operations])

    # Generate a friendly summary
    summary = generate_summary(exec_result.changes, exec_result.warnings)
    summary += "\n\nYour cleaned file is ready to download."

    session.add_message("assistant", summary)

    return ChatResponse(
        session_id=session.id,
        reply=summary,
        download_ready=True,
        download_url=f"/download/{session.id}",
    )
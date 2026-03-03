from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from models.schemas import ChatRequest, ChatResponse
from utils.session_manager import session_manager
from services.scanner import scan_dataframe
from services.executor import execute_operations
from services.ai_service import parse_instructions, generate_clarifying_question, generate_summary

router = APIRouter(prefix="/chat", tags=["chat"])


# Send a chat message with cleaning instructions, get back a reply and (if applicable) a download link for the cleaned file.
# Always to check if a session is valid and has a file loaded, but we allow chatting even if the scan report is missing 
# (it will be generated on demand) because the user might want to ask questions before uploading.
# The main flow is:
# 1. Validate session and file loaded.
# 2. Parse the user's instruction using an LLM, passing in the scan report and conversation history for context.
# 3. If the instruction is ambiguous, generate a clarifying question and return it without executing anything.
# 4. If the instruction is clear, execute the parsed operations on the DataFrame.
# 5. Generate a friendly summary of the changes and any warnings, and return it along with a download link for the cleaned file.
@router.post("", response_model=ChatResponse)
async def chat(request: ChatRequest):
    # Validate session and file presence
    session = session_manager.get(request.session_id)
    # Note: we allow chatting even if no file is loaded, because the user might be asking for help or 
    # instructions before uploading. The main thing is that the session must exist.
    if not session:
        raise HTTPException(status_code=404, detail="Session not found. Please upload a file first.")

    if session.df is None:
        raise HTTPException(status_code=400, detail="No file loaded in this session.")

    user_message = request.message.strip()

    # Use cached scan report from upload; only recompute if missing.
    # This avoids redundant work and ensures consistency with the opening message.
    if session.scan_report is None:
        session.scan_report = scan_dataframe(session.df)
    scan_report = session.scan_report

    # # Pass history BEFORE adding the current user message — ai_service appends
    # # it itself as the final user turn, so we must not duplicate it here.
    # history_snapshot = session.get_history()

    # Now record the user message in session history.
    session.add_message("user", user_message)

    # Ask LLM to parse the instruction
    parsed = parse_instructions(
        user_message=user_message,
        scan_report=scan_report,
        conversation_history=[],
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

    # Take a snapshot before applying changes, for undo/redo functionality. We do this even if there are warnings,
    # because the user might want to undo if they don't like the results. 
    # The description is just the user's message, but it could be enhanced to include more context if needed.
    session.snapshot(description=user_message)

    # Execute operations
    source_df = session.cleaned_df if session.cleaned_df is not None else session.df
    cleaned_df, exec_result = execute_operations(source_df, parsed.operations)
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
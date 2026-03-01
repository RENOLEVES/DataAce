import os
import json
from urllib import response

from models.schemas import Operation, ParsedInstructions, ScanReport

# import anthropic
# client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

from openai import OpenAI
client = OpenAI(base_url="http://localhost:11434/v1", api_key="ollama")

SUPPORTED_OPERATIONS = """
Supported operations:
- fill_nulls: column (or "all"), strategy ("median"|"mean"|"mode"|"drop"), value (fixed value)
- remove_duplicates: scope ("exact")
- convert_to_datetime: column, format (optional, e.g. "%Y-%m-%d")
- convert_to_numeric: column
- standardize_case: column (or "all"), to ("lower"|"upper"|"title")
- strip_whitespace: column (or "all")
- replace_pseudo_nulls: column (or "all")
- drop_column: column
- drop_rows_where_null: column (or "all")
- rename_column: column (old name), value (new name)
- cap_outliers: column (or "all")
- convert_excel_dates: column
"""


def parse_instructions(user_message: str, scan_report: ScanReport | None, conversation_history: list[dict]) -> ParsedInstructions:
    """
    Ask Claude to convert the user's natural language instruction into structured operations.
    Returns operations + any ambiguities that need clarification.
    """
    scan_context = ""
    if scan_report:
        issues_summary = "\n".join([
            f"- [{i.severity.upper()}] Column '{i.column}': {i.issue_type} — {i.description}"
            for i in scan_report.issues
        ])
        scan_context = f"""
        The data has already been scanned. Here is what was found:
        Total rows: {scan_report.total_rows}
        Total columns: {scan_report.total_columns}
        Issues detected:
        {issues_summary}
        """

    system_prompt = f"""You are a data cleaning assistant. Your job is to parse user instructions into structured cleaning operations.

    {SUPPORTED_OPERATIONS}

    {scan_context}

    Return ONLY valid JSON in this exact format:
    {{
    "operations": [
        {{
        "operation": "operation_name",
        "column": "column_name_or_all_or_null",
        "strategy": "strategy_or_null",
        "format": "format_or_null",
        "value": "value_or_null",
        "scope": "scope_or_null",
        "to": "to_or_null"
        }}
    ],
    "ambiguities": ["list of things that are unclear and need user clarification"]
    }}

    Rules:
    - If the instruction is clear, return operations with empty ambiguities list.
    - If something is ambiguous (e.g. user says "fix nulls" without specifying strategy), add it to ambiguities.
    - Only add ambiguities that genuinely block execution. Make sensible defaults where possible.
    - Never return both operations and ambiguities for the same issue — either handle it or ask.
    - If instruction references a column not in the scan, add it as ambiguity.
    """

    messages = conversation_history + [{"role": "user", "content": user_message}]


    ## for authropic client:
    # response = client.messages.create(
    #     model="claude-sonnet-4-6",
    #     max_tokens=1000,
    #     system=system_prompt,
    #     messages=messages,
    # )

    # raw = response.content[0].text.strip()

    response = client.chat.completions.create(
        model="llama3.2",
        max_tokens=1000,
        messages=[{"role": "system", "content": system_prompt}] + messages,
    )
    raw = response.choices[0].message.content.strip()

    # Strip markdown fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    parsed = json.loads(raw)
    operations = [Operation(**op) for op in parsed.get("operations", [])]
    ambiguities = parsed.get("ambiguities", [])

    return ParsedInstructions(operations=operations, ambiguities=ambiguities)

# This function generates a clarifying question when the user's instruction is ambiguous.
# It uses the list of ambiguities identified by parse_instructions and the scan report 
# context to ask a specific question that will help resolve the ambiguity.
def generate_clarifying_question(ambiguities: list[str], scan_report: ScanReport | None) -> str:
    """
    Given a list of ambiguities, generate ONE clear, specific clarifying question for the user.
    """
    scan_context = ""
    if scan_report:
        cols = ", ".join(set(i.column for i in scan_report.issues if i.column != "ALL"))
        scan_context = f"The dataset has columns with issues: {cols}."

    prompt = f"""You are a data cleaning assistant. The user gave an instruction that has the following ambiguities:

    {chr(10).join(f'- {a}' for a in ambiguities)}

    {scan_context}

    Generate ONE clear, specific clarifying question to resolve the most critical ambiguity.
    - Keep it short and direct.
    - Offer 2-3 concrete options where possible.
    - Do not ask multiple questions.
    - Do not explain yourself, just ask the question.
    """

    # for anthropic client:
    # response = client.messages.create(
    #     model="claude-sonnet-4-6",
    #     max_tokens=200,
    #     messages=[{"role": "user", "content": prompt}],
    # )


    response = client.chat.completions.create(
        model="llama3.2",
        max_tokens=1000,
        messages=[{"role": "system", "content": prompt}],
    )

    return response.choices[0].message.content.strip()


# This function is used to generate a human-friendly summary of the changes and warnings after executing operations.
# used in chat.py to create a nice assistant reply.
def generate_summary(changes: list[str], warnings: list[str]) -> str:
    """
    Generate a short human-friendly summary of what was done.
    """
    if not changes and not warnings:
        return "No changes were applied."

    changes_text = "\n".join(f"- {c}" for c in changes)
    warnings_text = "\n".join(f"- ⚠️ {w}" for w in warnings) if warnings else ""

    prompt = f"""Summarize these data cleaning actions in 2-3 friendly sentences for a data analyst.
    Be concise, mention key numbers, and note any warnings.

    Changes made:
    {changes_text}

    {f"Warnings:{chr(10)}{warnings_text}" if warnings_text else ""}

    Do not use bullet points. Write in plain prose."""

    # response = client.messages.create(
    #     model="claude-sonnet-4-6",
    #     max_tokens=200,
    #     messages=[{"role": "user", "content": prompt}],
    # )

    response = client.chat.completions.create(
        model="llama3.2",
        max_tokens=1000,
        messages=[{"role": "system", "content": prompt}],
    )

    return response.choices[0].message.content.strip()
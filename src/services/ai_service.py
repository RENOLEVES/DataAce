import os
import json
from urllib import response

from models.schemas import Operation, ParsedInstructions, ScanReport

# import anthropic
# client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

from openai import OpenAI
client = OpenAI(base_url="http://localhost:1111/v1", api_key="ollama")

SUPPORTED_OPERATIONS = """
Supported operations:
- fill_nulls: column (or "all"), strategy ("median"|"mean"|"mode"|"drop"), value (fixed value)
- remove_duplicates: scope ("exact")
- convert_to_datetime: column, format (optional)
- convert_to_numeric: column
- standardize_case: column (or "all"), to ("lower"|"upper"|"title")
- strip_whitespace: column (or "all")
- replace_pseudo_nulls: column (or "all")
- drop_column: column
- drop_rows_where_null: column (or "all")
- rename_column: column (old name), value (new name)
- cap_outliers: column (or "all")
- convert_excel_dates: column
- replace_string: column, value (old string to find), to (new string to replace with)

If the user requests something not covered above, use:
- custom_code: code (a single Python expression or statement using `df`), description (what it does)

Examples of custom_code:
  - fill with interpolation: df['price'] = df['price'].interpolate(method='linear', limit_direction='both')
  - normalize a column: df['col'] = (df['col'] - df['col'].min()) / (df['col'].max() - df['col'].min())
  - extract year from date: df['year'] = pd.to_datetime(df['date']).dt.year

Rules for custom_code:
- Always use `df` as the dataframe variable
- Only modify df, do not reassign it entirely (no df = ...)
- One line only
- `code` field is REQUIRED, never omit it
- `column` field should be null for custom_code, put the column name inside the code itself
"""



# ask AI to parse the user's instruction into structured operations, using the scan report context 
# to resolve ambiguities and provide defaults where possible. The response includes both the list 
# of operations to execute and any remaining ambiguities that require user clarification.
def parse_instructions(user_message: str, scan_report: ScanReport | None, conversation_history: list[dict]) -> ParsedInstructions:
    scan_context = ""
    if scan_report:
        col_names = ", ".join([i.column for i in scan_report.issues if i.column != "ALL"])
        all_cols = col_names or "unknown"
        scan_context = f"Available columns with issues: {all_cols}. Total rows: {scan_report.total_rows}."

    system_prompt = f"""You are a data cleaning assistant. Parse user instructions into structured cleaning operations.

                    If something is unclear, put it in the "ambiguities" list:
                    {{"operations": [], "ambiguities": ["unclear thing here"]}}

                    If the instruction is clear, return operations with empty ambiguities:
                    {{"operations": [...], "ambiguities": []}}

                    {SUPPORTED_OPERATIONS}

                    {scan_context}

                    CRITICAL RULES:
                    - Respond with ONLY a JSON object. Nothing else.
                    - No explanations, no markdown, no prose before or after.
                    - Your entire response must start with {{ and end with }}

                    Return ONLY this exact JSON format:
                    {{
                    "operations": [
                        {{
                        "operation": "operation_name",
                        "column": "column_name_or_null",
                        "strategy": null,
                        "format": null,
                        "value": null,
                        "scope": null,
                        "to": null,
                        "code": null,
                        "description": null
                        }}
                    ],
                    "ambiguities": []
                    }}"""

    retry_messages = conversation_history + [{"role": "user", "content": user_message}]

    # In case of parsing failures, we retry a 3 times with the conversation history to give the model more context.
    for attempt in range(3):
        response = client.chat.completions.create(
            model="qwen2.5-coder:7b",
            max_tokens=1000,
            temperature=0.1,
            messages=[{"role": "system", "content": system_prompt}] + retry_messages,
        )
        raw = response.choices[0].message.content.strip()

        # Strip markdown fences
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        # Extract JSON object
        start = raw.find("{")
        end = raw.rfind("}") + 1

        if start == -1 or end == 0:
            print(f"[parse_instructions] attempt {attempt+1}: no JSON found, retrying...")
            retry_messages = retry_messages + [
                {"role": "assistant", "content": raw},
                {"role": "user", "content": "You must respond with ONLY a JSON object. Start your response with { and end with }. No other text allowed."}
            ]
            continue

        raw = raw[start:end]
        import re
        raw = re.sub(r",\s*([}\]])", r"\1", raw)
        raw = re.sub(r'(?<!\\)\\(?!["\\/bfnrtu])', r'\\\\', raw)

        try:
            parsed = json.loads(raw)
            operations = [Operation(**op) for op in parsed.get("operations", [])]
            ambiguities = parsed.get("ambiguities", [])
            return ParsedInstructions(operations=operations, ambiguities=ambiguities)
        except (json.JSONDecodeError, Exception) as e:
            print(f"[parse_instructions] attempt {attempt+1}: parse error {e}, retrying...")
            continue

    # All retries failed — return empty so chat.py shows a friendly message
    print("[parse_instructions] all retries failed, returning empty")
    return ParsedInstructions(operations=[], ambiguities=["Could not parse your instruction. Please try rephrasing."])

# This function generates a clarifying question when the user's instruction is ambiguous.
# It uses the list of ambiguities identified by parse_instructions and the scan report 
# context to ask a specific question that will help resolve the ambiguity.
def generate_clarifying_question(ambiguities: list[str], scan_report: ScanReport | None) -> str:
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
        model="qwen2.5-coder:7b",
        max_tokens=1000,
        temperature=0.1,
        messages=[{"role": "system", "content": prompt}],
    )

    return response.choices[0].message.content.strip()


# This function is used to generate a human-friendly summary of the changes and warnings after executing operations.
# used in chat.py to create a nice assistant reply.
def generate_summary(changes: list[str], warnings: list[str]) -> str:
    if not changes and not warnings:
        return "No changes were applied."

    changes_text = "\n".join(f"- {c}" for c in changes)
    warnings_text = "\n".join(f"- {w}" for w in warnings) if warnings else ""

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
        model="qwen2.5-coder:7b",
        max_tokens=1000,
        temperature=0.1,
        messages=[{"role": "system", "content": prompt}],
    )

    return response.choices[0].message.content.strip()
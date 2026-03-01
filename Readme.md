# Data Cleaner API

A FastAPI backend for AI-powered data cleaning. Upload a messy file, describe what to fix in plain English, and download a clean file.

## Architecture

```
Upload file
    ↓
Local Scanner
    ↓
Chat — user gives instructions
    ↓
data convension
    ↓
local pre-processing
    ↓
Claude parses instructions → structured operations
    ↓
Ambiguous? → Ask clarifying question
Clear?     → Execute operations locally
    ↓
Return cleaned file
    ↓
Return optional Python code
```

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Set your API key

```bash
cp .env.example .env
# Edit .env and add your Anthropic API key
```

### 3. Run the server

```bash
cd data_cleaner
uvicorn main:app --reload --port 8000
```

API docs available at: http://localhost:8000/docs

---

## API Endpoints

### `POST /upload`
Upload a CSV, Excel, or JSON file.

**Form data:** `file` (multipart)

**Returns:**
```json
{
  "session_id": "abc-123",
  "filename": "customers.csv",
  "rows": 1000,
  "columns": 12,
  "scan_report": { ... },
  "opening_message": "I've scanned your file..."
}
```

---

### `POST /chat`
Send a cleaning instruction in the context of an active session.

**Body:**
```json
{
  "session_id": "abc-123",
  "message": "fill nulls with median, remove duplicates, standardize email to lowercase"
}
```

**Returns:**
```json
{
  "session_id": "abc-123",
  "reply": "Done! Removed 47 duplicates...",
  "download_ready": true,
  "download_url": "/download/abc-123"
}
```

If the instruction is ambiguous, `download_ready` will be `false` and `reply` will contain a clarifying question.

---

### `GET /download/{session_id}`
Download the cleaned file. Returns the file in the original format (CSV, Excel, or JSON) with `_cleaned` appended to the filename.

---

## Supported Cleaning Operations

| Operation | Description |
|-----------|-------------|
| `fill_nulls` | Fill missing values (median, mean, mode, fixed value, or drop) |
| `remove_duplicates` | Remove exact duplicate rows |
| `convert_to_datetime` | Convert a column to datetime |
| `convert_to_numeric` | Convert a column to numeric |
| `standardize_case` | Standardize text casing (lower/upper/title) |
| `strip_whitespace` | Remove leading/trailing whitespace |
| `replace_pseudo_nulls` | Replace "N/A", "none", "-" etc. with actual nulls |
| `drop_column` | Drop a column |
| `drop_rows_where_null` | Drop rows with nulls in a specific column |
| `rename_column` | Rename a column |
| `cap_outliers` | Cap outliers using IQR method |
| `convert_excel_dates` | Convert Excel serial date numbers to datetime |

## Project Structure

```
data_cleaner/
├── main.py                  # FastAPI app entry point
├── requirements.txt
├── .env.example
├── models/
│   └── schemas.py           # Pydantic models
├── routers/
│   ├── upload.py            # File upload + scan
│   ├── chat.py              # Conversation + execution
│   └── download.py          # File download
├── services/
│   ├── scanner.py           # Local rule-based issue detection
│   ├── executor.py          # Applies cleaning operations to dataframe
│   └── ai_service.py        # Claude API — parsing + clarification + summary
└── utils/
    ├── session_manager.py   # In-memory session state
    └── file_parser.py       # File parsing and serialization
```
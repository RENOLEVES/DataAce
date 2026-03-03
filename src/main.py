import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from dotenv import load_dotenv

load_dotenv()

from routers import upload, chat, download, notebook, preview, history

app = FastAPI(
    title="Data Cleaner API",
    description="Upload messy data, describe what to fix, download a clean file.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload.router)
app.include_router(chat.router)
app.include_router(download.router)
app.include_router(notebook.router)
app.include_router(preview.router)
app.include_router(history.router)


@app.get("/health")
def health():
    return {"status": "healthy"}


# STATIC_DIR is set by launcher.py so it works both in dev and when packaged.
# Falls back to src/static for normal development usage.
_static_dir = os.environ.get(
    "STATIC_DIR",
    os.path.join(os.path.dirname(__file__), "static"),
)

if os.path.exists(_static_dir):
    app.mount("/assets", StaticFiles(directory=_static_dir), name="static")

    @app.get("/")
    def serve_index():
        return FileResponse(os.path.join(_static_dir, "index.html"))

    @app.get("/{full_path:path}")
    def serve_react(full_path: str):
        # If the request is for a real file (e.g. JS/CSS chunk), serve it directly
        file_path = os.path.join(_static_dir, full_path)
        if os.path.isfile(file_path):
            return FileResponse(file_path)
        # Otherwise return index.html and let React Router handle it
        return FileResponse(os.path.join(_static_dir, "index.html"))
else:
    @app.get("/")
    def root():
        return {
            "status": "ok",
            "message": "Data Cleaner API is running. No frontend found — run in dev mode or build the React app first.",
        }
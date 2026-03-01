from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

from routers import upload, chat, download

app = FastAPI(
    title="Data Cleaner API",
    description="Upload messy data, describe what to fix, download a clean file.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Tighten this in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload.router)
app.include_router(chat.router)
app.include_router(download.router)


@app.get("/")
def root():
    return {"status": "ok", "message": "Data Cleaner API is running."}


@app.get("/health")
def health():
    return {"status": "healthy"}
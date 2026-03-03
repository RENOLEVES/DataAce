import sys
import os
import threading
import webbrowser
import time
import uvicorn


# Returns the base path for the application. When frozen by PyInstaller, 
# files are extracted to sys._MEIPASS. In development, use the directory of this file.
def get_base_path() -> str:
    if getattr(sys, "frozen", False):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))


# Sets up the environment by configuring paths and loading environment variables.
def setup_environment():
    base = get_base_path()

    # Make sure src/ is importable
    src_path = os.path.join(base, "src")
    if src_path not in sys.path:
        sys.path.insert(0, src_path)

    # Load .env file if present
    env_path = os.path.join(base, ".env")
    if os.path.exists(env_path):
        from dotenv import load_dotenv
        load_dotenv(env_path)
    else:
        print("Warning: .env file not found. API keys may be missing.")

    # Tell the app where to find static files (React build output)
    static_path = os.path.join(base, "src", "static")
    os.environ["STATIC_DIR"] = static_path


def open_browser(port: int, delay: float = 2.0):
    time.sleep(delay)
    webbrowser.open(f"http://127.0.0.1:{port}")


def main():
    port = 8000

    setup_environment()

    print(f"[launcher] Starting DataCleaner on http://127.0.0.1:{port}")
    print("[launcher] Opening browser...")

    # Open browser in background thread
    browser_thread = threading.Thread(
        target=open_browser,
        args=(port,),
        daemon=True,
    )
    browser_thread.start()

    # Start FastAPI server
    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=port,
        reload=False,       # Must be False when packaged
        log_level="warning",
    )


if __name__ == "__main__":
    main()
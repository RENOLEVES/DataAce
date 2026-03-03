# DataCleaner.spec

import os
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

block_cipher = None

hidden_imports = collect_submodules('fastapi') + \
                 collect_submodules('starlette') + \
                 collect_submodules('uvicorn')

hidden_imports += [
    # Your app modules
    "routers.upload",
    "routers.chat",
    "routers.download",
    "routers.notebook",
    "routers.history",
    "services.scanner",
    "services.executor",
    "services.ai_service",
    "services.notebook_generator",
    "models.schemas",
    "utils.session_manager",
    "utils.file_parser",

    # Data libraries
    "pandas",
    "numpy",
    "openpyxl",
    "openpyxl.cell._writer",

    # AI clients
    "anthropic",
    "openai",

    # Other
    "dotenv",
    "multipart",
    "aiofiles",
]

datas = [
    ("src", "src"),

    ("src/static", "src/static"),
]

# Add pandas and numpy data files (timezone data, etc.)
datas += collect_data_files("pandas")
datas += collect_data_files("numpy")

a = Analysis(
    ["launcher.py"],
    pathex=[os.path.abspath(".")],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude things we don't need to keep the exe smaller
        "tkinter",
        "matplotlib",
        "scipy",
        "sklearn",
        "IPython",
        "jupyter",
        "notebook",
        "pytest",
        "PIL",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="DataAce",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # icon="assets/icon.ico",
)

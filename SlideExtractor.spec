# SlideExtractor.spec
# PyInstaller spec file — run with:  pyinstaller SlideExtractor.spec
#
# Handles all the tricky hidden imports for customtkinter, imageio-ffmpeg,
# reportlab, and Pillow so the bundled EXE works on a clean Windows machine.

import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# ── Collect data files that packages need at runtime ─────────────────────────
import os as _os
datas = []
datas += collect_data_files("customtkinter")   # themes, fonts, images
datas += collect_data_files("imageio_ffmpeg")  # bundled ffmpeg binary
datas += collect_data_files("reportlab")       # fonts & resources

# ── Bundle icon.ico if it exists next to this spec file
_icon_src = _os.path.join(_os.path.dirname(_os.path.abspath(SPEC)), "icon.ico")
if _os.path.isfile(_icon_src):
    datas += [(_icon_src, ".")]   # copies icon.ico into the root of the bundle

# ── Hidden imports that PyInstaller misses with static analysis ───────────────
hiddenimports = []
hiddenimports += collect_submodules("customtkinter")
hiddenimports += collect_submodules("PIL")
hiddenimports += collect_submodules("reportlab")
hiddenimports += [
    "imageio_ffmpeg",
    "tkinter",
    "tkinter.filedialog",
    "tkinter.messagebox",
]

# ─────────────────────────────────────────────────────────────────────────────

a = Analysis(
    ["slide_extractor.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Trim unused heavy packages (if any) to keep EXE smaller
        "matplotlib", "numpy", "scipy", "pandas",
        "IPython", "jupyter", "notebook",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="SlideExtractor",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False, # UPX disabled due to lack of compression & execution delays
    # upx_exclude=[],
    # upx_path='upx/upx.exe',
    runtime_tmpdir=None,
    console=False, # no console window
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="icon.ico",
)

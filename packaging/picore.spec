# PyInstaller build for πCore (one-folder app).
#   python -m PyInstaller packaging/picore.spec --noconfirm
# Output: dist/PiCore/PiCore.exe
# Only the assets the app uses are bundled. picore.config.json (your API key) is never included.
import os

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
ASSETS = ["background1.png", "background2.png", "picore_logo.png", "bgmusic.mp3"]

a = Analysis(
    [os.path.join(ROOT, "Pi Core.py")],
    pathex=[ROOT],
    datas=[(os.path.join(ROOT, "assets", f), "assets") for f in ASSETS],
    hiddenimports=["picore.scenes.calc", "picore.scenes.graph", "picore.scenes.history",
                   "picore.scenes.simple", "picore.engine.checker"],
    excludes=["matplotlib", "tkinter", "scipy", "pandas", "IPython", "PyQt5", "PySide6",
              "mysql", "pytest", "PIL"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="PiCore",
    icon=os.path.join(SPECPATH, "picore.ico"),
    console=False,
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="PiCore", upx=False)

# PyInstaller build for πCore (one-folder app).
#   python -m PyInstaller packaging/picore.spec --noconfirm
# Output: dist/PiCore/PiCore.exe
# Only the assets the app uses are bundled. picore.config.json (your API key) is never included.
import os

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
ASSETS = ["background1.png", "background2.png", "picore_logo.png", "bgmusic.mp3"]
# Freely licensed fonts (SIL OFL) always ship. The Shotengai demo font is personal-use only, so it
# is bundled only for your own builds:  set PICORE_PERSONAL_BUILD=1  before building.
FONTS = ["ShipporiMincho-Regular.ttf", "ShipporiMincho-Bold.ttf", "YujiSyuku-Regular.ttf",
         "STIXTwoMath-Symbols.ttf", "OFL-ShipporiMincho.txt", "OFL-YujiSyuku.txt", "OFL-STIXTwoMath.txt"]
if os.environ.get("PICORE_PERSONAL_BUILD") == "1":
    FONTS.append("ShotengaiDemo.otf")

a = Analysis(
    [os.path.join(ROOT, "Pi Core.py")],
    pathex=[ROOT],
    datas=[(os.path.join(ROOT, "assets", f), "assets") for f in ASSETS]
          + [(os.path.join(ROOT, "assets", "fonts", f), "assets/fonts") for f in FONTS],
    hiddenimports=["picore.scenes.calc", "picore.scenes.graph", "picore.scenes.history",
                   "picore.scenes.simple", "picore.engine.checker"],
    excludes=["matplotlib", "tkinter", "scipy", "pandas", "IPython", "PyQt5", "PySide6",
              "mysql", "pytest", "PIL", "fontTools"],
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

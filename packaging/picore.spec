# PyInstaller build for πCore (one-folder app).
#   python -m PyInstaller packaging/picore.spec --noconfirm
# Output: dist/PiCore/PiCore.exe
# Only the assets the app uses are bundled. picore.config.json (your API key) is never included.
import os

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
ASSETS = ["background1.png", "background2.png", "picore_logo.png"]
# Music is optional and not in the repository (licence unknown): bundled only if you add it yourself.
ASSETS += [f for f in ("bgmusic.mp3",) if os.path.exists(os.path.join(ROOT, "assets", f))]
# Freely licensed fonts (SIL OFL) always ship. The Shotengai demo font is personal-use only, so it
# is bundled only for your own builds:  set PICORE_PERSONAL_BUILD=1  before building.
FONTS = ["ShipporiMincho-Regular.ttf", "ShipporiMincho-Bold.ttf", "YujiSyuku-Regular.ttf",
         "STIXTwoMath-Symbols.ttf", "OFL-ShipporiMincho.txt", "OFL-YujiSyuku.txt", "OFL-STIXTwoMath.txt"]
if os.environ.get("PICORE_PERSONAL_BUILD") == "1":
    FONTS.append("ShotengaiDemo.otf")

a = Analysis(
    [os.path.join(ROOT, "main.py")],
    pathex=[ROOT],
    datas=[(os.path.join(ROOT, "assets", f), "assets") for f in ASSETS]
          + [(os.path.join(ROOT, "assets", "fonts", f), "assets/fonts") for f in FONTS],
    hiddenimports=["picore.scenes.calc", "picore.scenes.graph", "picore.scenes.history",
                   "picore.scenes.simple", "picore.scenes.tree", "picore.scenes.explore",
                   "picore.engine.checker", "picore.engine.reasoning_commands",
                   "picore.reasoning.mistakes.algebra", "picore.reasoning.mistakes.calculus",
                   "picore.reasoning.mistakes.equations", "picore.reasoning.mistakes.trig",
                   "picore.reasoning.mistakes.checks"],
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

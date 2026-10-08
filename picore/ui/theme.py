"""Colors, canvas size and cached fonts — the gold-on-black πCore look."""
import os

import pygame

from ..paths import asset

WIDTH, HEIGHT = 1280, 720

YELLOW = (251, 202, 31)
GOLD = (233, 181, 11)
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
PANEL = (240, 240, 240)
TEXT_LIGHT = (230, 230, 230)
MUTED = (150, 150, 150)
PLACEHOLDER = (120, 120, 120)
LOADER = (180, 140, 255)
ERROR = (255, 110, 110)
GOOD = (110, 220, 130)
WARN = (255, 170, 60)
GRAPH_BG = (14, 14, 14)
GRID = (45, 45, 45)

# Text: Shippori Mincho (SIL OFL), with STIX Two Math (SIL OFL) for Greek letters and maths
# symbols that Shippori lacks. Titles & buttons: the Shotengai brush font if present
# (personal-use demo, git-ignored), otherwise Yuji Syuku (SIL OFL), which can be shipped.
TEXT_FONTS = {False: "ShipporiMincho-Regular.ttf", True: "ShipporiMincho-Bold.ttf"}
SYMBOL_FONT = "STIXTwoMath-Symbols.ttf"
DISPLAY_FONTS = ["ShotengaiDemo.otf", "YujiSyuku-Regular.ttf"]
SYSTEM_FALLBACK = "segoeui,arial,helvetica,dejavusans"

_cache = {}
_display_path = None
_has = {}   # (font id, char) -> whether that font draws a real glyph for char


def reset():
    """Forget cached fonts. Must be called when pygame shuts down: a Font used after
    pygame.quit() crashes the interpreter (access violation), not with a Python error."""
    global _display_path
    _cache.clear()
    _has.clear()
    _display_path = None


def _load(filename, size, bold=False):
    try:
        return pygame.font.Font(asset("fonts/" + filename), size)
    except (FileNotFoundError, OSError, pygame.error):
        return pygame.font.SysFont(SYSTEM_FALLBACK, size, bold=bold)


def _has_glyph(fnt, ch):
    """True if ``fnt`` really draws ``ch``: not blank (demo fonts) and not the 'missing' box."""
    if ch == " ":
        return True
    if isinstance(fnt, FontChain):
        return any(_has_glyph(f, ch) for f in fnt.fonts)
    key = (id(fnt), ch)
    if key not in _has:
        surf = fnt.render(ch, True, WHITE)
        notdef = fnt.render("\U0010FFFD", True, WHITE)
        same_as_notdef = (surf.get_size() == notdef.get_size()
                          and pygame.image.tobytes(surf, "RGBA") == pygame.image.tobytes(notdef, "RGBA"))
        _has[key] = surf.get_bounding_rect().width > 0 and not same_as_notdef
    return _has[key]


class FontChain:
    """Behaves like a pygame Font, but draws each character with the first font in the chain
    that has it, all on one baseline. Lets a pretty font be used even if it lacks π, √ or ':'."""

    def __init__(self, fonts):
        self.fonts = fonts
        self.main = fonts[0]

    def _runs(self, text):
        runs = []
        for ch in text:
            f = next((f for f in self.fonts if _has_glyph(f, ch)), self.main)
            if runs and runs[-1][0] is f:
                runs[-1][1] += ch
            else:
                runs.append([f, ch])
        return runs

    def render(self, text, antialias, color, background=None):
        runs = self._runs(text)
        if len(runs) <= 1:
            f = runs[0][0] if runs else self.main
            return f.render(text, antialias, color, background)
        surfs = [(f, f.render(t, antialias, color)) for f, t in runs]
        ascent = max(f.get_ascent() for f, _ in surfs)
        width = sum(s.get_width() for _, s in surfs)
        height = max(ascent - f.get_ascent() + s.get_height() for f, s in surfs)
        out = pygame.Surface((max(1, width), max(1, height)), pygame.SRCALPHA)
        if background is not None:
            out.fill(background)
        x = 0
        for f, s in surfs:
            out.blit(s, (x, ascent - f.get_ascent()))
            x += s.get_width()
        return out

    def size(self, text):
        return sum(f.size(t)[0] for f, t in self._runs(text)), self.main.get_height()

    def get_height(self):
        return self.main.get_height()

    def get_linesize(self):
        return self.main.get_linesize()

    def get_ascent(self):
        return self.main.get_ascent()

    def get_descent(self):
        return self.main.get_descent()


def font(size, bold=False):
    """Body text font (results, input, labels)."""
    key = ("text", size, bold)
    if key not in _cache:
        _cache[key] = FontChain([_load(TEXT_FONTS[bold], size, bold), _load(SYMBOL_FONT, size)])
    return _cache[key]


def _display_font(size):
    global _display_path
    if _display_path is None:
        _display_path = next((f for f in DISPLAY_FONTS if os.path.exists(asset("fonts/" + f))), "")
    key = ("display", size)
    if key not in _cache:
        brush = _load(_display_path, size, True) if _display_path else font(size, True)
        _cache[key] = FontChain([brush, font(int(size * 0.8), True)])
    return _cache[key]


def display(text, size, color):
    """Render a title/button label in the brush font, cropped to its ink so it centers cleanly.
    Characters the brush font can't draw (':', '(', 'π', ...) come from the text font."""
    out = _display_font(size).render(text, True, color)
    ink = out.get_bounding_rect()
    return out.subsurface(ink).copy() if ink.width and ink.height else out

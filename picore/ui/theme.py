"""Colors, canvas size and cached fonts — the gold-on-black πCore look."""
import pygame

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
GRAPH_BG = (14, 14, 14)
GRID = (45, 45, 45)

# Comma-separated list: pygame picks the first installed one, so this works on
# Windows (Segoe UI), macOS (Arial) and Linux (DejaVu Sans).
UI_FONTS = "segoeui,segoeuisymbol,arial,helvetica,dejavusans"

_cache = {}


def font(size, bold=False):
    key = (size, bold)
    if key not in _cache:
        _cache[key] = pygame.font.SysFont(UI_FONTS, size, bold=bold)
    return _cache[key]

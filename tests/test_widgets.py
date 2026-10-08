import os

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame  # noqa: E402
import pytest  # noqa: E402

from picore.ui.widgets import TextInput, wrap_text  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def _pg():
    pygame.font.init()
    yield
    pygame.font.quit()


def font():
    return pygame.font.SysFont(None, 20)


def test_wrap_keeps_newlines_and_fits():
    f = font()
    lines = wrap_text("first line\nsecond " + "word " * 40, f, 200)
    assert lines[0] == "first line"
    assert all(f.size(ln)[0] <= 200 for ln in lines)


def test_wrap_breaks_long_words():
    f = font()
    lines = wrap_text("9" * 300, f, 150)
    assert len(lines) > 1 and "".join(lines) == "9" * 300


def key(k, mod=0):
    return pygame.event.Event(pygame.KEYDOWN, key=k, mod=mod, unicode="")


def test_text_input_editing():
    t = TextInput((0, 0, 400, 100))
    t.handle(pygame.event.Event(pygame.TEXTINPUT, text="x+1"))
    t.handle(key(pygame.K_HOME))
    t.handle(pygame.event.Event(pygame.TEXTINPUT, text="2"))
    assert t.text == "2x+1"
    t.handle(key(pygame.K_END))
    t.handle(key(pygame.K_BACKSPACE))
    assert t.text == "2x+"
    t.handle(pygame.event.Event(pygame.TEXTINPUT, text="\t\x1b"))   # control chars ignored
    assert t.text == "2x+"
    assert t.handle(key(pygame.K_RETURN)) == "submit"


def test_text_input_limit_and_recall():
    t = TextInput((0, 0, 400, 100))
    t.handle(pygame.event.Event(pygame.TEXTINPUT, text="1" * 500))
    assert len(t.text) == TextInput.MAX_LEN
    t.set_text("")
    t.recall = ["newest", "older"]
    t.handle(key(pygame.K_UP))
    assert t.text == "newest"
    t.handle(key(pygame.K_UP))
    assert t.text == "older"
    t.handle(key(pygame.K_DOWN))
    t.handle(key(pygame.K_DOWN))
    assert t.text == ""


def test_text_font_falls_back_for_math_symbols():
    from picore.ui import theme as T
    f = T.font(20)
    for sym in ("π", "√", "∫", "≈", "∞", "ε"):   # pi, sqrt, integral, approx, inf, epsilon
        runs = f._runs(sym)
        assert T._has_glyph(runs[0][0], sym), f"no font draws {sym!r}"


def test_display_text_is_cropped_and_renders_punctuation():
    from picore.ui import theme as T
    surf = T.display("MUSIC: ON", 26, (0, 0, 0))
    assert surf.get_width() > 50 and surf.get_bounding_rect().size == surf.get_size()

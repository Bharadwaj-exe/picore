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

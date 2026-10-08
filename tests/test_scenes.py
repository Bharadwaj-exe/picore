"""Headless smoke tests: drive every screen with real events and make sure nothing crashes."""
import os
import time

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame  # noqa: E402
import pytest  # noqa: E402


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    from picore import paths
    data = tmp_path_factory.mktemp("data")
    old = paths.user_data_dir
    paths.user_data_dir = lambda: data
    os.environ["PICORE_WOLFRAM_APPID"] = ""
    from picore.app import App
    a = App()
    a.settings.data["wolfram_app_id"] = ""          # never call the network from tests
    yield a
    paths.user_data_dir = old
    from picore.ui import theme
    theme.reset()
    pygame.quit()


def frame(app, events=()):
    for kind, result, error in app.worker.poll():
        for sc in app.scenes.values():
            if hasattr(sc, "on_result"):
                sc.on_result(kind, result, error)
    for e in events:
        app.scene.handle(e)
    app.scene.update(16)
    app.scene.draw(app.screen)


def settle(app, kind, timeout=30):
    end = time.time() + timeout
    while app.worker.busy(kind) and time.time() < end:
        time.sleep(0.02)
        frame(app)
    frame(app)


def key(k, mod=0):
    return pygame.event.Event(pygame.KEYDOWN, key=k, mod=mod, unicode="")


def click(pos):
    return [pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=pos),
            pygame.event.Event(pygame.MOUSEBUTTONUP, button=1, pos=pos)]


def test_loading_reaches_menu(app):
    settle(app, "boot")
    app.scenes["loading"].t = 10 ** 6
    frame(app)
    assert app.scene is app.scenes["menu"]
    frame(app, [key(pygame.K_RETURN)])
    assert app.scene is app.scenes["calc"]


@pytest.mark.parametrize("query", ["x^2 - 5x + 6", "check x^2 = 4 -> x = 2", "equiv x/x ; 1",
                                   "derive x^3 : d/dx, integrate", "what is love", "((((", "9^9^9"])
def test_calc_handles_queries(app, query):
    app.go("calc")
    c = app.scenes["calc"]
    c.input.set_text(query)
    frame(app, [key(pygame.K_RETURN)])
    settle(app, "calc")
    assert c.cards.cards, f"no result cards for {query!r}"


def test_graph_tree_explore_history_screens(app):
    app.go("calc")
    c = app.scenes["calc"]
    c.input.set_text("sin(x)/x")
    frame(app, [key(pygame.K_g, pygame.KMOD_CTRL)])
    settle(app, "plot")
    assert app.scene is app.scenes["graph"]
    frame(app, [pygame.event.Event(pygame.MOUSEWHEEL, x=0, y=1)] + click((600, 300)) + [key(pygame.K_r)])
    frame(app, [key(pygame.K_ESCAPE)])

    c.input.set_text("2sin(x)^2 + 3x")
    frame(app, [key(pygame.K_t, pygame.KMOD_CTRL)])
    assert app.scene is app.scenes["tree"]
    frame(app, [key(pygame.K_DOWN), key(pygame.K_RIGHT), key(pygame.K_DOWN), key(pygame.K_UP)])
    frame(app, [key(pygame.K_s)])
    settle(app, "tree_simplify")
    frame(app, [key(pygame.K_ESCAPE)])

    c.input.set_text("explore a x^2 + b x + c")
    frame(app, [key(pygame.K_RETURN)])
    ex = app.scenes["explore"]
    assert app.scene is ex
    knob_y = ex.sliders[0].rect.centery
    frame(app, click((ex.sliders[0].rect.left + 5, knob_y)))
    assert ex.sliders[0].value < 0
    frame(app, [key(pygame.K_ESCAPE)])

    frame(app, [key(pygame.K_h, pygame.KMOD_CTRL)])
    assert app.scene is app.scenes["history"]
    assert app.scenes["history"].items
    frame(app)


def test_tree_shows_parse_error_with_position(app):
    app.go("tree", text="2 + * 3")
    frame(app)
    assert app.scenes["tree"].error.pos == 4

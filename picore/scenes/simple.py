"""Loading and menu screens."""
import pygame

from ..ui import theme as T
from ..ui.widgets import Button


class Scene:
    def __init__(self, app):
        self.app = app

    def enter(self, **kwargs):
        pass

    def handle(self, e):
        pass

    def update(self, dt):
        pass

    def draw(self, s):
        pass


def _warm_up():
    """Real start-up work hidden behind the loading screen: importing SymPy is the slow part."""
    from ..engine import evaluate
    evaluate("x^2-1")
    return True


class LoadingScene(Scene):
    WORDS = ["Consulting Archimedes", "Dividing Circles by Zero", "Summoning Infinite Series",
             "Arguing with Irrational Numbers", "Convincing π to Terminate",
             "Chasing Digits Past Infinity", "Proving This Will Eventually Load"]
    MIN_MS = 1800

    def enter(self, **kwargs):
        self.t = 0
        self.ready = False
        self.error = None
        self.app.worker.submit("boot", _warm_up)

    def on_result(self, kind, result, error):
        if kind == "boot":
            self.ready, self.error = error is None, error

    def update(self, dt):
        self.t += dt
        if self.ready and self.t >= self.MIN_MS:
            self.app.go("menu")

    def draw(self, s):
        s.blit(self.app.bg_game, (0, 0))
        if self.error:
            msg = f"Start-up failed: {self.error}"
            txt = T.font(24, True).render(msg, True, T.ERROR)
        else:
            word = self.WORDS[int(self.t // 1100) % len(self.WORDS)]
            dots = "." * (int(self.t // 300) % 4)
            txt = T.font(30, True).render(word + dots, True, T.LOADER)
        s.blit(txt, txt.get_rect(center=(T.WIDTH // 2, T.HEIGHT // 2)))


class MenuScene(Scene):
    def __init__(self, app):
        super().__init__(app)
        self.enter_btn = Button("ENTER", (T.WIDTH // 2, 504), (230, 58), 36)

    def handle(self, e):
        if self.enter_btn.clicked(e) or (e.type == pygame.KEYDOWN and e.key in (pygame.K_RETURN, pygame.K_SPACE)):
            self.app.go("calc")

    def draw(self, s):
        s.blit(self.app.bg_menu, (0, 0))
        self.enter_btn.draw(s)

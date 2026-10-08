"""Graph screen: one function, drawn with the shared Plot widget."""
import pygame

from ..engine.local import fmt
from ..ui import theme as T
from ..ui.plot import Plot, sampler
from ..ui.widgets import Button
from .simple import Scene


class GraphScene(Scene):
    def __init__(self, app):
        super().__init__(app)
        self.back_btn = Button("BACK", (90, 50), (120, 44), 30)
        self.reset_btn = Button("RESET", (1150, 50), (130, 44), 28)
        self.plot = Plot((60, 100, 1160, 540))

    def enter(self, expr=None, label="", **kwargs):
        var = sorted(expr.free_symbols, key=lambda s: s.name)[0]
        self.label = f"y = {fmt(expr)}"
        try:
            self.plot.set_function(sampler(expr, var))
        except Exception:
            self.plot.fn, self.plot.error = None, "This function can't be graphed"

    def handle(self, e):
        if self.back_btn.clicked(e) or (e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE):
            self.app.go("calc")
            return
        if self.reset_btn.clicked(e) or (e.type == pygame.KEYDOWN and e.key == pygame.K_r):
            self.plot.reset_view()
            return
        self.plot.handle(e)

    def draw(self, s):
        s.blit(self.app.bg_game, (0, 0))
        self.back_btn.draw(s)
        self.reset_btn.draw(s)
        title = T.font(26, True).render(self.label, True, T.YELLOW)
        if title.get_width() > 860:
            title = pygame.transform.smoothscale(title, (860, int(title.get_height() * 860 / title.get_width())))
        s.blit(title, title.get_rect(center=(T.WIDTH // 2, 50)))
        self.plot.draw(s)
        hint = T.font(16).render("scroll: zoom   ·   drag: pan   ·   R: reset   ·   hover: trace   ·   Esc: back",
                                 True, T.MUTED)
        s.blit(hint, hint.get_rect(midtop=(T.WIDTH // 2, self.plot.rect.bottom + 12)))

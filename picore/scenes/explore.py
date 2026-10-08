"""Parameter explorer: drag sliders, watch the graph and its analysis update live."""
import pygame

from ..engine.local import fmt
from ..explore import X, analyze, make_experiment
from ..lang import ParseError
from ..ui import theme as T
from ..ui.plot import Plot, sampler
from ..ui.widgets import Button, Slider, wrap_text
from .simple import Scene

MARK_COLORS = {"root": (110, 220, 130), "vertex": (255, 140, 90), "point": (150, 190, 255)}
SIDE = pygame.Rect(895, 100, 330, 540)


class ExplorerScene(Scene):
    def __init__(self, app):
        super().__init__(app)
        self.back_btn = Button("BACK", (90, 50), (120, 44), 30)
        self.reset_btn = Button("RESET", (1150, 50), (130, 44), 28)
        self.plot = Plot((60, 100, 815, 540))
        self.exp = None
        self.error = None

    def enter(self, text="", **kwargs):
        self.error = None
        try:
            self.exp = make_experiment(text)
        except (ParseError, ValueError) as exc:
            self.exp, self.error = None, str(exc)
            return
        self.sliders = [Slider(p.name, (SIDE.x + 15, SIDE.y + 82 + i * 58, SIDE.w - 40, 10))
                        for i, p in enumerate(self.exp.params)]
        self.fn = sampler(self.exp.expr, X, self.exp.params)
        self.refresh(fit=True)

    def refresh(self, fit=False):
        for sl, p in zip(self.sliders, self.exp.params):
            self.exp.values[p] = sl.value
        values = [sl.value for sl in self.sliders]
        self.plot.set_function(lambda xs, v=values: self.fn(xs, *v), fit=fit)
        try:
            self.analysis = analyze(self.exp)
        except Exception:  # a failed analysis must never take the screen down; the graph still works
            self.analysis = None

    def handle(self, e):
        if self.back_btn.clicked(e) or (e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE):
            self.app.go("calc")
            return
        if self.exp is None:
            return
        if self.reset_btn.clicked(e) or (e.type == pygame.KEYDOWN and e.key == pygame.K_r):
            self.plot.reset_view()
            return
        for sl in self.sliders:
            if sl.handle(e):
                self.refresh()
                return
            if sl.dragging:
                return
        self.plot.handle(e)

    def draw(self, s):
        s.blit(self.app.bg_game, (0, 0))
        self.back_btn.draw(s)
        self.reset_btn.draw(s)
        if self.error:
            msg = T.font(22, True).render(self.error, True, T.ERROR)
            s.blit(msg, msg.get_rect(center=(T.WIDTH // 2, T.HEIGHT // 2)))
            return
        title = T.font(26, True).render(f"y = {fmt(self.exp.expr)}", True, T.YELLOW)
        s.blit(title, title.get_rect(center=(T.WIDTH // 2, 50)))
        an = self.analysis
        markers = [(x, y, label, MARK_COLORS[kind]) for x, y, label, kind in (an.markers if an else [])]
        vlines = [(x, (255, 140, 90)) for x in (an.vlines if an else [])]
        self.plot.draw(s, markers, vlines)

        pygame.draw.rect(s, T.BLACK, SIDE)
        pygame.draw.rect(s, T.YELLOW, SIDE, 2)
        head = T.display("Parameters", 24, T.YELLOW)
        s.blit(head, (SIDE.x + 15, SIDE.y + 10))
        for sl in self.sliders:
            sl.draw(s)
        y = SIDE.y + 82 + len(self.sliders) * 58 - 22
        pygame.draw.line(s, T.MUTED, (SIDE.x + 10, y), (SIDE.right - 10, y))
        y += 10
        if an:
            kind = T.font(16, True).render(f"Analysis · {an.kind}", True, T.MUTED)
            s.blit(kind, (SIDE.x + 15, y))
            y += 24
            for fact in an.facts:
                value = wrap_text(fact.value, T.font(17), SIDE.w - 40)[:2]
                why = wrap_text(fact.why, T.font(15), SIDE.w - 40)[:2] if fact.why else []
                if y + 20 + 19 * len(value) > SIDE.bottom - 6:
                    break                                    # no room: never draw outside the panel
                if y + 20 + 19 * len(value) + 17 * len(why) > SIDE.bottom - 6:
                    why = []
                s.blit(T.font(17, True).render(f"{fact.label}:", True, T.YELLOW), (SIDE.x + 15, y))
                y += 20
                for ln in value:
                    s.blit(T.font(17).render(ln, True, T.WHITE), (SIDE.x + 25, y))
                    y += 19
                for ln in why:
                    s.blit(T.font(15).render(ln, True, T.MUTED), (SIDE.x + 25, y))
                    y += 17
                y += 3
        hint = T.font(15).render("drag sliders (or scroll on them)  ·  scroll graph: zoom  ·  drag graph: pan  ·  "
                                 "R: reset view  ·  Esc: back", True, T.MUTED)
        s.blit(hint, hint.get_rect(midtop=(T.WIDTH // 2 - 120, self.plot.rect.bottom + 12)))

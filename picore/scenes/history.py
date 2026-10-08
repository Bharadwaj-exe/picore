"""History screen: past queries as cards; click to expand, RUN to re-open in the calculator."""
import pygame

from ..ui import theme as T
from ..ui.widgets import Button, CardList, wrap_text
from .simple import Scene

CONFIRM_MS = 3000


def fit(text, fnt, max_width):
    """Shorten ``text`` with an ellipsis so it fits in ``max_width`` pixels."""
    if fnt.size(text)[0] <= max_width:
        return text
    while text and fnt.size(text + "…")[0] > max_width:
        text = text[:-1]
    return text.rstrip() + "…"


class HistoryScene(Scene):
    def __init__(self, app):
        super().__init__(app)
        self.back_btn = Button("BACK", (90, 50), (120, 44), 30)
        self.clear_btn = Button("CLEAR HISTORY", (1080, 50), (250, 44), 26)
        self.cards = CardList((80, 110, 1110, 540))
        self.items = []
        self.expanded = set()
        self.error = None
        self.confirm_until = 0

    def enter(self, **kwargs):
        self.expanded.clear()
        self.reload()

    def reload(self):
        try:
            self.items = self.app.history.fetch(100)
            self.error = None
        except Exception as exc:
            self.items, self.error = [], f"Couldn't read history: {exc}"
        self.rebuild()

    def rebuild(self):
        keep = self.cards.scroll
        self.cards.load([(it.expression, "", it) for it in self.items],
                        renderer=lambda row, width: self._render(row[2], width))
        self.cards.scroll_by(keep)

    def _render(self, item, width):
        pad = CardList.PAD
        ft, fb, fs = T.font(22, True), T.font(18), T.font(15, True)
        is_open = item.id in self.expanded
        if is_open:
            body = []
            for title, content in item.results:
                body.append(("title", title))
                body += [("line", ln) for ln in wrap_text(content, fb, width - 2 * pad - 20)]
        else:
            first = next((c for t, c in item.results if t != "Input"), "")
            body = [("line", fit(first.replace("\n", "  "), fb, width - 2 * pad - 20))]
        lh = fb.get_linesize()
        h = pad + ft.get_linesize() + 8 + len(body) * lh + pad
        surf = pygame.Surface((width, h))
        surf.fill(T.BLACK)
        pygame.draw.rect(surf, T.YELLOW, surf.get_rect(), 3)
        meta = fs.render(f"{item.created_at}   ·   {'Wolfram|Alpha' if item.source == 'wolfram' else 'SymPy'}"
                         f"   ·   {'click to collapse' if is_open else 'click to expand'}", True, T.MUTED)
        meta_x = width - meta.get_width() - pad - 110
        title = fit(item.expression, ft, meta_x - pad - 24)   # never run into the date
        surf.blit(ft.render(title, True, T.YELLOW), (pad, pad - 4))
        surf.blit(meta, (meta_x, pad))
        # RUN chip (hit-tested in handle via the same geometry)
        run = pygame.Rect(width - pad - 90, pad - 4, 90, 30)
        pygame.draw.rect(surf, T.YELLOW, run)
        rt = fs.render("RUN", True, T.BLACK)
        surf.blit(rt, rt.get_rect(center=run.center))
        y = pad + ft.get_linesize() + 4
        for kind, text in body:
            if kind == "title":
                surf.blit(fs.render(text, True, (200, 200, 255)), (pad + 10, y + 2))
            else:
                surf.blit(fb.render(text, True, T.TEXT_LIGHT), (pad + 10, y))
            y += lh
        return surf

    def handle(self, e):
        if self.back_btn.clicked(e) or (e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE):
            self.app.go("calc")
            return
        if self.clear_btn.clicked(e) and self.items:
            now = pygame.time.get_ticks()
            if now < self.confirm_until:
                try:
                    self.app.history.clear()
                except Exception as exc:
                    self.error = f"Couldn't clear history: {exc}"
                self.confirm_until = 0
                self.expanded.clear()
                self.reload()
            else:
                self.confirm_until = now + CONFIRM_MS
            return
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            hit = self.cards.hit(e.pos)
            if hit:
                rect, item = hit
                run = pygame.Rect(rect.right - CardList.PAD - 90, rect.y + CardList.PAD - 4, 90, 30)
                if run.collidepoint(e.pos):
                    self.app.go("calc", run=item.expression)
                    return
                self.expanded ^= {item.id}
                self.rebuild()
        self.cards.handle(e)

    def draw(self, s):
        s.blit(self.app.bg_game, (0, 0))
        self.back_btn.draw(s)
        confirming = pygame.time.get_ticks() < self.confirm_until
        self.clear_btn.text = "CLICK AGAIN TO CONFIRM" if confirming else "CLEAR HISTORY"
        self.clear_btn.font_size = 20 if confirming else 26
        if self.items:
            self.clear_btn.draw(s)
        title = T.display("History", 40, T.YELLOW)
        s.blit(title, title.get_rect(center=(T.WIDTH // 2, 50)))
        if self.error:
            msg = T.font(22, True).render(self.error, True, T.ERROR)
            s.blit(msg, msg.get_rect(center=(T.WIDTH // 2, T.HEIGHT // 2)))
        elif not self.items:
            msg = T.font(24, True).render("Nothing here yet. Solve something first!", True, T.MUTED)
            s.blit(msg, msg.get_rect(center=(T.WIDTH // 2, T.HEIGHT // 2)))
        else:
            self.cards.draw(s)

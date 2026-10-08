"""Main calculator screen: input card, result cards, graph & history buttons."""
import pygame

from .. import engine
from ..engine.local import plot_target
from ..ui import theme as T
from ..ui.widgets import Button, CardList, TextInput
from .simple import Scene

TIMEOUT_S = 25
EXAMPLES = ["x^2 - 5x + 6", "solve x+y=3 and x-y=1", "d/dx sin(x)^2", "integrate x^2 from 0 to 3",
            "check x^2-5x+6=0 -> x^2 = 5x-6 -> x = 5 ± √6", "check d/dx(x^2 sin(x)) -> 2x cos(x)",
            "equiv (x^2-1)/(x-1) ; x+1", "derive (x+1)^2 : expand, d/dx, sub x=1",
            "tree 2sin(x)^2 + 3x", "explore a x^2 + b x + c"]


class CalcScene(Scene):
    def __init__(self, app):
        super().__init__(app)
        self.back_btn = Button("BACK", (90, 50), (120, 44), 30)
        self.graph_btn = Button("GRAPH", (1072, 88), (122, 48), 26)
        self.tree_btn = Button("TREE", (1204, 88), (122, 48), 26)
        self.history_btn = Button("HISTORY", (1072, 152), (122, 48), 26)
        self.explore_btn = Button("EXPLORE", (1204, 152), (122, 48), 26)
        self.input = TextInput((190, 62, 800, 110))
        self.cards = CardList((80, 225, 1110, 410))
        self.status = ""
        self.status_color = T.MUTED
        self.last = None          # (text, Response) of the last finished query
        self.example_rects = []

    def enter(self, run=None, **kwargs):
        try:
            self.input.recall = self.app.history.recent_expressions()
        except Exception:
            self.input.recall = []
        if run:
            self.input.set_text(run)
            self.submit()

    # ---- actions -------------------------------------------------------------
    def submit(self):
        text = self.input.text.strip()
        if not text:
            return
        word, _, rest = text.partition(" ")
        if word.lower() in ("tree", "explore") and rest.strip():     # screens, not calculations
            self.app.go(word.lower(), text=rest)
            return
        self.pending_text = text
        self.app.worker.submit("calc", engine.evaluate, text, self.app.settings.wolfram_app_id,
                               self.app.settings.wolfram_proxy)
        self.set_status("Computing", T.LOADER)

    def open_graph(self):
        text = self.input.text.strip()
        if not text:
            self.set_status("Type a function first, e.g. sin(x)/x", T.ERROR)
            return
        if self.last and self.last[0] == text and self.last[1].plot_expr is not None:
            self.app.go("graph", expr=self.last[1].plot_expr, label=text)
            return
        self.pending_plot = text
        self.app.worker.submit("plot", plot_target, text)
        self.set_status("Preparing graph", T.LOADER)

    def open_screen(self, name):
        """TREE / EXPLORE use what's in the input box (minus any command word)."""
        text = self.input.text.strip()
        word, _, rest = text.partition(" ")
        if word.lower() in ("tree", "explore", "check", "equiv", "derive"):
            text = rest
        if not text:
            example = "2sin(x)^2 + 3x" if name == "tree" else "a x^2 + b x + c"
            self.set_status(f"Type an expression first, e.g. {example}", T.ERROR)
            return
        self.app.go(name, text=text)

    def render_pod(self, pod, width):
        """Border colour shows the verdict: green proved/correct, amber evidence-only or needs care,
        red wrong, grey undecided. Everything else is gold."""
        title, content = pod[0], pod[1]
        border = T.YELLOW
        t = title.lower()
        if t.endswith("mistake here") or "does not follow" in t or title == "Error":
            border = T.ERROR
        elif t.endswith("check needed") or "checked numerically" in t:
            border = T.WARN
        elif t.endswith("couldn't check") or "could not be verified" in t:
            border = T.MUTED
        elif t.endswith("correct") or "verified symbolically" in t:
            border = T.GOOD
        elif title == "Verification":
            border = T.GOOD if content.startswith("Proved") else T.WARN if "not a proof" in content else T.ERROR
        elif title == "Verdict" and pod[1].startswith(("Equivalent", "Probably", "Not", "Unable")):
            border = T.GOOD if pod[1] == "Equivalent" or pod[1].startswith("Equivalent,") else \
                T.WARN if pod[1].startswith("Probably") else T.ERROR if pod[1].startswith("Not") else T.MUTED
        return self.cards.render_card(title, content, width, border=border)

    def set_status(self, text, color=T.MUTED):
        self.status, self.status_color = text, color

    def on_result(self, kind, result, error):
        if kind == "calc":
            if error is not None:
                result = engine.Response([("Error", f"Something went wrong: {error}")], "error")
            self.last = (self.pending_text, result)
            self.cards.load(result.pods, renderer=self.render_pod)
            if result.source == "local":
                self.set_status("Solved offline with SymPy")
            elif result.source == "wolfram":
                self.set_status("Answer from Wolfram|Alpha")
            else:
                self.set_status("")
            if result.ok:
                try:
                    self.app.history.save(self.pending_text, result.pods, result.source)
                    if self.pending_text in self.input.recall:
                        self.input.recall.remove(self.pending_text)
                    self.input.recall.insert(0, self.pending_text)
                except Exception as exc:
                    self.set_status(f"Couldn't save to history: {exc}", T.ERROR)
        elif kind == "plot":
            if result is None:
                self.set_status("Can't graph that. Try a function of one variable, like x^2 or sin(x)/x",
                                T.ERROR)
            else:
                self.set_status("")
                if self.app.scene is self:
                    self.app.go("graph", expr=result, label=self.pending_plot)

    # ---- loop ----------------------------------------------------------------
    def handle(self, e):
        if self.back_btn.clicked(e) or (e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE
                                        and not self.input.text):
            self.app.worker.cancel("calc")
            self.input.set_text("")
            self.cards.load([])
            self.set_status("")
            self.app.go("menu")
            return
        if self.graph_btn.clicked(e):
            self.open_graph()
            return
        if self.history_btn.clicked(e):
            self.app.go("history")
            return
        if self.tree_btn.clicked(e) or self.explore_btn.clicked(e):
            self.open_screen("tree" if self.tree_btn.clicked(e) else "explore")
            return
        if e.type == pygame.KEYDOWN and e.mod & pygame.KMOD_CTRL:
            if e.key in (pygame.K_t, pygame.K_e):
                self.open_screen("tree" if e.key == pygame.K_t else "explore")
                return
            if e.key == pygame.K_g:
                self.open_graph()
                return
            if e.key == pygame.K_h:
                self.app.go("history")
                return
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1 and not self.cards.cards:
            for rect, ex in self.example_rects:
                if rect.collidepoint(e.pos):
                    self.input.set_text(ex)
                    self.submit()
                    return
        if self.input.handle(e) == "submit":
            self.submit()
        self.cards.handle(e)

    def update(self, dt):
        self.input.update(dt)
        w = self.app.worker
        if w.busy("calc") and w.elapsed("calc") > TIMEOUT_S:
            w.cancel("calc")
            self.cards.load([("Timed out", "That took too long to compute. Try a simpler form, "
                                           "or ask for a specific operation (solve / factor / d/dx).")])
            self.set_status("")

    def draw(self, s):
        s.blit(self.app.bg_game, (0, 0))
        self.back_btn.draw(s)
        for b in (self.graph_btn, self.tree_btn, self.history_btn, self.explore_btn):
            b.draw(s)
        self.input.draw(s)

        status = self.status
        if self.app.worker.busy("calc") or self.app.worker.busy("plot"):
            status += "." * (pygame.time.get_ticks() // 300 % 4)
        if status:
            txt = T.font(18, True).render(status, True, self.status_color)
            s.blit(txt, (190, 192))

        if self.cards.cards:
            self.cards.draw(s)
        else:
            self.draw_examples(s)

    def draw_examples(self, s):
        title = T.display("Try one of these", 26, T.YELLOW)
        s.blit(title, (100, 250))
        x, y = 100, 292
        self.example_rects = []
        mouse = pygame.mouse.get_pos()
        for ex in EXAMPLES:
            t = T.font(20, True).render(ex, True, T.BLACK)
            r = t.get_rect(topleft=(x, y)).inflate(24, 14)
            r.topleft = (x, y)
            if r.right > 1180:
                x, y = 100, y + r.height + 18
                r.topleft = (x, y)
            hover = r.collidepoint(mouse)
            pygame.draw.rect(s, T.BLACK, r.move(4, 4))
            pygame.draw.rect(s, T.WHITE if hover else T.YELLOW, r)
            pygame.draw.rect(s, T.BLACK, r, 2)
            s.blit(t, t.get_rect(center=r.center))
            self.example_rects.append((r, ex))
            x = r.right + 18
        hint = T.font(17).render("Enter: solve   ·   ↑/↓: previous inputs   ·   Ctrl+G graph   ·   Ctrl+T tree   ·   "
                                 "Ctrl+E explore   ·   Ctrl+H history   ·   Esc: clear", True, T.MUTED)
        s.blit(hint, (100, y + 64))

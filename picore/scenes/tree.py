"""AST viewer: see how Pi Core actually reads an expression.

Hover a node to highlight its subtree (and the matching characters in the input);
click to select it and see its operator, precedence, operands and domain; press
SIMPLIFY to simplify just that subtree (verified by the equivalence engine).
Arrow keys walk the tree: up = parent, down = first child, left/right = siblings.
"""
from dataclasses import dataclass, field

import pygame

from ..engine.local import fmt
from ..lang import ParseError, parse
from ..lang import ast as A
from ..lang.sympy_backend import domain_conditions, to_sympy
from ..reasoning.equivalence import compare
from ..ui import theme as T
from ..ui.widgets import Button, wrap_text
from .simple import Scene

AREA = pygame.Rect(60, 150, 1160, 370)
PANEL = pygame.Rect(60, 532, 1000, 128)
FUNC_COLOR = (190, 160, 255)
LEAF_BG = (24, 24, 24)


@dataclass
class LNode:
    node: object
    path: tuple
    depth: int
    x: float = 0.0
    y: float = 0.0
    children: list = field(default_factory=list)
    rect: object = None


def layout(root):
    """Leaves take consecutive x slots; each parent sits centred over its children."""
    slots = [0]

    def build(node, path, depth):
        ln = LNode(node, path, depth)
        kids = A.children(node)
        if not kids:
            ln.x = slots[0]
            slots[0] += 1
        else:
            ln.children = [build(c, path + (i,), depth + 1) for i, c in enumerate(kids)]
            ln.x = (ln.children[0].x + ln.children[-1].x) / 2
        return ln

    top = build(root, (), 0)
    return top, slots[0]


def flatten(ln):
    yield ln
    for c in ln.children:
        yield from flatten(c)


def subtree_text(node):
    return A.to_text(node)


class TreeScene(Scene):
    def __init__(self, app):
        super().__init__(app)
        self.back_btn = Button("BACK", (90, 50), (120, 44), 30)
        self.simplify_btn = Button("SIMPLIFY", (1140, 575), (150, 44), 24)
        self.text = ""
        self.root = None
        self.error = None
        self.selected = ()
        self.result = None

    # ---- setup ---------------------------------------------------------------------
    def enter(self, text="", **kwargs):
        self.text, self.error, self.result = text.strip(), None, None
        self.selected = ()
        try:
            self.tree = parse(self.text)
        except ParseError as exc:
            self.root, self.error = None, exc
            return
        self.root, n_slots = layout(self.tree)
        nodes = list(flatten(self.root))
        depth = max(n.depth for n in nodes)
        dx = min(110, (AREA.w - 80) / max(1, n_slots - 1))
        dy = min(90, (AREA.h - 64) / max(1, depth))
        width = dx * (n_slots - 1)
        for n in nodes:
            n.x = AREA.centerx - width / 2 + n.x * dx
            n.y = AREA.y + 28 + n.depth * dy

    def find(self, path):
        n = self.root
        for i in path:
            n = n.children[i]
        return n

    # ---- input --------------------------------------------------------------------
    def handle(self, e):
        if self.back_btn.clicked(e) or (e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE):
            self.app.go("calc")
            return
        if self.root is None:
            return
        if self.simplify_btn.clicked(e):
            self.simplify_selected()
            return
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            hit = self.node_at(e.pos)
            if hit:
                self.select(hit.path)
        elif e.type == pygame.KEYDOWN:
            p = self.selected
            if e.key == pygame.K_UP and p:
                self.select(p[:-1])
            elif e.key == pygame.K_DOWN and self.find(p).children:
                self.select(p + (0,))
            elif e.key in (pygame.K_LEFT, pygame.K_RIGHT) and p:
                siblings = len(self.find(p[:-1]).children)
                step = -1 if e.key == pygame.K_LEFT else 1
                self.select(p[:-1] + ((p[-1] + step) % siblings,))
            elif e.key == pygame.K_s:
                self.simplify_selected()

    def select(self, path):
        self.selected = path
        self.result = None

    def node_at(self, pos):
        for n in flatten(self.root):
            if n.rect and n.rect.collidepoint(pos):
                return n
        return None

    def simplify_selected(self):
        node = self.find(self.selected).node
        if isinstance(node, (A.Equation, A.PlusMinus)):
            self.result = ("Select an expression (not '=' or '±') to simplify it.", T.MUTED)
            return
        self.result = ("Simplifying…", T.LOADER)
        self.app.worker.submit("tree_simplify", _simplify, node)

    def on_result(self, kind, result, error):
        if kind == "tree_simplify":
            self.result = (f"Couldn't simplify: {error}", T.ERROR) if error else result

    # ---- drawing -------------------------------------------------------------------
    def draw(self, s):
        s.blit(self.app.bg_game, (0, 0))
        self.back_btn.draw(s)
        title = T.display("Expression Tree", 36, T.YELLOW)
        s.blit(title, title.get_rect(center=(T.WIDTH // 2, 48)))
        if self.error:
            self.draw_source(s, None)
            msg = T.font(22, True).render(str(self.error), True, T.ERROR)
            s.blit(msg, msg.get_rect(center=(T.WIDTH // 2, 300)))
            return
        hover = self.node_at(pygame.mouse.get_pos())
        focus = hover or self.find(self.selected)
        self.draw_source(s, focus.node.span)
        inside = {n.path for n in flatten(focus)}
        pygame.draw.rect(s, T.GRAPH_BG, AREA)
        self.draw_edges(s, self.root, inside)
        for n in flatten(self.root):
            self.draw_node(s, n, n.path in inside, n.path == self.selected)
        pygame.draw.rect(s, T.YELLOW, AREA, 3)
        self.draw_panel(s, self.find(self.selected))
        hint = T.font(15).render("hover: highlight  ·  click: select  ·  ↑↓←→: walk the tree  ·  S: simplify  ·  Esc: back",
                                 True, T.MUTED)
        s.blit(hint, (60, PANEL.bottom + 10))

    def draw_source(self, s, span):
        """The input text, with the focused node's characters highlighted."""
        f = T.font(26, True)
        text = self.text
        a, b = span if span else (0, 0)
        parts = [(text[:a], T.TEXT_LIGHT, None), (text[a:b], T.BLACK, T.YELLOW), (text[b:], T.TEXT_LIGHT, None)]
        total = sum(f.size(p)[0] for p, _, _ in parts)
        x = T.WIDTH // 2 - total // 2
        for part, color, bg in parts:
            if not part:
                continue
            surf = f.render(part, True, color)
            if bg:
                pygame.draw.rect(s, bg, surf.get_rect(topleft=(x, 92)).inflate(6, 2))
            s.blit(surf, (x, 92))
            x += surf.get_width()
        if isinstance(self.error, ParseError) and self.error.pos is not None:   # caret under the problem
            cx = T.WIDTH // 2 - total // 2 + f.size(text[:self.error.pos])[0]
            pygame.draw.polygon(s, T.ERROR, [(cx, 128), (cx - 7, 140), (cx + 7, 140)])

    def draw_edges(self, s, n, inside):
        for c in n.children:
            lit = c.path in inside and n.path in inside
            pygame.draw.line(s, T.YELLOW if lit else (80, 80, 80), (n.x, n.y), (c.x, c.y), 3 if lit else 2)
            self.draw_edges(s, c, inside)

    def draw_node(self, s, n, highlighted, selected):
        node = n.node
        label = A.label(node)
        f = T.font(22, True)
        w = max(44, f.size(label)[0] + 22)
        rect = pygame.Rect(0, 0, w, 40)
        rect.center = (int(n.x), int(n.y))
        n.rect = rect
        if isinstance(node, (A.BinOp, A.Neg, A.PlusMinus, A.Factorial, A.Equation)):
            bg, fg = (T.YELLOW, T.BLACK)
        elif isinstance(node, (A.Call, A.Deriv)):
            bg, fg = (FUNC_COLOR, T.BLACK)
        else:
            bg, fg = (LEAF_BG, T.WHITE)
        if not highlighted:
            bg = tuple(int(c * 0.45) for c in bg)
            fg = tuple(int(c * 0.6) for c in fg) if fg == T.WHITE else fg
        pygame.draw.rect(s, bg, rect, border_radius=10)
        pygame.draw.rect(s, T.WHITE if selected else T.BLACK, rect, 3 if selected else 2, border_radius=10)
        t = f.render(label, True, fg)
        s.blit(t, t.get_rect(center=rect.center))

    def draw_panel(self, s, n):
        node = n.node
        pygame.draw.rect(s, T.BLACK, PANEL)
        pygame.draw.rect(s, T.YELLOW, PANEL, 2)
        lines = [f"Selected: {subtree_text(node)}",
                 f"Type: {A.kind(node)}" + (f"   ·   operator '{A.label(node)}'" if A.children(node) else "")
                 + f"   ·   precedence {A.precedence(node)} ({A.PRECEDENCE_NAMES[A.precedence(node)]})"]
        kids = A.children(node)
        if kids:
            lines.append("Operands: " + "   |   ".join(subtree_text(k) for k in kids))
        try:
            conds = domain_conditions(node)
            if conds:
                lines.append("Defined when: " + ";  ".join(c.describe() for c in conds))
        except Exception:
            pass
        y = PANEL.y + 10
        lines = lines[:4]
        for i, ln in enumerate(lines):
            f = T.font(19, True) if i == 0 else T.font(17)
            for part in wrap_text(ln, f, PANEL.w - 30)[:2]:
                s.blit(f.render(part, True, T.YELLOW if i == 0 else T.TEXT_LIGHT), (PANEL.x + 15, y))
                y += f.get_linesize()
        self.simplify_btn.draw(s)
        if self.result:
            text, color = self.result
            f = T.font(17, True)
            line = wrap_text(text, f, PANEL.w - 30)[0]
            s.blit(f.render(line, True, color), (PANEL.x + 15, PANEL.bottom - f.get_linesize() - 6))


def _simplify(node):
    """Simplify one subtree and verify the result with the equivalence engine."""
    import sympy as sp
    value = to_sympy(node)
    simplified = sp.simplify(value)
    if simplified == value:
        expanded = sp.expand(value)
        if expanded != value:
            simplified = expanded
    if simplified == value:
        return (f"{subtree_text(node)} is already as simple as SymPy can make it.", T.MUTED)
    verdict = compare(node, simplified)
    tag = {"exact": "verified", "conditional": "verified where defined", "numeric": "checked numerically"}.get(
        verdict.verdict, verdict.title.lower())
    extra = f" ({', '.join(verdict.restrictions)})" if verdict.restrictions else ""
    return (f"{subtree_text(node)}  =  {fmt(simplified)}   [{tag}{extra}]", T.GOOD)

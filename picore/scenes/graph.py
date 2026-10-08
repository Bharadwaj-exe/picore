"""Interactive graph drawn directly with pygame: scroll to zoom, drag to pan, hover to trace."""
import math

import numpy as np
import pygame
import sympy as sp

from ..engine.local import fmt
from ..ui import theme as T
from ..ui.widgets import Button
from .simple import Scene

PLOT = pygame.Rect(60, 100, 1160, 540)


def nice_step(span, target=10):
    raw = span / target
    mag = 10 ** math.floor(math.log10(raw))
    for m in (1, 2, 5, 10):
        if raw <= m * mag:
            return m * mag
    return 10 * mag


def tick_label(v, step):
    if abs(v) < step / 1e6:
        return "0"
    decimals = max(0, -int(math.floor(math.log10(step))))
    return f"{v:.{decimals}f}" if abs(v) < 1e6 else f"{v:.2e}"


class GraphScene(Scene):
    def __init__(self, app):
        super().__init__(app)
        self.back_btn = Button("BACK", (90, 50), (120, 44), 30)
        self.reset_btn = Button("RESET", (1150, 50), (130, 44), 28)

    def enter(self, expr=None, label="", **kwargs):
        self.expr = expr
        self.var = sorted(expr.free_symbols, key=lambda s: s.name)[0]
        self.label = f"y = {fmt(expr)}"
        self.error = None
        self.dragging = None
        try:
            self.fn = sp.lambdify(self.var, expr, modules="numpy")
        except Exception:
            self.fn, self.error = None, "This function can't be graphed"
        self.reset_view()

    # ---- sampling ------------------------------------------------------------
    def sample(self, xs):
        with np.errstate(all="ignore"):
            ys = self.fn(xs)
        ys = np.asarray(ys, dtype=complex) * np.ones_like(xs)
        real = np.where(np.abs(ys.imag) < 1e-9, ys.real, np.nan)
        return real.astype(float)

    def reset_view(self):
        self.x0, self.x1 = -10.0, 10.0
        self.y0, self.y1 = -10 * PLOT.h / PLOT.w, 10 * PLOT.h / PLOT.w
        if not self.fn:
            return
        try:
            ys = self.sample(np.linspace(self.x0, self.x1, 801))
        except Exception:
            self.fn, self.error = None, "This function can't be graphed"
            return
        finite = ys[np.isfinite(ys)]
        if finite.size:
            lo, hi = np.percentile(finite, [5, 95])
            if hi - lo < 1e-9:
                lo, hi = lo - 1, hi + 1
            pad = (hi - lo) * 0.25
            self.y0, self.y1 = float(lo - pad), float(hi + pad)
        self.points = None

    # ---- coordinate helpers --------------------------------------------------
    def to_px(self, x, y):
        px = PLOT.x + (x - self.x0) / (self.x1 - self.x0) * PLOT.w
        py = PLOT.bottom - (y - self.y0) / (self.y1 - self.y0) * PLOT.h
        return px, py

    def to_world(self, px, py):
        x = self.x0 + (px - PLOT.x) / PLOT.w * (self.x1 - self.x0)
        y = self.y0 + (PLOT.bottom - py) / PLOT.h * (self.y1 - self.y0)
        return x, y

    def zoom(self, factor, center):
        cx, cy = self.to_world(*center)
        self.x0, self.x1 = cx + (self.x0 - cx) * factor, cx + (self.x1 - cx) * factor
        self.y0, self.y1 = cy + (self.y0 - cy) * factor, cy + (self.y1 - cy) * factor

    # ---- loop ----------------------------------------------------------------
    def handle(self, e):
        if self.back_btn.clicked(e) or (e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE):
            self.app.go("calc")
            return
        if self.reset_btn.clicked(e) or (e.type == pygame.KEYDOWN and e.key == pygame.K_r):
            self.reset_view()
        elif e.type == pygame.MOUSEWHEEL:
            pos = pygame.mouse.get_pos()
            if PLOT.collidepoint(pos):
                self.zoom(0.85 if e.y > 0 else 1 / 0.85, pos)
        elif e.type == pygame.KEYDOWN and e.key in (pygame.K_PLUS, pygame.K_EQUALS, pygame.K_KP_PLUS):
            self.zoom(0.8, PLOT.center)
        elif e.type == pygame.KEYDOWN and e.key in (pygame.K_MINUS, pygame.K_KP_MINUS):
            self.zoom(1.25, PLOT.center)
        elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1 and PLOT.collidepoint(e.pos):
            self.dragging = e.pos
        elif e.type == pygame.MOUSEBUTTONUP and e.button == 1:
            self.dragging = None
        elif e.type == pygame.MOUSEMOTION and self.dragging:
            dx = (e.pos[0] - self.dragging[0]) / PLOT.w * (self.x1 - self.x0)
            dy = (e.pos[1] - self.dragging[1]) / PLOT.h * (self.y1 - self.y0)
            self.x0, self.x1 = self.x0 - dx, self.x1 - dx
            self.y0, self.y1 = self.y0 + dy, self.y1 + dy
            self.dragging = e.pos

    def draw(self, s):
        s.blit(self.app.bg_game, (0, 0))
        self.back_btn.draw(s)
        self.reset_btn.draw(s)
        title = T.font(26, True).render(self.label, True, T.YELLOW)
        if title.get_width() > 860:
            title = pygame.transform.smoothscale(title, (860, int(title.get_height() * 860 / title.get_width())))
        s.blit(title, title.get_rect(center=(T.WIDTH // 2, 50)))

        pygame.draw.rect(s, T.GRAPH_BG, PLOT)
        if self.error:
            msg = T.font(24, True).render(self.error, True, T.ERROR)
            s.blit(msg, msg.get_rect(center=PLOT.center))
        else:
            prev = s.get_clip()
            s.set_clip(PLOT)
            self.draw_grid(s)
            self.draw_curve(s)
            self.draw_trace(s)
            s.set_clip(prev)
        pygame.draw.rect(s, T.YELLOW, PLOT, 3)
        hint = T.font(16).render("scroll: zoom   ·   drag: pan   ·   R: reset   ·   hover: trace   ·   Esc: back",
                                 True, T.MUTED)
        s.blit(hint, hint.get_rect(midtop=(T.WIDTH // 2, PLOT.bottom + 12)))

    def draw_grid(self, s):
        small = T.font(14)
        for axis in ("x", "y"):
            lo, hi = (self.x0, self.x1) if axis == "x" else (self.y0, self.y1)
            step = nice_step(hi - lo)
            v = math.ceil(lo / step) * step
            while v <= hi:
                if axis == "x":
                    px, _ = self.to_px(v, 0)
                    pygame.draw.line(s, T.GRID, (px, PLOT.top), (px, PLOT.bottom))
                    if px < PLOT.left + 6 or px > PLOT.right - 40:
                        v += step
                        continue
                    _, ay = self.to_px(0, 0)
                    ly = min(max(ay + 4, PLOT.top + 4), PLOT.bottom - 18)
                    lab = small.render(tick_label(v, step), True, T.MUTED)
                    s.blit(lab, (px + 3, ly))
                else:
                    _, py = self.to_px(0, v)
                    pygame.draw.line(s, T.GRID, (PLOT.left, py), (PLOT.right, py))
                    ax, _ = self.to_px(0, 0)
                    lx = min(max(ax + 4, PLOT.left + 4), PLOT.right - 60)
                    if abs(v) > step / 1e6:
                        s.blit(small.render(tick_label(v, step), True, T.MUTED), (lx, py + 2))
                v += step
        ox, oy = self.to_px(0, 0)
        pygame.draw.line(s, T.WHITE, (PLOT.left, oy), (PLOT.right, oy), 2)
        pygame.draw.line(s, T.WHITE, (ox, PLOT.top), (ox, PLOT.bottom), 2)

    def draw_curve(self, s):
        xs = np.linspace(self.x0, self.x1, PLOT.w * 2)
        try:
            ys = self.sample(xs)
        except Exception:
            self.error = "This function can't be graphed"
            return
        seg = []
        limit = PLOT.h * 3
        prev_py = None
        for x, y in zip(xs, ys):
            if not np.isfinite(y):
                prev_py = None
                if len(seg) > 1:
                    pygame.draw.lines(s, T.YELLOW, False, seg, 3)
                seg = []
                continue
            px, py = self.to_px(x, y)
            py = max(-limit, min(limit + PLOT.bottom, py))
            if prev_py is not None and abs(py - prev_py) > PLOT.h:   # asymptote: break the line
                if len(seg) > 1:
                    pygame.draw.lines(s, T.YELLOW, False, seg, 3)
                seg = []
            seg.append((px, py))
            prev_py = py
        if len(seg) > 1:
            pygame.draw.lines(s, T.YELLOW, False, seg, 3)

    def draw_trace(self, s):
        mx, my = pygame.mouse.get_pos()
        if not PLOT.collidepoint(mx, my) or self.dragging:
            return
        x, _ = self.to_world(mx, my)
        try:
            y = float(self.sample(np.array([x]))[0])
        except Exception:
            return
        if not math.isfinite(y):
            return
        px, py = self.to_px(x, y)
        pygame.draw.line(s, (90, 90, 90), (px, PLOT.top), (px, PLOT.bottom))
        pygame.draw.circle(s, T.WHITE, (int(px), int(py)), 6)
        pygame.draw.circle(s, T.YELLOW, (int(px), int(py)), 6, 2)
        lab = T.font(18, True).render(f"({x:.4g}, {y:.4g})", True, T.BLACK)
        box = lab.get_rect(bottomleft=(px + 12, py - 10)).inflate(14, 8)
        box.clamp_ip(PLOT)
        pygame.draw.rect(s, T.YELLOW, box)
        s.blit(lab, lab.get_rect(center=box.center))

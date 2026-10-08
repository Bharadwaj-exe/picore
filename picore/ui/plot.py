"""Reusable interactive plot: grid, axes, curve, markers, zoom/pan/trace.

Used by the graph screen and the parameter explorer. The plot knows nothing about
SymPy: it draws whatever ``fn(xs) -> ys`` it is given (see ``sampler``).
"""
import math

import numpy as np
import pygame
import sympy as sp

from . import theme as T


def sampler(expr, var, params=()):
    """Vectorised numpy function f(xs, *param_values) -> real ys (NaN where complex/undefined)."""
    raw = sp.lambdify((var, *params), expr, modules="numpy")

    def fn(xs, *values):
        with np.errstate(all="ignore"):
            ys = raw(xs, *values)
        ys = np.asarray(ys, dtype=complex) * np.ones_like(xs)
        return np.where(np.abs(ys.imag) < 1e-9, ys.real, np.nan).astype(float)
    return fn


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


class Plot:
    def __init__(self, rect):
        self.rect = pygame.Rect(rect)
        self.fn = None
        self.error = None
        self.dragging = None
        self.x0, self.x1, self.y0, self.y1 = -10.0, 10.0, -5.0, 5.0

    # ---- view ----------------------------------------------------------------------
    def set_function(self, fn, fit=True):
        self.fn, self.error = fn, None
        if fit:
            self.reset_view()

    def sample(self, xs):
        return self.fn(xs)

    def reset_view(self):
        r = self.rect
        self.x0, self.x1 = -10.0, 10.0
        self.y0, self.y1 = -10 * r.h / r.w, 10 * r.h / r.w
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

    def to_px(self, x, y):
        r = self.rect
        return (r.x + (x - self.x0) / (self.x1 - self.x0) * r.w,
                r.bottom - (y - self.y0) / (self.y1 - self.y0) * r.h)

    def to_world(self, px, py):
        r = self.rect
        return (self.x0 + (px - r.x) / r.w * (self.x1 - self.x0),
                self.y0 + (r.bottom - py) / r.h * (self.y1 - self.y0))

    def zoom(self, factor, center):
        cx, cy = self.to_world(*center)
        self.x0, self.x1 = cx + (self.x0 - cx) * factor, cx + (self.x1 - cx) * factor
        self.y0, self.y1 = cy + (self.y0 - cy) * factor, cy + (self.y1 - cy) * factor

    # ---- input -------------------------------------------------------------------------
    def handle(self, e):
        """Zoom/pan events. Returns True if the event was used."""
        if e.type == pygame.MOUSEWHEEL and self.rect.collidepoint(pygame.mouse.get_pos()):
            self.zoom(0.85 if e.y > 0 else 1 / 0.85, pygame.mouse.get_pos())
            return True
        if e.type == pygame.KEYDOWN and e.key in (pygame.K_PLUS, pygame.K_EQUALS, pygame.K_KP_PLUS):
            self.zoom(0.8, self.rect.center)
            return True
        if e.type == pygame.KEYDOWN and e.key in (pygame.K_MINUS, pygame.K_KP_MINUS):
            self.zoom(1.25, self.rect.center)
            return True
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1 and self.rect.collidepoint(e.pos):
            self.dragging = e.pos
            return True
        if e.type == pygame.MOUSEBUTTONUP and e.button == 1 and self.dragging:
            self.dragging = None
            return True
        if e.type == pygame.MOUSEMOTION and self.dragging:
            r = self.rect
            dx = (e.pos[0] - self.dragging[0]) / r.w * (self.x1 - self.x0)
            dy = (e.pos[1] - self.dragging[1]) / r.h * (self.y1 - self.y0)
            self.x0, self.x1 = self.x0 - dx, self.x1 - dx
            self.y0, self.y1 = self.y0 + dy, self.y1 + dy
            self.dragging = e.pos
            return True
        return False

    # ---- drawing -----------------------------------------------------------------------
    def draw(self, s, markers=(), vlines=()):
        """``markers``: [(x, y, label, color)]; ``vlines``: [(x, color)] such as an axis of symmetry."""
        pygame.draw.rect(s, T.GRAPH_BG, self.rect)
        if self.error or not self.fn:
            msg = T.font(24, True).render(self.error or "Nothing to draw", True, T.ERROR)
            s.blit(msg, msg.get_rect(center=self.rect.center))
        else:
            prev = s.get_clip()
            s.set_clip(self.rect)
            self.draw_grid(s)
            for x, color in vlines:
                px, _ = self.to_px(x, 0)
                for yy in range(self.rect.top, self.rect.bottom, 12):     # dashed
                    pygame.draw.line(s, color, (px, yy), (px, yy + 6), 2)
            self.draw_curve(s)
            for x, y, label, color in markers:
                self.draw_marker(s, x, y, label, color)
            self.draw_trace(s)
            s.set_clip(prev)
        pygame.draw.rect(s, T.YELLOW, self.rect, 3)

    def draw_grid(self, s):
        r, small = self.rect, T.font(14)
        for axis in ("x", "y"):
            lo, hi = (self.x0, self.x1) if axis == "x" else (self.y0, self.y1)
            step = nice_step(hi - lo)
            v = math.ceil(lo / step) * step
            while v <= hi:
                if axis == "x":
                    px, _ = self.to_px(v, 0)
                    pygame.draw.line(s, T.GRID, (px, r.top), (px, r.bottom))
                    if r.left + 6 <= px <= r.right - 40:
                        _, ay = self.to_px(0, 0)
                        ly = min(max(ay + 4, r.top + 4), r.bottom - 18)
                        s.blit(small.render(tick_label(v, step), True, T.MUTED), (px + 3, ly))
                else:
                    _, py = self.to_px(0, v)
                    pygame.draw.line(s, T.GRID, (r.left, py), (r.right, py))
                    ax, _ = self.to_px(0, 0)
                    lx = min(max(ax + 4, r.left + 4), r.right - 60)
                    if abs(v) > step / 1e6:
                        s.blit(small.render(tick_label(v, step), True, T.MUTED), (lx, py + 2))
                v += step
        ox, oy = self.to_px(0, 0)
        pygame.draw.line(s, T.WHITE, (r.left, oy), (r.right, oy), 2)
        pygame.draw.line(s, T.WHITE, (ox, r.top), (ox, r.bottom), 2)

    def draw_curve(self, s):
        r = self.rect
        xs = np.linspace(self.x0, self.x1, r.w * 2)
        try:
            ys = self.sample(xs)
        except Exception:
            self.error = "This function can't be graphed"
            return
        px = r.x + (xs - self.x0) / (self.x1 - self.x0) * r.w
        py = r.bottom - (ys - self.y0) / (self.y1 - self.y0) * r.h
        limit = r.h * 3
        py = np.clip(py, -limit, r.bottom + limit)
        # break the line at undefined points and at asymptotes (huge jumps)
        ok = np.isfinite(py)
        jump = np.zeros_like(ok)
        jump[1:] = np.abs(np.diff(np.where(ok, py, 0))) > r.h
        breaks = ~ok | jump
        start = 0
        for i in list(np.nonzero(breaks)[0]) + [len(xs)]:
            if i - start > 1:
                pygame.draw.lines(s, T.YELLOW, False, list(zip(px[start:i], py[start:i])), 3)
            # after an undefined point, restart past it; after a jump, restart AT it
            start = i + 1 if i < len(xs) and not ok[i] else i

    def draw_marker(self, s, x, y, label, color):
        if not (math.isfinite(x) and math.isfinite(y)):
            return
        px, py = self.to_px(x, y)
        pygame.draw.circle(s, color, (int(px), int(py)), 7)
        pygame.draw.circle(s, T.BLACK, (int(px), int(py)), 7, 2)
        mx, my = pygame.mouse.get_pos()
        if label and (mx - px) ** 2 + (my - py) ** 2 < 18 ** 2:     # label on hover, so markers never pile up
            t = T.font(15, True).render(label, True, color)
            s.blit(t, (px + 10, py - 22))

    def draw_trace(self, s):
        mx, my = pygame.mouse.get_pos()
        if not self.rect.collidepoint(mx, my) or self.dragging:
            return
        x, _ = self.to_world(mx, my)
        try:
            y = float(self.sample(np.array([x]))[0])
        except Exception:
            return
        if not math.isfinite(y):
            return
        px, py = self.to_px(x, y)
        pygame.draw.line(s, (90, 90, 90), (px, self.rect.top), (px, self.rect.bottom))
        pygame.draw.circle(s, T.WHITE, (int(px), int(py)), 6)
        pygame.draw.circle(s, T.YELLOW, (int(px), int(py)), 6, 2)
        lab = T.font(18, True).render(f"({x:.4g}, {y:.4g})", True, T.BLACK)
        box = lab.get_rect(bottomleft=(px + 12, py - 10)).inflate(14, 8)
        box.clamp_ip(self.rect)
        pygame.draw.rect(s, T.YELLOW, box)
        s.blit(lab, lab.get_rect(center=box.center))

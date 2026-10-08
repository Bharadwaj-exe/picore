"""Hand-drawn UI components (no widget toolkit, same style as the original)."""
import pygame

from . import theme as T


def wrap_text(text, fnt, max_width):
    """Word-wrap ``text`` to ``max_width`` px, keeping line breaks and splitting over-long words."""
    lines = []
    for para in text.replace("\xa0", " ").split("\n"):
        current = ""
        for word in para.split(" "):
            while fnt.size(word)[0] > max_width:      # break words wider than the box
                cut = len(word)
                while cut > 1 and fnt.size(word[:cut])[0] > max_width:
                    cut -= 1
                if current:
                    lines.append(current)
                    current = ""
                lines.append(word[:cut])
                word = word[cut:]
            test = f"{current} {word}" if current else word
            if fnt.size(test)[0] <= max_width:
                current = test
            else:
                lines.append(current)
                current = word
        lines.append(current)
    while lines and not lines[-1].strip():
        lines.pop()
    return lines or [""]


class Button:
    def __init__(self, text, center, size, font_size=30):
        self.text = text
        self.rect = pygame.Rect(0, 0, *size)
        self.rect.center = center
        self.font_size = font_size

    def draw(self, s):
        hover = self.rect.collidepoint(pygame.mouse.get_pos())
        off = (-2, -2) if hover else (0, 0)
        sh = (6, 6) if hover else (4, 4)
        pygame.draw.rect(s, T.BLACK, self.rect.move(sh))
        pygame.draw.rect(s, T.YELLOW, self.rect.move(off))
        pygame.draw.rect(s, T.BLACK, self.rect.move(off), 3)
        t = T.font(self.font_size, True).render(self.text, True, T.BLACK)
        s.blit(t, t.get_rect(center=self.rect.move(off).center))

    def clicked(self, e):
        return e.type == pygame.MOUSEBUTTONDOWN and e.button == 1 and self.rect.collidepoint(e.pos)


def _clipboard_text():
    try:
        if hasattr(pygame.scrap, "get_text"):          # pygame-ce
            return pygame.scrap.get_text() or ""
        if not pygame.scrap.get_init():
            pygame.scrap.init()
        for kind in ("text/plain;charset=utf-8", pygame.SCRAP_TEXT):
            raw = pygame.scrap.get(kind)
            if raw:
                return raw.decode("utf-8", "ignore").replace("\x00", "")
    except (pygame.error, AttributeError):
        pass
    return ""


class TextInput:
    """The ε input card: cursor movement, paste, history recall, length limit."""

    MAX_LEN = 200

    def __init__(self, rect, placeholder="Enter Expression"):
        self.rect = pygame.Rect(rect)
        self.placeholder = placeholder
        self.text = ""
        self.cursor = 0
        self.active = True
        self.blink = 0
        self.recall = []        # past expressions, newest first
        self.recall_idx = -1

    @property
    def field(self):
        return pygame.Rect(self.rect.x + 70, self.rect.centery - 24, self.rect.width - 90, 48)

    def set_text(self, text):
        self.text = text[: self.MAX_LEN]
        self.cursor = len(self.text)
        self.recall_idx = -1

    def _insert(self, s):
        s = "".join(ch for ch in s if ch.isprintable())
        room = self.MAX_LEN - len(self.text)
        s = s[:room]
        self.text = self.text[: self.cursor] + s + self.text[self.cursor:]
        self.cursor += len(s)

    def handle(self, e):
        """Return 'submit' when Enter is pressed with non-empty text."""
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            self.active = self.rect.collidepoint(e.pos)
            return None
        if not self.active:
            return None
        if e.type == pygame.TEXTINPUT:
            self._insert(e.text)
            self.blink = 0
        elif e.type == pygame.KEYDOWN:
            self.blink = 0
            ctrl = e.mod & (pygame.KMOD_CTRL | pygame.KMOD_META)
            if e.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                return "submit" if self.text.strip() else None
            if e.key == pygame.K_BACKSPACE and self.cursor:
                start = self.cursor - 1
                if ctrl:  # delete previous word
                    while start > 0 and self.text[start - 1] != " ":
                        start -= 1
                self.text = self.text[:start] + self.text[self.cursor:]
                self.cursor = start
            elif e.key == pygame.K_DELETE:
                self.text = self.text[: self.cursor] + self.text[self.cursor + 1:]
            elif e.key == pygame.K_LEFT:
                self.cursor = max(0, self.cursor - 1)
            elif e.key == pygame.K_RIGHT:
                self.cursor = min(len(self.text), self.cursor + 1)
            elif e.key == pygame.K_HOME:
                self.cursor = 0
            elif e.key == pygame.K_END:
                self.cursor = len(self.text)
            elif e.key == pygame.K_ESCAPE:
                self.set_text("")
            elif e.key == pygame.K_v and ctrl:
                self._insert(_clipboard_text().replace("\n", " ").replace("\r", ""))
            elif e.key in (pygame.K_UP, pygame.K_DOWN) and self.recall:
                step = 1 if e.key == pygame.K_UP else -1
                self.recall_idx = max(-1, min(len(self.recall) - 1, self.recall_idx + step))
                text = self.recall[self.recall_idx] if self.recall_idx >= 0 else ""
                self.text, self.cursor = text, len(text)
        return None

    def update(self, dt_ms):
        self.blink = (self.blink + dt_ms) % 1000

    def draw(self, s):
        hover = self.rect.collidepoint(pygame.mouse.get_pos())
        offset = -6 if hover or self.active else 0
        shadow = 18 if hover or self.active else 10
        pygame.draw.rect(s, T.GOLD, self.rect.move(shadow, shadow))
        main = self.rect.move(offset, offset)
        pygame.draw.rect(s, T.PANEL, main)
        pygame.draw.rect(s, T.BLACK, main, 4)

        eps = T.font(40, True).render("ε", True, T.BLACK)
        s.blit(eps, eps.get_rect(center=(main.x + 38, main.centery)))

        fld = self.field.move(offset, offset)
        pygame.draw.rect(s, T.WHITE, fld)
        pygame.draw.rect(s, T.BLACK, fld, 3)

        fnt = T.font(24, True)
        inner = fld.inflate(-20, 0)
        if not self.text:
            ph = fnt.render(self.placeholder, True, T.PLACEHOLDER)
            s.blit(ph, ph.get_rect(midleft=(inner.x, fld.centery)))
            cursor_x = inner.x
        else:
            full = fnt.render(self.text, True, T.BLACK)
            cursor_px = fnt.size(self.text[: self.cursor])[0]
            scroll = max(0, cursor_px - inner.width + 4)   # keep the cursor in view
            prev_clip = s.get_clip()
            s.set_clip(inner)
            s.blit(full, full.get_rect(midleft=(inner.x - scroll, fld.centery)))
            s.set_clip(prev_clip)
            cursor_x = inner.x + cursor_px - scroll
        if self.active and self.blink < 500:
            h = fnt.get_height()
            pygame.draw.line(s, T.BLACK, (cursor_x, fld.centery - h // 2 + 2),
                             (cursor_x, fld.centery + h // 2 - 2), 2)


class CardList:
    """Scrollable, clipped stack of result cards; card surfaces are built once per load."""

    PAD = 16
    GAP = 20

    def __init__(self, area):
        self.area = pygame.Rect(area)
        self.cards = []         # [(surface, payload)]
        self.scroll = 0

    def load(self, items, renderer=None):
        """``items`` is a list of (title, content) or (title, content, payload).

        ``renderer(item, width)`` may replace the default card look.
        """
        width = self.area.width - 12
        render = renderer or (lambda it, w: self.render_card(it[0], it[1], w))
        self.cards = [(render(it, width), it[2] if len(it) > 2 else None) for it in items]
        self.scroll = 0

    def render_card(self, title, content, width, title_color=T.WHITE, border=T.YELLOW):
        ft, fb = T.font(22, True), T.font(19)
        lines = wrap_text(content, fb, width - 2 * self.PAD)
        line_h = fb.get_linesize()
        h = self.PAD + ft.get_linesize() + 6 + len(lines) * line_h + self.PAD
        surf = pygame.Surface((width, h))
        surf.fill(T.BLACK)
        pygame.draw.rect(surf, border, surf.get_rect(), 3)
        surf.blit(ft.render(title, True, title_color), (self.PAD, self.PAD - 4))
        y = self.PAD + ft.get_linesize() + 2
        for ln in lines:
            surf.blit(fb.render(ln, True, T.TEXT_LIGHT), (self.PAD, y))
            y += line_h
        return surf

    @property
    def content_height(self):
        return sum(c.get_height() + self.GAP for c, _ in self.cards)

    def scroll_by(self, dy):
        lowest = min(0, self.area.height - self.content_height)
        self.scroll = max(lowest, min(0, self.scroll + dy))

    def card_rects(self):
        y = self.area.y + self.scroll
        for surf, payload in self.cards:
            yield pygame.Rect(self.area.x, y, surf.get_width(), surf.get_height()), surf, payload
            y += surf.get_height() + self.GAP

    def hit(self, pos):
        if not self.area.collidepoint(pos):
            return None
        for rect, _, payload in self.card_rects():
            if rect.collidepoint(pos):
                return rect, payload
        return None

    def handle(self, e):
        if e.type == pygame.MOUSEWHEEL and self.area.collidepoint(pygame.mouse.get_pos()):
            self.scroll_by(e.y * 40)
        elif e.type == pygame.KEYDOWN and e.key in (pygame.K_PAGEUP, pygame.K_PAGEDOWN):
            self.scroll_by(self.area.height * 0.8 * (1 if e.key == pygame.K_PAGEUP else -1))

    def draw(self, s):
        mouse = pygame.mouse.get_pos()
        prev = s.get_clip()
        s.set_clip(self.area.inflate(12, 12))
        for rect, surf, _ in self.card_rects():
            if rect.bottom < self.area.top - 10 or rect.top > self.area.bottom + 10:
                continue
            off = 5 if rect.collidepoint(mouse) and self.area.collidepoint(mouse) else 0
            pygame.draw.rect(s, T.YELLOW, rect.move(-5, 5))
            s.blit(surf, rect.move(off, -off))
        s.set_clip(prev)
        if self.content_height > self.area.height:   # scrollbar
            frac = self.area.height / self.content_height
            bar_h = max(30, int(self.area.height * frac))
            span = self.area.height - bar_h
            pos = 0 if self.content_height == self.area.height else \
                -self.scroll / (self.content_height - self.area.height)
            bar = pygame.Rect(self.area.right + 8, self.area.y + int(span * pos), 6, bar_h)
            pygame.draw.rect(s, T.YELLOW, bar)

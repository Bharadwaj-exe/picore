import pygame
import subprocess
import sys
import os
from db import fetch_history, clear_history

pygame.init()
screen = pygame.display.set_mode((800, 600))
pygame.display.set_caption("πCore History")

font_title = pygame.font.SysFont("segoeui", 20, bold=True)
font_body = pygame.font.SysFont("segoeui", 16)

clear_btn = pygame.Rect(620, 10, 160, 35)

clock = pygame.time.Clock()
scroll = 0
ignore_first_click = True   # correct debounce

try:
    data = fetch_history(100)
except Exception as e:
    print("HISTORY DB ERROR:", e)
    data = []

expanded = set()

def wrap_text(text, font, max_width):
    text = text.replace("\xa0", " ").replace("\n", " ")
    words = text.split()
    lines, current = [], ""
    for w in words:
        test = current + w + " "
        if font.size(test)[0] <= max_width:
            current = test
        else:
            lines.append(current)
            current = w + " "
    if current:
        lines.append(current)
    return lines or [""]

running = True
while running:
    screen.fill((30, 30, 30))
    query_rects = []
    card_rects = []

    # ----- CLEAR HISTORY BUTTON -----
    pygame.draw.rect(screen, (180, 60, 60), clear_btn)
    pygame.draw.rect(screen, (255, 120, 120), clear_btn, 2)
    txt = font_body.render("CLEAR HISTORY", True, (255, 255, 255))
    screen.blit(txt, txt.get_rect(center=clear_btn.center))

    # ----- DRAW HISTORY -----
    y = 60 + scroll
    last_qid = None

    for qid, expr, time, title, content in data:
        if qid != last_qid:
            header = font_title.render(
                f"{expr}   [{time}]", True, (255, 215, 100)
            )
            rect = header.get_rect(topleft=(20, y))
            screen.blit(header, rect)
            query_rects.append((rect, expr))
            y += 30
            last_qid = qid

        key = (qid, title)
        is_open = key in expanded

        max_w = 700
        lines = wrap_text(content, font_body, max_w) if is_open else [content[:100]]
        line_h = font_body.get_height() + 2
        box_h = 30 + len(lines) * line_h

        box = pygame.Rect(40, y, 720, box_h)
        pygame.draw.rect(screen, (60, 60, 60), box)
        pygame.draw.rect(screen, (120, 120, 120), box, 2)

        t = font_body.render(title, True, (200, 200, 255))
        screen.blit(t, (box.x + 10, box.y + 5))

        ty = box.y + 25
        for ln in lines:
            txt = font_body.render(ln, True, (220, 220, 220))
            screen.blit(txt, (box.x + 10, ty))
            ty += line_h

        card_rects.append((box, key))
        y += box_h + 10

    pygame.display.flip()

    # ----- EVENTS -----
    for e in pygame.event.get():
        if e.type == pygame.QUIT:
            running = False

        if e.type == pygame.MOUSEWHEEL:
            scroll += e.y * 20

        if e.type == pygame.MOUSEBUTTONUP and e.button == 1:
            if ignore_first_click:
                ignore_first_click = False
                continue

            mx, my = e.pos

            if clear_btn.collidepoint(mx, my):
                clear_history()
                data = fetch_history(100)
                expanded.clear()
                continue

            for rect, expr in query_rects:
                if rect.collidepoint(mx, my):
                    pygame.quit()
                    subprocess.Popen(
                        [sys.executable, "Pi Core.py", expr],
                        cwd=os.path.dirname(__file__)
                    )
                    running = False
                    break

            for rect, key in card_rects:
                if rect.collidepoint(mx, my):
                    if key in expanded:
                        expanded.remove(key)
                    else:
                        expanded.add(key)
                    break

    clock.tick(60)

pygame.quit()

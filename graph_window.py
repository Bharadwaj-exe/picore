import sys
import pygame
import matplotlib.pyplot as plt
import numpy as np
import urllib.parse
import io

expr = urllib.parse.unquote_plus(sys.argv[1])

pygame.init()
screen = pygame.display.set_mode((640, 480))
pygame.display.set_caption("πCore Graph")
font = pygame.font.SysFont(None, 24)
clock = pygame.time.Clock()

def render_plot(expr):
    x = np.linspace(-10, 10, 1000)

    # normalize user math syntax → python syntax
    expr = expr.replace("^", "**")
    expr = expr.replace("sin", "np.sin")
    expr = expr.replace("cos", "np.cos")
    expr = expr.replace("tan", "np.tan")
    expr = expr.replace("log", "np.log")
    expr = expr.replace("ln", "np.log")
    expr = expr.replace("exp", "np.exp")

    try:
        y = eval(expr, {
            "x": x,
            "np": np,
            "__builtins__": {}
        })
    except Exception:
        return None

    buf = io.BytesIO()
    plt.figure(figsize=(6,4))
    plt.plot(x, y)
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(buf, format="png")
    plt.close()
    buf.seek(0)
    return pygame.image.load(buf)


    buf = io.BytesIO()
    plt.figure(figsize=(6,4))
    plt.plot(x, y)
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(buf, format="png")
    plt.close()
    buf.seek(0)
    return pygame.image.load(buf)

img = render_plot(expr)

running = True
while running:
    for e in pygame.event.get():
        if e.type == pygame.QUIT:
            running = False

    screen.fill((30,30,30))
    if img:
        img = pygame.transform.smoothscale(img, (620,420))
        screen.blit(img, (10,30))
    else:
        err = font.render("Invalid expression for plotting", True, (220,80,80))
        screen.blit(err, err.get_rect(center=screen.get_rect().center))

    pygame.display.flip()
    clock.tick(60)

pygame.quit()

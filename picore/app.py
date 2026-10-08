"""πCore application: one window, one process, scene-based."""
import os
import warnings

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
warnings.filterwarnings("ignore", category=UserWarning)  # pygame's pkg_resources notice

import pygame  # noqa: E402

from . import paths  # noqa: E402
from .config import Settings  # noqa: E402
from .storage import History  # noqa: E402
from .ui import theme as T  # noqa: E402
from .ui.widgets import Button  # noqa: E402
from .worker import Worker  # noqa: E402


class Music:
    def __init__(self, settings):
        self.settings = settings
        self.available = False
        try:
            pygame.mixer.init()
            pygame.mixer.music.load(paths.asset("bgmusic.mp3"))
            pygame.mixer.music.set_volume(0.6)
            pygame.mixer.music.play(-1)
            self.available = True
        except pygame.error:
            return  # no audio device or file: run silently
        if not self.on:
            pygame.mixer.music.pause()

    @property
    def on(self):
        return bool(self.settings.get("music_on"))

    def toggle(self):
        if not self.available:
            return
        self.settings.set("music_on", not self.on)
        if self.on:
            pygame.mixer.music.unpause()
        else:
            pygame.mixer.music.pause()


class App:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((T.WIDTH, T.HEIGHT), pygame.RESIZABLE | pygame.SCALED)
        pygame.display.set_caption("πCore")
        try:
            pygame.display.set_icon(pygame.image.load(paths.asset("picore_logo.png")).convert_alpha())
        except (pygame.error, FileNotFoundError):
            pass
        self.bg_menu = self._load_bg("background1.png", (8, 8, 8))
        self.bg_game = self._load_bg("background2.png", (8, 8, 8))
        pygame.key.set_repeat(400, 35)

        self.settings = Settings()
        self.history = History(paths.user_data_dir() / "history.db")
        self.worker = Worker()
        self.music = Music(self.settings)
        self.music_btn = Button("", (1170, 680), (190, 46), 26)
        self.clock = pygame.time.Clock()

        from .scenes.calc import CalcScene
        from .scenes.graph import GraphScene
        from .scenes.history import HistoryScene
        from .scenes.simple import LoadingScene, MenuScene
        from .scenes.explore import ExplorerScene
        from .scenes.tree import TreeScene
        self.scenes = {"loading": LoadingScene(self), "menu": MenuScene(self), "calc": CalcScene(self),
                       "history": HistoryScene(self), "graph": GraphScene(self), "tree": TreeScene(self),
                       "explore": ExplorerScene(self)}
        self.scene = None
        self.go("loading")

    def _load_bg(self, name, fallback):
        surf = pygame.Surface((T.WIDTH, T.HEIGHT))
        try:
            img = pygame.image.load(paths.asset(name)).convert()
            surf = pygame.transform.smoothscale(img, (T.WIDTH, T.HEIGHT))
        except (pygame.error, FileNotFoundError):
            surf.fill(fallback)
        return surf

    def go(self, name, **kwargs):
        self.scene = self.scenes[name]
        self.scene.enter(**kwargs)

    def run(self):
        running = True
        while running:
            dt = self.clock.tick(60)
            for kind, result, error in self.worker.poll():
                for sc in self.scenes.values():   # results go to whichever scene asked
                    if hasattr(sc, "on_result"):
                        sc.on_result(kind, result, error)
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    running = False
                elif (self.music.available and self.music_btn.clicked(e)
                      and self.scene is not self.scenes["loading"]):
                    self.music.toggle()
                else:
                    self.scene.handle(e)
            self.scene.update(dt)
            self.scene.draw(self.screen)
            if self.music.available and self.scene is not self.scenes["loading"]:
                self.music_btn.text = "MUSIC: ON" if self.music.on else "MUSIC: OFF"
                self.music_btn.draw(self.screen)
            pygame.display.flip()
        T.reset()
        pygame.quit()


def selftest(out_path):
    """Headless check used by build scripts: engine, assets and storage all work in this build."""
    import json
    from .engine import evaluate
    from .explore import analyze, make_experiment
    from .lang import parse
    from .lang import ast as A
    exp = make_experiment("a x^2 + b x + c")
    report = {
        "solve": dict(evaluate("2x+3=7").pods).get("Solution"),
        "check": evaluate("check x^2=4 -> x=2").pods[0][1],
        "diagnosis": evaluate("check d/dx(sin(3x)) -> cos(3x)").pods[2][1].splitlines()[1],
        "equiv": dict(evaluate("equiv (x^2-1)/(x-1) ; x+1").pods).get("Verdict"),
        "tree": A.to_text(parse("2sin(x)^2 + 3x")),
        "explore": analyze(exp).kind,
        "assets": all(os.path.exists(paths.asset(f)) for f in
                      ("background1.png", "background2.png", "picore_logo.png", "bgmusic.mp3")),
        "storage": History(paths.user_data_dir() / "history.db").fetch(1) is not None,
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False)


def main():
    if os.environ.get("PICORE_SELFTEST"):
        selftest(os.environ["PICORE_SELFTEST"])
        return
    App().run()

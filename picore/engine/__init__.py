"""Computation front door: local SymPy first, Wolfram|Alpha as fallback."""
from dataclasses import dataclass, field

from . import local, wolfram
from .parser import ParseError


@dataclass
class Response:
    pods: list = field(default_factory=list)   # [(title, content), ...]
    source: str = "local"                      # "local" | "wolfram" | "error"
    plot_expr: object = None                   # SymPy expr in one variable, or None

    @property
    def ok(self):
        return self.source != "error"


def evaluate(text, wolfram_app_id=None, wolfram_proxy=None):
    text = text.strip()
    reason = None
    try:
        pods, plot = local.compute(text)
        return Response(pods, "local", plot)
    except ParseError as exc:
        reason = str(exc)
    except (NotImplementedError, ValueError, TypeError, ZeroDivisionError, RecursionError) as exc:
        reason = f"Offline engine couldn't finish ({exc.__class__.__name__})"

    if wolfram_app_id or wolfram_proxy:
        try:
            return Response(wolfram.query(text, wolfram_app_id, wolfram_proxy), "wolfram")
        except wolfram.WolframError as exc:
            return Response([("Error", str(exc))], "error")

    return Response([("Couldn't solve that offline", reason),
                     ("Tip", "Word questions like 'distance to the moon' need the online engine "
                             "(Wolfram|Alpha AppID or proxy, see README).")], "error")


__all__ = ["evaluate", "Response", "ParseError"]

"""Computation front door: local SymPy first, Wolfram|Alpha only for word questions."""
import logging
from dataclasses import dataclass, field

from . import local, wolfram
from .parser import ParseError

log = logging.getLogger(__name__)

MAX_INPUT = 2000        # whole query (a 'check' chain); each expression is also limited by the lexer

# ParseErrors that mean "this is probably English, not maths": only these go to Wolfram|Alpha.
_WORDY = ("Unknown name", "Unexpected character")


@dataclass
class Response:
    pods: list = field(default_factory=list)   # [(title, content), ...]
    source: str = "local"                      # "local" | "wolfram" | "error"
    plot_expr: object = None                   # SymPy expr in one variable, or None

    @property
    def ok(self):
        return self.source != "error"


def _looks_like_words(exc):
    return isinstance(exc, ParseError) and exc.message.startswith(_WORDY)


def evaluate(text, wolfram_app_id=None, wolfram_proxy=None):
    text = text.strip()
    if len(text) > MAX_INPUT:
        return Response([("Input too long", f"Please keep a query under {MAX_INPUT} characters.")], "error")
    try:
        pods, plot = local.compute(text)
        return Response(pods, "local", plot)
    except ParseError as exc:
        if not _looks_like_words(exc):                 # malformed maths or a size limit: explain locally
            return Response([("Couldn't read that", str(exc))], "error")
        reason = str(exc)
    except (NotImplementedError, ValueError, TypeError, ZeroDivisionError, RecursionError) as exc:
        log.info("local engine could not finish %r: %s", text, exc)
        reason = f"The offline engine couldn't finish this ({exc.__class__.__name__})."
    except Exception:                                  # a bug: keep the app alive and leave a trace
        log.exception("internal error while evaluating %r", text)
        return Response([("Internal error", "Something went wrong while computing this. The details were "
                                            "written to the log file (see README, 'Logs').")], "error")

    if wolfram_app_id or wolfram_proxy:
        try:
            return Response(wolfram.query(text, wolfram_app_id, wolfram_proxy), "wolfram")
        except wolfram.WolframError as exc:
            return Response([("Error", str(exc))], "error")

    return Response([("Couldn't solve that offline", reason),
                     ("Tip", "Word questions like 'distance to the moon' need the online engine "
                             "(Wolfram|Alpha AppID or proxy, see README).")], "error")


__all__ = ["evaluate", "Response", "ParseError"]

"""Diagnostics: a small rotating log file in the user data folder.

Internal errors (failed background jobs, rules that raised, uncaught exceptions) are
recorded here with tracebacks, so a user can send the file when something goes wrong.
The file never contains configuration secrets: nothing in Pi Core logs the AppID.
"""
import logging
import logging.handlers
import sys
import threading

LOG_NAME = "picore.log"
MAX_BYTES = 500_000
BACKUPS = 2

_configured = False


def setup(folder, level=logging.INFO):
    """Log the 'picore' package to <folder>/picore.log (rotated). Safe to call more than once."""
    global _configured
    logger = logging.getLogger("picore")
    logger.setLevel(level)
    if _configured:
        return folder / LOG_NAME
    try:
        handler = logging.handlers.RotatingFileHandler(folder / LOG_NAME, maxBytes=MAX_BYTES,
                                                       backupCount=BACKUPS, encoding="utf-8")
    except OSError:
        handler = logging.StreamHandler(sys.stderr)     # read-only folder: still log somewhere
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logger.addHandler(handler)

    def log_uncaught(exc_type, exc, tb):
        logger.critical("uncaught exception", exc_info=(exc_type, exc, tb))
        sys.__excepthook__(exc_type, exc, tb)

    def log_thread(args):
        logger.error("uncaught exception in thread %s", args.thread.name if args.thread else "?",
                     exc_info=(args.exc_type, args.exc_value, args.exc_traceback))

    sys.excepthook = log_uncaught
    threading.excepthook = log_thread
    _configured = True
    return folder / LOG_NAME

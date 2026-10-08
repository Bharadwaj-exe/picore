"""Run slow work (math, network) off the render loop."""
import queue
import threading
import time


class Worker:
    """Fire-and-forget background jobs whose results are polled each frame.

    Only the latest job per ``kind`` is delivered, so a stale or timed-out
    answer can never overwrite a newer one.
    """

    def __init__(self):
        self._done = queue.Queue()
        self._latest = {}   # kind -> (job_id, started_at)
        self._next_id = 0

    def submit(self, kind, fn, *args):
        self._next_id += 1
        job_id = self._next_id
        self._latest[kind] = (job_id, time.monotonic())

        def run():
            try:
                result, error = fn(*args), None
            except Exception as exc:  # surfaced to the UI, never crashes the app
                result, error = None, exc
            self._done.put((kind, job_id, result, error))

        threading.Thread(target=run, daemon=True).start()
        return job_id

    def busy(self, kind):
        return kind in self._latest

    def elapsed(self, kind):
        job = self._latest.get(kind)
        return time.monotonic() - job[1] if job else 0.0

    def cancel(self, kind):
        self._latest.pop(kind, None)

    def poll(self):
        """Yield (kind, result, error) for finished jobs that are still wanted."""
        while True:
            try:
                kind, job_id, result, error = self._done.get_nowait()
            except queue.Empty:
                return
            if self._latest.get(kind, (None,))[0] == job_id:
                del self._latest[kind]
                yield kind, result, error

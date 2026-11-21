"""Very small background-job registry (threads). Good for a single-user / small-team server."""
import threading
import time
import uuid
from typing import Any, Callable

_jobs: dict[str, "Job"] = {}
_lock = threading.Lock()


class Job:
    def __init__(self, kind: str):
        self.id = uuid.uuid4().hex[:12]
        self.kind = kind
        self.status = "queued"        # queued | running | done | error
        self.progress = 0
        self.message = "Waiting to start"
        self.result: Any = None
        self.error: str | None = None
        self.created = time.time()

    def update(self, percent: float, message: str | None = None) -> None:
        self.progress = max(self.progress, min(99, int(percent)))
        if message:
            self.message = message

    def public(self) -> dict[str, Any]:
        return {"id": self.id, "kind": self.kind, "status": self.status, "progress": self.progress,
                "message": self.message, "result": self.result if self.status == "done" else None, "error": self.error}


def start_job(kind: str, work: Callable[[Job], Any], friendly_errors: tuple[type[Exception], ...] = ()) -> Job:
    job = Job(kind)
    with _lock:
        for old_id in [k for k, v in _jobs.items() if time.time() - v.created > 6 * 3600]:
            _jobs.pop(old_id, None)
        _jobs[job.id] = job

    def run() -> None:
        job.status = "running"
        try:
            job.result = work(job)
            job.status, job.progress, job.message = "done", 100, "Done"
        except friendly_errors as exc:
            job.status, job.error = "error", str(exc)
        except Exception as exc:  # never let a worker die silently
            job.status, job.error = "error", f"{type(exc).__name__}: {exc}"

    threading.Thread(target=run, daemon=True).start()
    return job


def get_job(job_id: str) -> Job | None:
    return _jobs.get(job_id)

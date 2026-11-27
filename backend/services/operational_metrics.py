"""Process-local operational counters, not a durable monitoring backend."""

from threading import Lock

_lock = Lock()
_requests = 0
_errors = 0
_duration = 0.0


def record_request(status, seconds):
    global _requests, _errors, _duration
    with _lock:
        _requests += 1
        _errors += int(status >= 500)
        _duration += seconds


def snapshot():
    with _lock:
        return {"requests": _requests, "server_errors": _errors,
                "request_duration_seconds_sum": _duration,
                "scope": "current process since startup"}

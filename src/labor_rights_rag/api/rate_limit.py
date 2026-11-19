"""A per-client limit on /ask, kept in the memory of the process (ADR-0013).

"At most `limit` questions in any `window_seconds` ending now." Each question can call a
paid model, so one client must not be able to send them in a loop.
"""

import math
import time
from collections import deque
from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException, Request


class SlidingWindowLimiter:
    def __init__(
        self, limit: int, window_seconds: float, clock: Callable[[], float] = time.monotonic
    ) -> None:
        self._limit = limit
        self._window = window_seconds
        # Injected so tests move time by hand instead of sleeping.
        self._clock = clock
        self._requests: dict[str, deque[float]] = {}

    def check(self, key: str) -> float:
        """0 if the request may go ahead (it is then counted), otherwise seconds to wait.

        A refused request is not counted: otherwise a client that keeps trying would stay
        blocked forever.
        """
        now = self._clock()
        times = self._requests.setdefault(key, deque())
        while times and times[0] <= now - self._window:
            times.popleft()
        if len(times) < self._limit:
            times.append(now)
            return 0.0
        return times[0] + self._window - now


def limit_ask(request: Request) -> None:
    """429 with Retry-After once a client address has asked too much. The address is the
    connection's, never X-Forwarded-For, which any client can set to anything."""
    limiter: SlidingWindowLimiter = request.app.state.ask_limiter
    address = request.client.host if request.client else "unknown"
    wait = limiter.check(address)
    if wait > 0:
        raise HTTPException(
            status_code=429,
            detail="Too many questions, please wait",
            headers={"Retry-After": str(max(1, math.ceil(wait)))},
        )


AskLimit = Annotated[None, Depends(limit_ask)]

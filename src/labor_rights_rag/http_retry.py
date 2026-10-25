"""Try an HTTP request again after a short wait when the failure is likely to pass."""

import asyncio
from collections.abc import Awaitable, Callable, Sequence

import httpx

RETRYABLE_STATUS = (429, 500, 502, 503, 504)


async def with_retries(
    send: Callable[[], Awaitable[httpx.Response]], delays: Sequence[float]
) -> httpx.Response:
    """Send the request; on a dropped connection or a retryable status wait and send again.

    There is one try more than there are delays. If the last try still has a retryable status
    the response is returned, and the caller decides what to say about it (it has the body).
    A dropped connection on the last try is raised as the original `httpx.TransportError`.
    """
    for delay in (*delays, None):
        try:
            response = await send()
            if response.status_code not in RETRYABLE_STATUS or delay is None:
                return response
        except httpx.TransportError:
            if delay is None:
                raise
        await asyncio.sleep(delay)
    raise AssertionError("unreachable")  # the loop above always returns or raises

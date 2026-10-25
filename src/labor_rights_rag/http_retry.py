"""Try an HTTP request again after a short wait when the failure is likely to pass."""

import asyncio
from collections.abc import Awaitable, Callable, Sequence

import httpx

RETRYABLE_STATUS = (429, 500, 502, 503, 504)


async def with_retries(
    send: Callable[[], Awaitable[httpx.Response]], delays: Sequence[float]
) -> httpx.Response:
    """Send the request; on a dropped connection or a retryable status wait and send again.

    There is one try more than there are delays. The last failure is raised: a status as
    `httpx.HTTPStatusError`, a dropped connection as the original `httpx.TransportError`.
    """
    for delay in (*delays, None):
        try:
            response = await send()
            if response.status_code not in RETRYABLE_STATUS:
                return response
            error: Exception = httpx.HTTPStatusError(
                f"HTTP {response.status_code}", request=response.request, response=response
            )
        except httpx.TransportError as transport_error:
            error = transport_error
        if delay is None:
            raise error
        await asyncio.sleep(delay)
    raise AssertionError("unreachable")  # the loop above always returns or raises

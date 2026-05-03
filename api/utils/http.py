from __future__ import annotations

from typing import Any

import httpx
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential


async def fetch_with_retry(
    url: str,
    *,
    method: str = "GET",
    retries: int = 3,
    backoff: float = 1.5,
    timeout: float = 20.0,
    **kwargs: Any,
) -> httpx.Response:
    """Fetch a URL with bounded retries for transient network/API failures."""
    async for attempt in AsyncRetrying(
        stop=stop_after_attempt(max(retries, 1)),
        wait=wait_exponential(multiplier=max(backoff, 0.1), min=0.2, max=10.0),
        retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError)),
        reraise=True,
    ):
        with attempt:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.request(method.upper(), url, **kwargs)
                response.raise_for_status()
                return response

    raise RuntimeError("unreachable")

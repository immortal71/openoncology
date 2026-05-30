from __future__ import annotations

from typing import Any

import httpx
from fastapi import HTTPException, Request, status
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


def api_error(
    request: Request,
    *,
    status_code: int,
    error: str,
    detail: str,
) -> HTTPException:
    """Build a standardized HTTPException payload consumed by global handlers."""
    return HTTPException(
        status_code=status_code,
        detail={
            "error": error,
            "detail": detail,
            "request_id": getattr(request.state, "request_id", None),
        },
    )


def not_found_error(request: Request, detail: str) -> HTTPException:
    return api_error(
        request,
        status_code=status.HTTP_404_NOT_FOUND,
        error="not_found",
        detail=detail,
    )


def validation_error(request: Request, detail: str) -> HTTPException:
    return api_error(
        request,
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        error="validation_error",
        detail=detail,
    )


def conflict_error(request: Request, detail: str) -> HTTPException:
    return api_error(
        request,
        status_code=status.HTTP_409_CONFLICT,
        error="conflict",
        detail=detail,
    )


def forbidden_error(request: Request, detail: str) -> HTTPException:
    return api_error(
        request,
        status_code=status.HTTP_403_FORBIDDEN,
        error="forbidden",
        detail=detail,
    )


def bad_request_error(request: Request, detail: str) -> HTTPException:
    return api_error(
        request,
        status_code=status.HTTP_400_BAD_REQUEST,
        error="bad_request",
        detail=detail,
    )

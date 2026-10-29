"""
Helpers for mocking the Bento authorization service's /policy/evaluate endpoint.

Queued results are consumed in order, with the last one repeating once the queue is exhausted.
"""

__all__ = [
    "install",
    "authz_everything_true",
    "authz_everything_false",
    "authz_drs_specific_obj",
]

_queue: list[list[list[bool]]] = []

# Headers which would have been sent to the authorization service with each request, for assertions
request_headers: list[dict[str, str]] = []


async def _async_authz_post(self, request, _path, _body, require_token=False, headers_getter=None) -> dict:
    request_headers.append(self._extract_token_and_build_headers(request, require_token, headers_getter))
    return {"result": _queue.pop(0) if len(_queue) > 1 else _queue[0]}


def install(monkeypatch) -> None:
    from bento_lib.auth.middleware.base import BaseAuthMiddleware

    _queue.clear()
    request_headers.clear()
    monkeypatch.setattr(BaseAuthMiddleware, "async_authz_post", _async_authz_post)


def authz_everything_true(count: int = 1) -> None:
    _queue.append([[True] for _ in range(count)])


def authz_everything_false(count: int = 1) -> None:
    _queue.append([[False] for _ in range(count)])


def authz_drs_specific_obj(iters: int = 1) -> None:
    for _ in range(iters):
        authz_everything_false()
        authz_everything_true()

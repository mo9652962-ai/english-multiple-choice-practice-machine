"""Shared pytest isolation for process-global application state."""

import pytest


@pytest.fixture(autouse=True)
def reset_security_rate_limiter():
    """Keep TestClient requests in one test from throttling the next test.

    Production rate limiting remains process-global.  The fixture only clears
    its in-memory window around each isolated test because the test suite uses
    many temporary databases but shares one imported FastAPI application.
    """
    from backend.app import security_middleware

    with security_middleware._requests_lock:
        security_middleware._requests.clear()
    yield
    with security_middleware._requests_lock:
        security_middleware._requests.clear()

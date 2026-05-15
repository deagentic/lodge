import secrets
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles

from ...domain.config import settings
from .routers import health, ingest, query

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent

_AUTH_REALM = 'Basic realm="Lodge Dashboard"'

app = FastAPI(
    title=settings.app_title,
    version=settings.app_version,
    description="A FastAPI + PostgreSQL service scaffolded by Cornerstone",
)

# ---------------------------------------------------------------------------
# HTTP Basic Auth — F7 (ADR-0007)
# Enabled when DASHBOARD_USERNAME and DASHBOARD_PASSWORD are set in .env.
# Skipped transparently when both are empty (local-dev convenience).
# ---------------------------------------------------------------------------

_basic_security = HTTPBasic(auto_error=False)


def _require_dashboard_auth(
    credentials: HTTPBasicCredentials | None = Depends(_basic_security),
) -> None:
    expected_user = settings.dashboard_username
    expected_pass = settings.dashboard_password

    if not expected_user and not expected_pass:
        # Auth not configured — allow (dev/local mode)
        return

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": _AUTH_REALM},
        )

    user_ok = secrets.compare_digest(
        credentials.username.encode(), expected_user.encode()
    )
    pass_ok = secrets.compare_digest(
        credentials.password.encode(), expected_pass.encode()
    )

    if not (user_ok and pass_ok):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": _AUTH_REALM},
        )


app.include_router(health.router)
app.include_router(ingest.router)
app.include_router(query.router, dependencies=[Depends(_require_dashboard_auth)])

# Serve the plain HTML dashboard at /
# The StaticFiles mount itself is not behind FastAPI middleware, so the auth
# dependency on query.router covers the /v1/query API. For the static dashboard,
# a middleware approach is used below.


@app.middleware("http")
async def dashboard_auth_middleware(request, call_next):
    """Enforce HTTP Basic Auth on the static dashboard (paths not handled by routers)."""
    expected_user = settings.dashboard_username
    expected_pass = settings.dashboard_password

    if not expected_user and not expected_pass:
        return await call_next(request)

    # Paths handled by API routers already have Depends() auth — skip re-checking
    api_prefixes = ("/health", "/v1/")
    if any(request.url.path.startswith(p) for p in api_prefixes):
        return await call_next(request)

    import base64

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Basic "):
        from starlette.responses import Response

        return Response(
            status_code=401,
            headers={"WWW-Authenticate": _AUTH_REALM},
        )

    try:
        decoded = base64.b64decode(auth_header[6:]).decode()
        username, _, password = decoded.partition(":")
    except Exception:  # pylint: disable=broad-exception-caught
        from starlette.responses import Response

        return Response(status_code=401, headers={"WWW-Authenticate": "Basic"})

    user_ok = secrets.compare_digest(username.encode(), expected_user.encode())
    pass_ok = secrets.compare_digest(password.encode(), expected_pass.encode())

    if not (user_ok and pass_ok):
        from starlette.responses import Response

        return Response(
            status_code=401,
            headers={"WWW-Authenticate": _AUTH_REALM},
        )

    return await call_next(request)


app.mount("/", StaticFiles(directory=str(_PROJECT_ROOT / "dashboard" / "static"), html=True), name="dashboard")

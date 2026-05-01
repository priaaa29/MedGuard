import logging

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api import accounts, prescriptions, routines
from app.config import CORS_ORIGINS, IS_PRODUCTION
from app.db import get_db

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("medguard")

UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
SECURITY_HEADERS = {
    # Responses carry health information: never store them in any cache.
    "Cache-Control": "no-store",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "X-Frame-Options": "DENY",
}

# Schema is managed by Alembic (`alembic upgrade head`), not created at startup.
app = FastAPI(
    title="MedGuard API",
    version="0.4.0",
    # Interactive docs are handy locally but just extra surface in production.
    docs_url=None if IS_PRODUCTION else "/docs",
    redoc_url=None,
    openapi_url=None if IS_PRODUCTION else "/openapi.json",
)


@app.middleware("http")
async def reject_cross_site_writes(request: Request, call_next):
    """CSRF defence on top of SameSite=Lax cookies.

    Browsers send Origin on every cross-site request and on same-origin writes,
    so a write whose Origin isn't ours came from another site. Requests without
    Origin (curl, tests, server-side calls) carry no browser cookies to abuse.
    """
    origin = request.headers.get("origin")
    if request.method in UNSAFE_METHODS and origin and origin not in CORS_ORIGINS:
        return JSONResponse({"detail": "Cross-site request blocked."}, status_code=403)
    return await call_next(request)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    for name, value in SECURITY_HEADERS.items():
        response.headers.setdefault(name, value)
    return response


@app.exception_handler(Exception)
async def unhandled_error(request: Request, exc: Exception):
    # Log the details server-side; never send stack traces or internals to the client.
    logger.exception("unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        {"detail": "Something went wrong on our side. Please try again."},
        status_code=500,
        headers=SECURITY_HEADERS,
    )


app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Content-Type"],
)

app.include_router(accounts.router)
app.include_router(prescriptions.router)
app.include_router(routines.router)


@app.get("/api/health")
def health(db: Session = Depends(get_db)):
    """Liveness + database reachability, for the host's health checks."""
    try:
        db.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001
        logger.exception("health check: database unreachable")
        return JSONResponse({"status": "error", "database": "unreachable"}, status_code=503)
    return {"status": "ok"}

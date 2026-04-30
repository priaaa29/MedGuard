import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import accounts, prescriptions, routines
from app.config import CORS_ORIGINS
from app.db import init_db

logging.basicConfig(level=logging.INFO)

UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


@asynccontextmanager
async def lifespan(_: FastAPI):
    # create_all is fine while the schema is new; switch to Alembic before the
    # first change to an existing production table.
    init_db()
    yield


app = FastAPI(title="MedGuard API", version="0.3.0", lifespan=lifespan)


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
def health():
    return {"status": "ok"}

import json as _json
import logging
import os
import sys
import uuid
from contextlib import asynccontextmanager
from contextvars import ContextVar

from dotenv import find_dotenv, load_dotenv
from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy.orm import Session
from sqlalchemy.sql import text
from starlette.middleware.base import BaseHTTPMiddleware

from database import SessionLocal, get_db
from limiter import limiter
from routers import admin as admin_router
from routers import auth as auth_router
from routers import cardio as cardio_router
from routers import exercises as exercises_router
from routers import gdpr as gdpr_router
from routers import logs as logs_router
from routers import measurements as measurements_router
from routers import profile as profile_router
from routers import progress as progress_router
from routers import sessions as sessions_router
from routers import stats as stats_router
from seed import seed_exercises

load_dotenv(find_dotenv())

_request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")


class RequestIDFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = _request_id_ctx.get()  # type: ignore[attr-defined]
        return True


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        record.message = record.getMessage()
        return _json.dumps(
            {
                "time": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
                "level": record.levelname,
                "logger": record.name,
                "request_id": getattr(record, "request_id", "-"),
                "message": record.message,
            }
        )


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s [%(request_id)s]: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
_request_id_filter = RequestIDFilter()
_use_json = os.getenv("FITMAN_LOG_FORMAT", "json") != "text"
for _h in logging.root.handlers:
    _h.addFilter(_request_id_filter)
    if _use_json:
        _h.setFormatter(JSONFormatter())

logger = logging.getLogger(__name__)

_REQUIRED = ["SECRET_KEY"]
_missing = [v for v in _REQUIRED if not os.getenv(v)]
if _missing:
    print(f"ERROR: Missing required environment variables: {', '.join(_missing)}")
    print("Copy .env.example to .env and fill in the values.")
    sys.exit(1)


@asynccontextmanager
async def lifespan(app: FastAPI):
    db = SessionLocal()
    try:
        seed_exercises(db)
    finally:
        db.close()
    yield


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        token = _request_id_ctx.set(request_id)
        try:
            logger.info("%s %s", request.method, request.url.path)
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            _request_id_ctx.reset(token)


app = FastAPI(title="Fitman API", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]

origins = [
    o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
]

app.add_middleware(RequestIDMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(admin_router.router)
app.include_router(auth_router.router)
app.include_router(exercises_router.router)
app.include_router(sessions_router.router)
app.include_router(logs_router.router)
app.include_router(progress_router.router)
app.include_router(measurements_router.router)
app.include_router(cardio_router.router)
app.include_router(gdpr_router.router)
app.include_router(profile_router.router)
app.include_router(stats_router.router)


@app.get("/health")
def health(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ok"}
    except Exception:
        logger.exception("Health check: database unavailable")
        return JSONResponse(
            status_code=503,
            content={"status": "error", "detail": "database unavailable"},
        )

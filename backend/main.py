import os
import sys
from contextlib import asynccontextmanager

from dotenv import find_dotenv, load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import SessionLocal
from routers import auth as auth_router
from routers import cardio as cardio_router
from routers import exercises as exercises_router
from routers import logs as logs_router
from routers import measurements as measurements_router
from routers import profile as profile_router
from routers import progress as progress_router
from routers import sessions as sessions_router
from routers import stats as stats_router
from seed import seed_exercises

load_dotenv(find_dotenv())

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


app = FastAPI(title="Fitman API", lifespan=lifespan)

origins = [
    o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(auth_router.router)
app.include_router(exercises_router.router)
app.include_router(sessions_router.router)
app.include_router(logs_router.router)
app.include_router(progress_router.router)
app.include_router(measurements_router.router)
app.include_router(cardio_router.router)
app.include_router(profile_router.router)
app.include_router(stats_router.router)


@app.get("/health")
def health():
    return {"status": "ok"}

"""FastAPI application entry point for Gait Analysis Backend MVP."""
import platform
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from src.database.database import init_db
from src.api.routes import subjects, sessions, uploads, analysis, jobs, assessments, reports, progress
from src.api.error_handlers import validation_exception_handler, generic_exception_handler, gait_exception_handler
from src.api.middleware import RequestTimingMiddleware
from src.core.exceptions import GaitAnalysisError
from src.core.logging import get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing database...")
    init_db()
    logger.info("Database ready.")
    yield


app = FastAPI(
    title="Gait Analysis Backend API",
    description="Evidence-based gait analysis backend \u2014 Milestones 1\u20136",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(RequestTimingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(GaitAnalysisError, gait_exception_handler)

# Register routers
app.include_router(subjects.router)
app.include_router(sessions.router)
app.include_router(uploads.router)
app.include_router(analysis.router)
app.include_router(jobs.router)
app.include_router(assessments.router)
app.include_router(reports.router)
app.include_router(progress.router)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/v1/system/status")
def system_status():
    cuda_available = False
    try:
        import torch
        cuda_available = torch.cuda.is_available()
    except Exception:
        pass

    return {
        "status": "ok",
        "python": platform.python_version(),
        "platform": platform.system(),
        "cuda_available": cuda_available,
        "api_version": "1.0.0",
    }

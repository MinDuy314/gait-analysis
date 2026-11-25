from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from src.core.exceptions import GaitAnalysisError


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content={"detail": exc.errors()})


async def gait_exception_handler(request: Request, exc: GaitAnalysisError):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


async def generic_exception_handler(request: Request, exc: Exception):
    return JSONResponse(status_code=500, content={"detail": "Internal server error.", "error": str(exc)})

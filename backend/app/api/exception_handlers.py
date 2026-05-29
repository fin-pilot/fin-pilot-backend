from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from backend.app.core.exceptions import (
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
)


def _json_error(status_code: int, message: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"detail": message})


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(NotFoundError)
    async def _not_found_handler(
        exc: NotFoundError,
    ) -> JSONResponse:
        return _json_error(404, exc.message)

    @app.exception_handler(ValidationError)
    async def _validation_handler(
        exc: ValidationError,
    ) -> JSONResponse:
        return _json_error(400, exc.message)

    @app.exception_handler(PermissionDeniedError)
    async def _permission_handler(
        exc: PermissionDeniedError,
    ) -> JSONResponse:
        return _json_error(403, exc.message)

    @app.exception_handler(ConflictError)
    async def _conflict_handler(
        exc: ConflictError,
    ) -> JSONResponse:
        return _json_error(409, exc.message)

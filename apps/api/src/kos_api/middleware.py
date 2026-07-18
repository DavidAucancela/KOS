"""Middleware transversal de la API: trace_id, errores RFC 9457 y CORS (doc 10 §2)."""

from __future__ import annotations

import time
import uuid
from collections.abc import Awaitable, Callable
from http import HTTPStatus

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from kos_core.observability import bind_trace_id, get_tracer, http_request_duration_seconds

_CORS_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]
_tracer = get_tracer("kos-api")


def install(app: FastAPI) -> None:
    """Registra middleware y manejadores globales de la aplicación."""

    app.add_middleware(
        CORSMiddleware,
        allow_origins=_CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def trace_id_middleware(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        trace_id = str(uuid.uuid4())
        request.state.trace_id = trace_id
        bind_trace_id(trace_id)
        started = time.perf_counter()
        with _tracer.start_as_current_span(f"{request.method} {request.url.path}") as span:
            span.set_attribute("kos.trace_id", trace_id)
            span.set_attribute("http.method", request.method)
            span.set_attribute("http.route", request.url.path)
            response = await call_next(request)
            span.set_attribute("http.status_code", response.status_code)
        response.headers["X-Trace-Id"] = trace_id

        # Plantilla de ruta (no la URL cruda) para no explotar la cardinalidad
        # de Prometheus con ids dinámicos (p. ej. /v1/documents/{doc_id}).
        route = request.scope.get("route")
        route_path = route.path if route is not None else request.url.path
        http_request_duration_seconds.labels(
            method=request.method, route=route_path, status=str(response.status_code)
        ).observe(time.perf_counter() - started)
        return response

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        """Errores esperados (4xx) en formato RFC 9457."""
        trace_id: str | None = getattr(request.state, "trace_id", None)
        headers = dict(exc.headers or {})
        if trace_id:
            headers["X-Trace-Id"] = trace_id
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "type": "about:blank",
                "title": HTTPStatus(exc.status_code).phrase,
                "status": exc.status_code,
                "detail": exc.detail,
                "trace_id": trace_id,
            },
            media_type="application/problem+json",
            headers=headers,
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """500 en formato RFC 9457 (application/problem+json), sin detalles internos."""
        trace_id: str | None = getattr(request.state, "trace_id", None)
        headers = {"X-Trace-Id": trace_id} if trace_id else None
        return JSONResponse(
            status_code=500,
            content={
                "type": "about:blank",
                "title": "Internal Server Error",
                "status": 500,
                "trace_id": trace_id,
            },
            media_type="application/problem+json",
            headers=headers,
        )

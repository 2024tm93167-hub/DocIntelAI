"""DocIntel AI FastAPI application entrypoint."""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routers import ai, analytics, documents, health, metrics, sharing, suggestions, users, versions, ws
from app.api.middleware import MetricsMiddleware
from app.config.settings import get_settings
from app.utils.exceptions import DocIntelError

settings = get_settings()

app = FastAPI(title=settings.app_name, version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_origin_regex=(
        r"http://(localhost|127\.0\.0\.1)(:\d+)?" if settings.environment == "development" else None
    ),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(DocIntelError)
async def docintel_error_handler(request: Request, exc: DocIntelError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})


app.include_router(health.router)
app.include_router(users.router)
app.include_router(documents.router)
app.include_router(versions.router)
app.include_router(suggestions.router)
app.include_router(sharing.router)
app.include_router(ai.router)
app.include_router(analytics.router)
app.include_router(ws.router)
app.include_router(metrics.router)

app.add_middleware(MetricsMiddleware)

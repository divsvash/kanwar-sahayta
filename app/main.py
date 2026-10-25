"""
Kanwar Sahayata FastAPI Application.

Main application factory with middleware, exception handlers,
and API router mounting. Entry point for Uvicorn.
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.config import settings
from app.api.v1.router import router as v1_router
from app.ui.routes import router as ui_router
from fastapi.responses import RedirectResponse
from app.core.exceptions import AppException


def create_app() -> FastAPI:
    """
    Application factory.

    Creates and configures the FastAPI application with:
    - CORS middleware for dashboard access
    - Global exception handlers
    - API router mounting
    - OpenAPI documentation
    """

    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="District administration platform for Kanwar Yatra operations",
        docs_url="/docs" if settings.DEBUG else "/docs",
        redoc_url="/redoc" if settings.DEBUG else None,
    )

    # ──────────────────────────────────────────
    # CORS Middleware
    # ──────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ──────────────────────────────────────────
    # Exception Handlers
    # ──────────────────────────────────────────

    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException):
        """Handle all application exceptions with structured responses."""
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": True,
                "error_code": exc.error_code,
                "message": exc.message,
                "details": exc.details,
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        """Catch-all for unhandled exceptions."""
        if settings.DEBUG:
            raise exc
        return JSONResponse(
            status_code=500,
            content={
                "error": True,
                "error_code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred. Please try again later.",
            },
        )

    # ──────────────────────────────────────────
    # Mount API Routers
    # ──────────────────────────────────────────
    app.include_router(v1_router)
    app.include_router(ui_router)

    @app.get('/', include_in_schema=False)
    async def root():
        return RedirectResponse(url='/ui/dashboard', status_code=303)

    # ──────────────────────────────────────────
    # Root Endpoint
    # ──────────────────────────────────────────

    @app.get("/")
    async def root():
        """Root endpoint with API information."""
        return {
            "service": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "environment": settings.ENVIRONMENT,
            "docs": "/docs",
            "health": "/api/v1/health",
        }

    return app


# Create application instance
app = create_app()


# ──────────────────────────────────────────
# Startup / Shutdown Events
# ──────────────────────────────────────────

@app.on_event("startup")
async def startup_event():
    """Log application startup."""
    import logging
    logger = logging.getLogger("kanwar_sahayata")
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    logger.info(f"Database: {settings.DATABASE_URL.split('@')[-1]}")


@app.on_event("shutdown")
async def shutdown_event():
    """Log application shutdown."""
    import logging
    logger = logging.getLogger("kanwar_sahayata")
    logger.info(f"Shutting down {settings.APP_NAME}")
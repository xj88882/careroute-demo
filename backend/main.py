"""CareRoute Backend — FastAPI Application Entry Point."""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from config import settings
from database import init_db
from routers import public, partner, admin


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database tables on startup."""
    await init_db()
    print(f"  {settings.APP_NAME} v{settings.APP_VERSION} started")
    print(f"  API docs: http://localhost:8000/docs")
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(public.router)
app.include_router(partner.router)
app.include_router(admin.router)


@app.get("/")
async def root():
    return {
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "endpoints": {
            "public": "/api/v2/public",
            "partner": "/api/v2/partner",
            "admin": "/api/v2/admin",
        },
    }


@app.get("/health")
async def health():
    return {"status": "healthy"}

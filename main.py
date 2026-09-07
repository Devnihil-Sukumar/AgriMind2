from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config.settings import settings
from app.utils.logger import logger

from app.api import (
    farmer_router,
    farm_router,
    crop_router,
    recommendation_router,
    weather_router,
)
from app.api.agrimind_api import router as agrimind_router

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="AgriMind - Dynamic Memory-Augmented Collaborative Multi-Agent Decision Intelligence Framework for Precision Agriculture",
)

# =====================================================
# CORS
#
# Permissive for local development so the dashboard can also be
# opened directly from disk or a separate dev server, not just
# from the /dashboard mount below.
# =====================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# =====================================================
# ROOT ENDPOINT
# =====================================================

@app.get("/")
def root():
    return {
        "project": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "status": "Running"
    }


# =====================================================
# REGISTER ROUTERS
# =====================================================

app.include_router(farmer_router)
app.include_router(farm_router)
app.include_router(crop_router)
app.include_router(recommendation_router)
app.include_router(weather_router)
app.include_router(agrimind_router)


# =====================================================
# DASHBOARD (static frontend)
# =====================================================

app.mount(
    "/dashboard",
    StaticFiles(directory="frontend", html=True),
    name="dashboard"
)


# =====================================================
# STARTUP EVENT
# =====================================================

@app.on_event("startup")
async def startup_event():
    logger.info("==========================================")
    logger.info(f"{settings.PROJECT_NAME} Started")
    logger.info(f"Version : {settings.VERSION}")
    logger.info("==========================================")


# =====================================================
# SHUTDOWN EVENT
# =====================================================

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("AgriMind stopped.")
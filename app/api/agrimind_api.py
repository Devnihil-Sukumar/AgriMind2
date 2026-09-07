"""
==========================================================================
AgriMind

Multi-Agent Recommendation API

Exposes the Module 5 dynamic multi-agent pipeline
(app.orchestrator.dynamic_orchestrator) over HTTP for the frontend
dashboard.

Author : AgriMind Team
==========================================================================
"""

import logging

from fastapi import APIRouter, HTTPException
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from app.config import ai_settings
from app.orchestrator.dynamic_orchestrator import dynamic_orchestrator

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api",
    tags=["AgriMind Pipeline"]
)


##########################################################################
# Request / Response Models
##########################################################################

class RecommendationRequest(BaseModel):

    query: str = Field(
        ...,
        min_length=3,
        description="Natural language farming question, "
                    "e.g. 'What should I do to maximize cotton yield?'"
    )

    crop: str = Field(
        "rice",
        description="Crop name. Defaults to 'rice' when not provided."
    )

    latitude: float | None = Field(
        None,
        ge=-90,
        le=90,
        description="Farm latitude. Falls back to the server "
                    "default when omitted."
    )

    longitude: float | None = Field(
        None,
        ge=-180,
        le=180,
        description="Farm longitude. Falls back to the server "
                    "default when omitted."
    )


##########################################################################
# Defaults
##########################################################################

@router.get("/defaults")
def get_defaults():

    return {
        "latitude": ai_settings.DEFAULT_LATITUDE,
        "longitude": ai_settings.DEFAULT_LONGITUDE,
        "crop": "rice"
    }


##########################################################################
# Health
##########################################################################

@router.get("/health")
def health():

    return {
        "status": "ok"
    }


##########################################################################
# Recommend
##########################################################################

@router.post("/recommend")
async def recommend(payload: RecommendationRequest):

    latitude = (

        payload.latitude

        if payload.latitude is not None

        else ai_settings.DEFAULT_LATITUDE

    )

    longitude = (

        payload.longitude

        if payload.longitude is not None

        else ai_settings.DEFAULT_LONGITUDE

    )

    crop = (payload.crop or "rice").strip().lower()

    logger.info(

        "Recommendation request: crop=%s lat=%s lon=%s query=%r",
        crop,
        latitude,
        longitude,
        payload.query

    )

    try:

        result = await run_in_threadpool(

            dynamic_orchestrator.run,

            user_query=payload.query,

            crop=crop,

            latitude=latitude,

            longitude=longitude

        )

    except Exception as e:

        logger.exception(e)

        raise HTTPException(

            status_code=500,

            detail=f"Pipeline execution failed: {e}"

        )

    return result

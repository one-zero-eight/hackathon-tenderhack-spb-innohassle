from fastapi import APIRouter
from fastapi_derive_responses import AutoDeriveResponsesAPIRoute

router = APIRouter(prefix="/health", tags=["Health"], route_class=AutoDeriveResponsesAPIRoute)


@router.get("/ping")
async def ping():
    return {"ping": "pong"}

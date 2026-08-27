from fastapi import APIRouter
from models.schemas import EntitlementResponse
from services.licensing import development_entitlements

router = APIRouter()


@router.get("/development", response_model=EntitlementResponse)
async def development() -> EntitlementResponse:
    return development_entitlements()

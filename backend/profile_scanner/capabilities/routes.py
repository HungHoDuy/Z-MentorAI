from fastapi import APIRouter

from capabilities.registry import CAPABILITIES


router = APIRouter(tags=["capabilities"])


@router.get("/capabilities")
async def list_capabilities():
    return {"status": "success", "feature": "capabilities", "capabilities": CAPABILITIES}

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from backend.api.dependencies.auth import CurrentUser, get_current_user
from backend.services.llm_service import (
    get_active_provider, set_active_provider, get_available_providers,
    PROVIDER_LABELS, PROVIDER_MODELS, LLMProvider,
)

router = APIRouter(prefix="/settings", tags=["settings"])

VALID_PROVIDERS: list[LLMProvider] = ["gemini", "groq", "openai"]


class SetProviderRequest(BaseModel):
    provider: str


@router.get("/llm")
async def get_llm_settings(current_user: CurrentUser = Depends(get_current_user)):
    active = get_active_provider()
    available = get_available_providers()
    return {
        "active_provider": active,
        "available_providers": [
            {"id": p, "label": PROVIDER_LABELS[p], "model": PROVIDER_MODELS[p], "available": True}
            for p in available
        ],
        "all_providers": [
            {"id": p, "label": PROVIDER_LABELS[p], "model": PROVIDER_MODELS[p], "available": p in available}
            for p in VALID_PROVIDERS
        ],
    }


@router.post("/llm")
async def set_llm_provider(
    body: SetProviderRequest,
    current_user: CurrentUser = Depends(get_current_user),
):
    provider = body.provider
    if provider not in VALID_PROVIDERS:
        raise HTTPException(status_code=400, detail="Invalid provider. Must be gemini, groq, or openai.")
    available = get_available_providers()
    if provider not in available:
        raise HTTPException(status_code=400, detail=f"Provider '{provider}' has no API key configured.")
    set_active_provider(provider)  # type: ignore
    return {"success": True, "active_provider": provider, "label": PROVIDER_LABELS[provider]}  # type: ignore

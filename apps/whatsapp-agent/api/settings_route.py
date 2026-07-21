from fastapi import APIRouter

from schemas import SettingsStatus
from settings import get_settings

router = APIRouter(tags=["settings"])


@router.get("/api/settings/status", response_model=SettingsStatus)
async def settings_status():
    settings = get_settings()
    return SettingsStatus(
        app_env=settings.app_env,
        agent_mode=settings.agent_mode,
        llm_provider=settings.llm_provider,
        llm_live_ready=settings.live_llm_ready,
        whatsapp_mode=settings.whatsapp_mode,
        whatsapp_live_ready=settings.live_whatsapp_ready,
        database_kind="sqlite" if "sqlite" in settings.database_url else "postgresql",
        agent_min_typing_delay_ms=settings.agent_min_typing_delay_ms,
        agent_max_typing_delay_ms=settings.agent_max_typing_delay_ms,
    )

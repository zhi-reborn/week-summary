from fastapi import APIRouter, Request

from app.api.errors import ApiError
from app.application.settings_service import SettingsService
from app.domain.model_settings import ModelCapabilities, ModelSettingsUpdate, ModelSettingsView
from app.infrastructure.llm.client import LLMConnectionError, OpenAICompatibleClient

router = APIRouter(prefix="/api/settings/model", tags=["settings"])


def _service(request: Request) -> SettingsService:
    return SettingsService(request.app.state.settings.data_dir)


@router.get("", response_model=ModelSettingsView)
def get_model_settings(request: Request) -> ModelSettingsView:
    try:
        return _service(request).get()
    except FileNotFoundError as exc:
        raise ApiError(404, "MODEL_SETTINGS_NOT_CONFIGURED", "尚未配置私有模型") from exc


@router.put("", response_model=ModelSettingsView)
def save_model_settings(payload: ModelSettingsUpdate, request: Request) -> ModelSettingsView:
    return _service(request).save(payload)


@router.post("/test", response_model=ModelCapabilities)
def test_model_connection(request: Request) -> ModelCapabilities:
    try:
        settings, api_key = _service(request).load_client_values()
    except FileNotFoundError as exc:
        raise ApiError(404, "MODEL_SETTINGS_NOT_CONFIGURED", "尚未配置私有模型") from exc
    client = OpenAICompatibleClient(
        base_url=str(settings.base_url),
        model=settings.model,
        api_key=api_key,
        timeout_seconds=settings.timeout_seconds,
    )
    try:
        capabilities = client.test_connection()
        request.app.state.model_connectivity = {
            "status": "reachable",
            "json_mode": capabilities.json_mode,
        }
        return capabilities
    except LLMConnectionError as exc:
        request.app.state.model_connectivity = {"status": "failed", "error_code": exc.code}
        status = 504 if exc.code == "MODEL_TIMEOUT" else 502
        raise ApiError(status, exc.code, str(exc)) from exc

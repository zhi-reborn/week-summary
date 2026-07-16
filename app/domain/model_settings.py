from pydantic import AnyHttpUrl, BaseModel, Field


class ModelSettings(BaseModel):
    base_url: AnyHttpUrl
    model: str = Field(min_length=1, max_length=200)
    timeout_seconds: int = Field(default=120, ge=5, le=900)
    max_retries: int = Field(default=2, ge=0, le=5)
    temperature: float = Field(default=0.1, ge=0, le=1)
    context_tokens: int | None = Field(default=None, ge=2048)


class ModelSettingsUpdate(ModelSettings):
    api_key: str | None = Field(default=None, max_length=4096)


class ModelSettingsView(ModelSettings):
    has_api_key: bool


class ModelCapabilities(BaseModel):
    reachable: bool
    model_callable: bool
    json_mode: bool
    message: str

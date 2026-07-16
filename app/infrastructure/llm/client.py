import json
from typing import Any

import httpx

from app.domain.model_settings import ModelCapabilities


class LLMConnectionError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


class OpenAICompatibleClient:
    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        api_key: str | None,
        timeout_seconds: int = 120,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._url = f"{base_url.rstrip('/')}/chat/completions"
        self._model = model
        self._api_key = api_key
        self._timeout = timeout_seconds
        self._transport = transport

    def test_connection(self) -> ModelCapabilities:
        payload = self._capability_payload()
        payload["response_format"] = {"type": "json_object"}
        response = self._send(payload)
        json_mode = True
        if response.status_code == 400 and "response_format" in response.text.lower():
            payload.pop("response_format")
            response = self._send(payload)
            json_mode = False
        self._raise_for_status(response)
        self._parse_message_json(response)
        message = "连接成功" if json_mode else "连接成功，但模型不支持结构化 JSON 模式"
        return ModelCapabilities(
            reachable=True,
            model_callable=True,
            json_mode=json_mode,
            message=message,
        )

    def _send(self, payload: dict[str, Any]) -> httpx.Response:
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        try:
            with httpx.Client(transport=self._transport, timeout=self._timeout) as client:
                return client.post(self._url, headers=headers, json=payload)
        except httpx.TimeoutException as exc:
            raise LLMConnectionError("MODEL_TIMEOUT", "模型连接超时") from exc
        except httpx.RequestError as exc:
            raise LLMConnectionError("MODEL_UNREACHABLE", "无法连接模型服务") from exc

    def _capability_payload(self) -> dict[str, Any]:
        return {
            "model": self._model,
            "temperature": 0,
            "max_tokens": 32,
            "messages": [
                {"role": "system", "content": "Return one JSON object only."},
                {"role": "user", "content": 'Return {"ok": true}.'},
            ],
        }

    @staticmethod
    def _raise_for_status(response: httpx.Response) -> None:
        if response.status_code < 400:
            return
        if response.status_code in {401, 403}:
            raise LLMConnectionError("AUTH_FAILED", "模型认证失败")
        if response.status_code == 404:
            raise LLMConnectionError("MODEL_NOT_FOUND", "模型或接口不存在")
        raise LLMConnectionError("MODEL_REQUEST_REJECTED", "模型拒绝了能力测试请求")

    @staticmethod
    def _parse_message_json(response: httpx.Response) -> dict[str, Any]:
        try:
            payload = response.json()
            content = payload["choices"][0]["message"]["content"]
            parsed = json.loads(content)
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise LLMConnectionError("INVALID_MODEL_RESPONSE", "模型响应不是有效 JSON") from exc
        if not isinstance(parsed, dict):
            raise LLMConnectionError("INVALID_MODEL_RESPONSE", "模型响应必须是 JSON 对象")
        return parsed

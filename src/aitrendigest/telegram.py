from __future__ import annotations

from typing import Any
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class TelegramPublisher:
    def __init__(self, client: Any | None, bot_token: str, chat_id: str):
        self._client = client
        self._bot_token = bot_token
        self._chat_id = chat_id

    def _send_via_urllib(self, url: str, payload: dict[str, str]) -> bool:
        request = Request(
            url,
            data=urlencode(payload).encode("utf-8"),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        try:
            with urlopen(request, timeout=20.0) as response:
                return 200 <= getattr(response, "status", 200) < 300
        except URLError:
            return False

    def get_updates(self, offset: int | None = None) -> list[dict[str, Any]]:
        url = f"https://api.telegram.org/bot{self._bot_token}/getUpdates"
        params: dict[str, Any] = {"timeout": 5}
        if offset is not None:
            params["offset"] = offset
        if self._client is None:
            raise RuntimeError("telegram update polling requires an HTTP client")
        response = self._client.get(url, params=params, timeout=10.0)
        if not response.is_success:
            raise RuntimeError(f"telegram getUpdates failed: {response.status_code}")
        payload = response.json()
        if not payload.get("ok", False):
            raise RuntimeError("telegram getUpdates returned an error payload")
        result = payload.get("result")
        if not isinstance(result, list):
            raise RuntimeError("telegram getUpdates returned no result list")
        return result

    def send_message(self, message: str) -> None:
        url = f"https://api.telegram.org/bot{self._bot_token}/sendMessage"
        payload = {"chat_id": self._chat_id, "text": message}
        last_error: Exception | None = None
        for _ in range(2):
            try:
                if self._client is not None:
                    response = self._client.post(url, json=payload, timeout=20.0)
                    if response.is_success:
                        return
                    last_error = RuntimeError(f"telegram send failed: {response.status_code}")
                else:
                    if self._send_via_urllib(url, payload):
                        return
                    last_error = RuntimeError("telegram send failed")
            except Exception as exc:  # pragma: no cover - network/runtime fallback path
                last_error = exc
        raise last_error if last_error else RuntimeError("telegram send failed")

from aitrendigest.telegram import TelegramPublisher


class DummyResponse:
    def __init__(self, payload):
        self._payload = payload
        self.status_code = 200
        self.is_success = True

    def json(self):
        return self._payload


class DummyClient:
    def __init__(self):
        self.calls = []

    def get(self, url, params, timeout):
        self.calls.append({"url": url, "params": params, "timeout": timeout})
        return DummyResponse(
            {
                "ok": True,
                "result": [
                    {
                        "update_id": 100,
                        "message": {
                            "chat": {"id": 555},
                            "text": "/period 3",
                        },
                    }
                ],
            }
        )


def test_telegram_publisher_fetches_updates():
    client = DummyClient()
    publisher = TelegramPublisher(client, "token", "bootstrap")

    updates = publisher.get_updates(offset=99)

    assert updates[0]["update_id"] == 100
    assert updates[0]["message"]["text"] == "/period 3"
    assert client.calls[0]["url"].endswith("/getUpdates")
    assert client.calls[0]["params"] == {"timeout": 5, "offset": 99}
    assert client.calls[0]["timeout"] == 10.0

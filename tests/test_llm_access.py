"""Access probes send one minimal request and never expose credentials."""

import requests

from scout import sources
from scout.config import load_settings


def test_minimal_probe_sends_one_request_and_extracts_error(monkeypatch):
    calls = []
    key = "test-sensitive-credential"

    class Response:
        status_code = 402
        headers = {"X-ZenMux-RequestId": "request-123"}

        def json(self):
            return {"error": {"type": "reject_no_credit", "message": "Denied " + key}}

    def post(url, **kwargs):
        calls.append(kwargs)
        return Response()

    monkeypatch.setattr(sources._session, "post", post)
    result = sources.probe_llm_access(load_settings(), key)
    assert len(calls) == 1
    assert set(calls[0]["json"]) == {"model", "messages"}
    assert len(calls[0]["json"]["messages"]) == 1
    assert not calls[0]["allow_redirects"]
    assert result["http_status"] == 402 and result["error_type"] == "reject_no_credit"
    assert result["request_id"] == "request-123" and key not in result["error_message"]


def test_probe_never_retries_transport_failure(monkeypatch):
    calls = []

    def post(*args, **kwargs):
        calls.append(1)
        raise requests.ConnectionError("offline")

    monkeypatch.setattr(sources._session, "post", post)
    result = sources.probe_llm_access(load_settings(), "test-key")
    assert len(calls) == 1 and result["status"] == "failed"
    assert result["http_status"] is None

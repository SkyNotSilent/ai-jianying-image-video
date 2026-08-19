from types import SimpleNamespace

import pytest
import requests

from src.api.error_model import ClassifiedError
from src.config import Config
from src.media import image_generator
from src.media.image_generator import ImageGenerator


def test_image_retry_delay_uses_configured_interval_for_regular_failures():
    generator = object.__new__(ImageGenerator)
    generator.retry_interval_seconds = 7

    assert generator._retry_delay(None, attempt=0) == 7
    assert generator._retry_delay(None, attempt=1) == 14


def test_image_retry_delay_prefers_provider_retry_after_for_rate_limits():
    generator = object.__new__(ImageGenerator)
    generator.retry_interval_seconds = 7
    response = SimpleNamespace(status_code=429, headers={"retry-after": "11"})

    assert generator._retry_delay(response, attempt=2) == 11


def test_image_rate_limiter_allows_measured_eight_request_burst(monkeypatch):
    image_generator._IMAGE_REQUEST_TIMESTAMPS.clear()
    monkeypatch.setattr(image_generator.time, "monotonic", lambda: 100.0)
    sleeps = []
    monkeypatch.setattr(image_generator.time, "sleep", sleeps.append)
    generator = object.__new__(ImageGenerator)

    for _ in range(8):
        generator._wait_for_rate_limit()

    assert len(image_generator._IMAGE_REQUEST_TIMESTAMPS) == 8
    assert sleeps == []


def test_image_rate_limiter_waits_after_twenty_requests_in_rolling_minute(monkeypatch):
    image_generator._IMAGE_REQUEST_TIMESTAMPS.clear()
    image_generator._IMAGE_REQUEST_TIMESTAMPS.extend([100.0] * 20)
    now = [100.0]
    sleeps = []

    monkeypatch.setattr(image_generator.time, "monotonic", lambda: now[0])

    def advance(seconds):
        sleeps.append(seconds)
        now[0] += seconds

    monkeypatch.setattr(image_generator.time, "sleep", advance)
    generator = object.__new__(ImageGenerator)

    generator._wait_for_rate_limit()

    assert sleeps == [60.0]
    assert list(image_generator._IMAGE_REQUEST_TIMESTAMPS) == [160.0]


def test_image_401_is_wrapped_as_safe_auth_error(tmp_path, monkeypatch):
    secret = "sk-image-provider-secret"

    class UnauthorizedResponse:
        status_code = 401
        headers = {"x-request-id": "req-image-auth"}

        def raise_for_status(self):
            raise requests.HTTPError(
                f"Authorization: Bearer {secret}", response=self
            )

    monkeypatch.setattr(
        Config,
        "image_config",
        classmethod(lambda cls: {
            "api_url": "https://image.invalid/v1/images/generations",
            "api_key": secret,
            "model": "fake-image",
        }),
    )
    monkeypatch.setattr(
        Config,
        "generation_config",
        classmethod(lambda cls: {"retry_count": 0, "retry_interval_seconds": 1}),
    )
    monkeypatch.setattr(image_generator.requests, "post", lambda *_args, **_kwargs: UnauthorizedResponse())
    monkeypatch.setattr(ImageGenerator, "_wait_for_rate_limit", lambda self: None)
    generator = ImageGenerator(str(tmp_path))

    with pytest.raises(ClassifiedError) as exc_info:
        generator.generate("safe prompt")

    safe = exc_info.value.safe_error
    assert safe.code.value == "auth"
    assert safe.request_id == "req-image-auth"
    assert secret not in str(exc_info.value)

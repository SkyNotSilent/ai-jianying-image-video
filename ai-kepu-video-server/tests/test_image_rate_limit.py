from src.media import image_generator
from src.media.image_generator import ImageGenerator


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

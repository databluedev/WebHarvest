"""Tests for network capture module."""
import pytest
from app.services.network_capture import (
    NetworkRequest,
    NetworkResponse,
    ConsoleMessage,
    NetworkCapture,
    NetworkCaptureHandler,
)


class TestNetworkCapture:
    def test_capture_creation(self):
        capture = NetworkCapture()
        assert capture.requests == []
        assert capture.responses == []
        assert capture.console_messages == []

    def test_get_api_responses(self):
        capture = NetworkCapture(
            responses=[
                NetworkResponse(
                    url="https://api.example.com/data",
                    status=200,
                    headers={"content-type": "application/json"},
                    resource_type="xhr",
                ),
                NetworkResponse(
                    url="https://example.com/style.css",
                    status=200,
                    headers={"content-type": "text/css"},
                    resource_type="stylesheet",
                ),
                NetworkResponse(
                    url="https://api.example.com/users",
                    status=200,
                    headers={"content-type": "application/json; charset=utf-8"},
                    resource_type="fetch",
                ),
            ]
        )
        api = capture.get_api_responses()
        assert len(api) == 2
        assert api[0].url == "https://api.example.com/data"
        assert api[1].url == "https://api.example.com/users"

    def test_get_api_responses_with_pattern(self):
        capture = NetworkCapture(
            responses=[
                NetworkResponse(
                    url="https://api.example.com/products",
                    status=200,
                    headers={"content-type": "application/json"},
                    resource_type="xhr",
                ),
                NetworkResponse(
                    url="https://api.example.com/users",
                    status=200,
                    headers={"content-type": "application/json"},
                    resource_type="xhr",
                ),
            ]
        )
        filtered = capture.get_api_responses(pattern="products")
        assert len(filtered) == 1
        assert "products" in filtered[0].url

    def test_get_errors(self):
        capture = NetworkCapture(
            console_messages=[
                ConsoleMessage(type="log", text="Info message"),
                ConsoleMessage(type="error", text="Something broke"),
                ConsoleMessage(type="warning", text="Deprecation notice"),
                ConsoleMessage(type="error", text="Another error"),
            ]
        )
        errors = capture.get_errors()
        assert len(errors) == 2
        assert errors[0].text == "Something broke"

    def test_to_dict(self):
        capture = NetworkCapture(
            requests=[
                NetworkRequest(url="https://example.com", method="GET", resource_type="document"),
            ],
            responses=[
                NetworkResponse(
                    url="https://api.example.com/data",
                    status=200,
                    headers={"content-type": "application/json"},
                    resource_type="xhr",
                ),
            ],
            console_messages=[
                ConsoleMessage(type="log", text="Hello"),
            ],
        )
        d = capture.to_dict()
        assert d["requests_count"] == 1
        assert d["responses_count"] == 1
        assert len(d["console_messages"]) == 1
        assert len(d["api_responses"]) == 1


class TestNetworkCaptureHandler:
    def test_handler_creation(self):
        handler = NetworkCaptureHandler()
        capture = handler.get_capture()
        assert isinstance(capture, NetworkCapture)

    def test_handler_with_body_capture(self):
        handler = NetworkCaptureHandler(capture_bodies=True, max_body_size=500_000)
        assert handler._capture_bodies is True
        assert handler._max_body_size == 500_000

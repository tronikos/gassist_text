"""Tests for TextAssistant."""

import google.oauth2.credentials
import grpc
import pytest

from gassist_text import TextAssistant


def test_textinput():
    """Test assist call raises if no credentials."""
    credentials = google.oauth2.credentials.Credentials(token=None)
    with TextAssistant(credentials) as assistant, pytest.raises(
        grpc._channel._MultiThreadedRendezvous
    ):
        assistant.assist("tell me a joke")

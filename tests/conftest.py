"""Shared fixtures for the tests."""

from typing import Any

import google.auth.transport.grpc
import google.oauth2.credentials
import grpc
import grpc.aio
import pytest


@pytest.fixture
def credentials() -> google.oauth2.credentials.Credentials:
    """Return credentials that are never actually used to authenticate."""
    return google.oauth2.credentials.Credentials(  # type: ignore[no-untyped-call]
        token="fake-token"
    )


@pytest.fixture
def insecure_channels(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make the clients talk to the fake service over an insecure channel.

    The clients always build an authorized TLS channel, which the fake service
    does not speak, so channel creation is redirected here. Everything else,
    including the streaming, is exercised for real.
    """

    def authorized_channel(
        credentials: object, request: object, target: str, **kwargs: Any
    ) -> grpc.Channel:
        return grpc.insecure_channel(target, **kwargs)

    def aio_secure_channel(
        target: str, credentials: object, *args: Any, **kwargs: Any
    ) -> grpc.aio.Channel:
        return grpc.aio.insecure_channel(target, *args, **kwargs)

    monkeypatch.setattr(
        google.auth.transport.grpc, "secure_authorized_channel", authorized_channel
    )
    monkeypatch.setattr(grpc.aio, "secure_channel", aio_secure_channel)

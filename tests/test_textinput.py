"""Tests for TextAssistant and TextAssistantAsync.

Both clients are exercised against a real gRPC service, so the streaming, the
conversation state carried between turns and the responses are all covered for
real. Only the TLS/authorization layer is swapped out, by the insecure_channels
fixture.
"""

import asyncio
from collections.abc import Coroutine
from typing import Any, TypeVar

import google.oauth2.credentials
import grpc
import pytest

from gassist_text import TextAssistant, TextAssistantAsync
from google.assistant.embedded.v1alpha2 import embedded_assistant_pb2

from .fake_assistant import FakeAssistant, serve, serve_async

PLAYING = embedded_assistant_pb2.ScreenOutConfig.PLAYING
SCREEN_MODE_UNSPECIFIED = embedded_assistant_pb2.ScreenOutConfig.SCREEN_MODE_UNSPECIFIED

_T = TypeVar("_T")

pytestmark = pytest.mark.usefixtures("insecure_channels")


def run(coro: Coroutine[Any, Any, _T]) -> _T:
    """Run a coroutine to completion, so async tests need no extra plugin."""
    return asyncio.run(coro)


def test_assist_returns_text_html_and_audio(
    credentials: google.oauth2.credentials.Credentials,
) -> None:
    """Test the three parts of a response are returned, with the audio joined."""
    fake = FakeAssistant(
        text="a joke", html=b"<html>a joke</html>", audio_chunks=[b"one", b"two"]
    )
    server, address = serve(fake)
    try:
        with TextAssistant(
            credentials, audio_out=True, api_endpoint=address
        ) as assistant:
            assert assistant.assist("tell me a joke") == (
                "a joke",
                b"<html>a joke</html>",
                b"onetwo",
            )
    finally:
        server.stop(None)


def test_assist_async_returns_text_html_and_audio(
    credentials: google.oauth2.credentials.Credentials,
) -> None:
    """Test the async client returns the same response as the sync one."""
    fake = FakeAssistant(
        text="a joke", html=b"<html>a joke</html>", audio_chunks=[b"one", b"two"]
    )

    async def scenario() -> tuple[str, bytes | None, bytes]:
        server, address = await serve_async(fake)
        try:
            async with TextAssistantAsync(
                credentials, audio_out=True, api_endpoint=address
            ) as assistant:
                return await assistant.assist("tell me a joke")
        finally:
            await server.stop(None)

    assert run(scenario()) == ("a joke", b"<html>a joke</html>", b"onetwo")


def test_audio_is_dropped_unless_requested(
    credentials: google.oauth2.credentials.Credentials,
) -> None:
    """Test audio is discarded when audio_out is off, even if the service sends it."""
    fake = FakeAssistant(text="a joke", audio_chunks=[b"one", b"two"])
    server, address = serve(fake)
    try:
        with TextAssistant(credentials, api_endpoint=address) as assistant:
            assert assistant.assist("tell me a joke") == ("a joke", None, b"")
    finally:
        server.stop(None)


def test_html_is_none_when_not_sent(
    credentials: google.oauth2.credentials.Credentials,
) -> None:
    """Test the html part is None, not empty bytes, when the service sends none."""
    fake = FakeAssistant(text="a joke")
    server, address = serve(fake)
    try:
        with TextAssistant(credentials, api_endpoint=address) as assistant:
            assert assistant.assist("tell me a joke")[1] is None
    finally:
        server.stop(None)


def test_request_carries_the_configuration(
    credentials: google.oauth2.credentials.Credentials,
) -> None:
    """Test the constructor arguments reach the service in the request."""
    fake = FakeAssistant(text="a joke")
    server, address = serve(fake)
    try:
        with TextAssistant(
            credentials,
            language_code="de-DE",
            device_model_id="model-id",
            device_id="device-id",
            display=True,
            api_endpoint=address,
        ) as assistant:
            assistant.assist("erzähl mir einen Witz")
    finally:
        server.stop(None)

    assert len(fake.requests) == 1
    config = fake.requests[0].config
    assert config.text_query == "erzähl mir einen Witz"
    assert config.dialog_state_in.language_code == "de-DE"
    assert config.device_config.device_model_id == "model-id"
    assert config.device_config.device_id == "device-id"
    assert config.screen_out_config.screen_mode == PLAYING
    assert config.audio_out_config.encoding == embedded_assistant_pb2.AudioOutConfig.MP3
    assert config.audio_out_config.sample_rate_hertz == 24000


def test_screen_mode_is_unset_without_display(
    credentials: google.oauth2.credentials.Credentials,
) -> None:
    """Test the screen mode is left alone when display is off."""
    fake = FakeAssistant(text="a joke")
    server, address = serve(fake)
    try:
        with TextAssistant(credentials, api_endpoint=address) as assistant:
            assistant.assist("tell me a joke")
    finally:
        server.stop(None)

    assert (
        fake.requests[0].config.screen_out_config.screen_mode == SCREEN_MODE_UNSPECIFIED
    )


def test_conversation_state_is_carried_between_turns(
    credentials: google.oauth2.credentials.Credentials,
) -> None:
    """Test a follow up continues the conversation the first query started."""
    fake = FakeAssistant(text="a joke", conversation_state=b"state-from-service")
    server, address = serve(fake)
    try:
        with TextAssistant(credentials, api_endpoint=address) as assistant:
            assistant.assist("tell me a joke")
            assistant.assist("another one")
    finally:
        server.stop(None)

    first, second = (request.config.dialog_state_in for request in fake.requests)
    assert first.is_new_conversation is True
    assert first.conversation_state == b""
    assert second.is_new_conversation is False
    assert second.conversation_state == b"state-from-service"


def test_conversation_state_is_carried_between_turns_async(
    credentials: google.oauth2.credentials.Credentials,
) -> None:
    """Test the async client also continues the conversation across turns."""
    fake = FakeAssistant(text="a joke", conversation_state=b"state-from-service")

    async def scenario() -> None:
        server, address = await serve_async(fake)
        try:
            async with TextAssistantAsync(credentials, api_endpoint=address) as a:
                await a.assist("tell me a joke")
                await a.assist("another one")
        finally:
            await server.stop(None)

    run(scenario())

    first, second = (request.config.dialog_state_in for request in fake.requests)
    assert first.is_new_conversation is True
    assert first.conversation_state == b""
    assert second.is_new_conversation is False
    assert second.conversation_state == b"state-from-service"


def test_service_error_is_raised(
    credentials: google.oauth2.credentials.Credentials,
) -> None:
    """Test a failure from the service reaches the caller."""
    fake = FakeAssistant(abort_with=grpc.StatusCode.PERMISSION_DENIED)
    server, address = serve(fake)
    try:
        with (
            TextAssistant(credentials, api_endpoint=address) as assistant,
            pytest.raises(grpc.RpcError) as exc,
        ):
            assistant.assist("tell me a joke")
    finally:
        server.stop(None)
    assert exc.value.code() == grpc.StatusCode.PERMISSION_DENIED


def test_service_error_is_raised_async(
    credentials: google.oauth2.credentials.Credentials,
) -> None:
    """Test a failure from the service reaches the caller of the async client."""
    fake = FakeAssistant(abort_with=grpc.StatusCode.PERMISSION_DENIED)

    async def scenario() -> grpc.StatusCode:
        server, address = await serve_async(fake)
        try:
            async with TextAssistantAsync(credentials, api_endpoint=address) as a:
                with pytest.raises(grpc.RpcError) as exc:
                    await a.assist("tell me a joke")
            return exc.value.code()
        finally:
            await server.stop(None)

    assert run(scenario()) == grpc.StatusCode.PERMISSION_DENIED


def test_channel_is_closed_on_exit(
    credentials: google.oauth2.credentials.Credentials,
) -> None:
    """Test leaving the context manager closes the channel instead of leaking it."""
    fake = FakeAssistant(text="a joke")
    server, address = serve(fake)
    try:
        with TextAssistant(credentials, api_endpoint=address) as assistant:
            assistant.assist("tell me a joke")
        with pytest.raises(ValueError, match="Channel closed"):
            assistant.assist("another one")
    finally:
        server.stop(None)


def test_channel_is_closed_on_exit_async(
    credentials: google.oauth2.credentials.Credentials,
) -> None:
    """Test leaving the async context manager closes the channel."""
    fake = FakeAssistant(text="a joke")

    async def scenario() -> None:
        server, address = await serve_async(fake)
        try:
            assistant = TextAssistantAsync(credentials, api_endpoint=address)
            async with assistant:
                await assistant.assist("tell me a joke")
            assert assistant._channel is None
        finally:
            await server.stop(None)

    run(scenario())


def test_close_async_is_safe_before_and_after_use(
    credentials: google.oauth2.credentials.Credentials,
) -> None:
    """Test closing the async client is safe when unused, and is idempotent."""

    async def scenario() -> None:
        assistant = TextAssistantAsync(credentials, api_endpoint="localhost:1")
        await assistant.close()
        await assistant.close()

    run(scenario())


def test_async_channel_binds_to_the_running_loop(
    credentials: google.oauth2.credentials.Credentials,
) -> None:
    """Test the client can be built outside of the loop that later uses it.

    A grpc.aio channel is tied to the loop that was running when it was created,
    so building it eagerly in the constructor would break this.
    """
    fake = FakeAssistant(text="a joke")
    assistant = TextAssistantAsync(credentials, api_endpoint="unused")

    async def scenario() -> tuple[str, bytes | None, bytes]:
        server, address = await serve_async(fake)
        assistant._api_endpoint = address
        try:
            async with assistant:
                return await assistant.assist("tell me a joke")
        finally:
            await server.stop(None)

    assert run(scenario())[0] == "a joke"


def test_concurrent_assists_share_one_channel(
    credentials: google.oauth2.credentials.Credentials,
) -> None:
    """Test racing first calls open a single channel rather than leaking one."""
    fake = FakeAssistant(text="a joke")

    async def scenario() -> None:
        server, address = await serve_async(fake)
        assistant = TextAssistantAsync(credentials, api_endpoint=address)
        try:
            async with assistant:
                await asyncio.gather(
                    assistant.assist("one"),
                    assistant.assist("two"),
                    assistant.assist("three"),
                )
                channel = assistant._channel
                await assistant.assist("four")
                assert assistant._channel is channel
        finally:
            await server.stop(None)

    run(scenario())
    assert len(fake.requests) == 4

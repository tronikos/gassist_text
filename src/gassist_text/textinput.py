# Copyright (C) 2017 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Implements a text client for the Google Assistant Service."""

# Copied from:
# https://github.com/googlesamples/assistant-sdk-python/blob/master/google-assistant-sdk/googlesamples/assistant/grpc/textinput.py
# Changes:
# - Renamed class
# - Simplified constructor:
#   - Added default values
#   - Moved creation of the authorized gRPC channel in the constructor
# - Return audio response as mp3
# - Extracted command line tool to demo.py
# - Added strict typing with mypy
# - Close the gRPC channel when the assistant is closed
# - Added TextAssistantAsync, an asyncio variant built on grpc.aio

import asyncio
from collections.abc import Iterator
from dataclasses import dataclass, field
from types import TracebackType

import google.auth.transport.grpc
import google.auth.transport.requests
import google.oauth2.credentials
import grpc
import grpc.aio

from google.assistant.embedded.v1alpha2 import (
    embedded_assistant_pb2,
    embedded_assistant_pb2_grpc,
)

from . import assistant_helpers

ASSISTANT_API_ENDPOINT = "embeddedassistant.googleapis.com"
DEFAULT_GRPC_DEADLINE = 60 * 3 + 5
PLAYING = embedded_assistant_pb2.ScreenOutConfig.PLAYING


@dataclass
class _AssistResult:
    """Accumulates the parts of an assist response as they stream in."""

    text: str = ""
    html: bytes | None = None
    audio_chunks: list[bytes] = field(default_factory=list)

    def as_tuple(self) -> tuple[str, bytes | None, bytes]:
        """Return the response as a tuple of: [text, html, audio]."""
        return self.text, self.html, b"".join(self.audio_chunks)


class _TextAssistantBase:
    """Shared configuration and message handling for the text assistants."""

    def __init__(
        self,
        language_code: str,
        device_model_id: str,
        device_id: str,
        display: bool,
        audio_out: bool,
        deadline_sec: int,
    ) -> None:
        self.language_code = language_code
        self.device_model_id = device_model_id
        self.device_id = device_id
        self.conversation_state: bytes | None = None
        # Force reset of first conversation.
        self.is_new_conversation = True
        self.display = display
        self.audio_out = audio_out
        self.deadline = deadline_sec

    def _create_requests(
        self, text_query: str
    ) -> Iterator[embedded_assistant_pb2.AssistRequest]:
        """Build the requests to stream to the Assistant for a text query.

        The synchronous gRPC API calls next() on what it is given, so this must
        be an iterator and not merely an iterable.
        """
        config = embedded_assistant_pb2.AssistConfig(
            audio_out_config=embedded_assistant_pb2.AudioOutConfig(
                encoding=embedded_assistant_pb2.AudioOutConfig.MP3,
                sample_rate_hertz=24000,
                volume_percentage=100,
            ),
            dialog_state_in=embedded_assistant_pb2.DialogStateIn(
                language_code=self.language_code,
                conversation_state=self.conversation_state or b"",
                is_new_conversation=self.is_new_conversation,
            ),
            device_config=embedded_assistant_pb2.DeviceConfig(
                device_id=self.device_id,
                device_model_id=self.device_model_id,
            ),
            text_query=text_query,
        )
        # Continue current conversation with later requests.
        self.is_new_conversation = False
        if self.display:
            config.screen_out_config.screen_mode = PLAYING
        req = embedded_assistant_pb2.AssistRequest(config=config)
        assistant_helpers.log_assist_request_without_audio(req)
        return iter([req])

    def _handle_response(
        self, resp: embedded_assistant_pb2.AssistResponse, result: _AssistResult
    ) -> None:
        """Merge a streamed response into the accumulated result."""
        assistant_helpers.log_assist_response_without_audio(resp)
        if resp.screen_out.data:
            result.html = resp.screen_out.data
        if resp.dialog_state_out.conversation_state:
            self.conversation_state = resp.dialog_state_out.conversation_state
        if resp.dialog_state_out.supplemental_display_text:
            result.text = resp.dialog_state_out.supplemental_display_text
        if self.audio_out and resp.audio_out.audio_data:
            result.audio_chunks.append(resp.audio_out.audio_data)


def _create_channel_credentials(
    credentials: google.oauth2.credentials.Credentials,
) -> grpc.ChannelCredentials:
    """Create channel credentials that authorize each call with an OAuth2 token.

    This is the credentials half of
    :func:`google.auth.transport.grpc.secure_authorized_channel`, split out so
    that it can also be used with :mod:`grpc.aio`, for which google-auth does
    not provide a helper.
    """
    metadata_plugin = google.auth.transport.grpc.AuthMetadataPlugin(  # type: ignore[no-untyped-call]
        credentials, google.auth.transport.requests.Request()
    )
    return grpc.composite_channel_credentials(
        grpc.ssl_channel_credentials(),
        grpc.metadata_call_credentials(metadata_plugin),
    )


class TextAssistant(_TextAssistantBase):
    """Assistant that supports text based conversations."""

    def __init__(
        self,
        credentials: google.oauth2.credentials.Credentials,
        language_code: str = "en-US",
        device_model_id: str = "default",
        device_id: str = "default",
        display: bool = False,
        audio_out: bool = False,
        deadline_sec: int = DEFAULT_GRPC_DEADLINE,
        api_endpoint: str = ASSISTANT_API_ENDPOINT,
    ) -> None:
        """Initialize.

        credentials: OAuth2 credentials.
        language_code: language for the conversation.
        device_model_id: identifier of the device model.
        device_id: identifier of the registered device instance.
        display: enable visual display of assistant response.
        audio_out: enable audio response.
        deadline_sec: gRPC deadline in seconds for Google Assistant API call.
        api_endpoint: Address of Google Assistant API service.
        """
        super().__init__(
            language_code, device_model_id, device_id, display, audio_out, deadline_sec
        )
        # Create an authorized gRPC channel.
        self.channel = google.auth.transport.grpc.secure_authorized_channel(  # type: ignore[no-untyped-call]
            credentials, google.auth.transport.requests.Request(), api_endpoint
        )
        self.assistant = embedded_assistant_pb2_grpc.EmbeddedAssistantStub(self.channel)

    def __enter__(self) -> "TextAssistant":  # noqa: D105
        return self

    def __exit__(  # noqa: D105
        self,
        etype: type[BaseException] | None,
        e: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        """Close the underlying gRPC channel."""
        self.channel.close()

    def assist(self, text_query: str) -> tuple[str, bytes | None, bytes]:
        """Send a text request to the Assistant and return the response as a tuple of: [text, html, audio]."""
        result = _AssistResult()
        for resp in self.assistant.Assist(
            self._create_requests(text_query), timeout=self.deadline
        ):
            self._handle_response(resp, result)
        return result.as_tuple()


class TextAssistantAsync(_TextAssistantBase):
    """Assistant that supports text based conversations, using asyncio."""

    def __init__(
        self,
        credentials: google.oauth2.credentials.Credentials,
        language_code: str = "en-US",
        device_model_id: str = "default",
        device_id: str = "default",
        display: bool = False,
        audio_out: bool = False,
        deadline_sec: int = DEFAULT_GRPC_DEADLINE,
        api_endpoint: str = ASSISTANT_API_ENDPOINT,
    ) -> None:
        """Initialize.

        credentials: OAuth2 credentials.
        language_code: language for the conversation.
        device_model_id: identifier of the device model.
        device_id: identifier of the registered device instance.
        display: enable visual display of assistant response.
        audio_out: enable audio response.
        deadline_sec: gRPC deadline in seconds for Google Assistant API call.
        api_endpoint: Address of Google Assistant API service.
        """
        super().__init__(
            language_code, device_model_id, device_id, display, audio_out, deadline_sec
        )
        self._credentials = credentials
        self._api_endpoint = api_endpoint
        self._channel: grpc.aio.Channel | None = None
        self._lock = asyncio.Lock()

    async def _get_channel(self) -> grpc.aio.Channel:
        """Return the authorized gRPC channel, creating it on first use.

        A grpc.aio channel is bound to the event loop that is running when it is
        created, so it is created lazily to bind to the loop that calls assist()
        rather than the one, if any, that constructed this object.
        """
        async with self._lock:
            if self._channel is None:
                # Creating the channel credentials reads the CA bundle from
                # disk, so keep it off the event loop. Refreshing the OAuth2
                # token is blocking too, but gRPC invokes the auth metadata
                # plugin on its own thread.
                channel_credentials = await asyncio.get_running_loop().run_in_executor(
                    None, _create_channel_credentials, self._credentials
                )
                self._channel = grpc.aio.secure_channel(
                    self._api_endpoint, channel_credentials
                )
            return self._channel

    async def __aenter__(self) -> "TextAssistantAsync":  # noqa: D105
        return self

    async def __aexit__(  # noqa: D105
        self,
        etype: type[BaseException] | None,
        e: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.close()

    async def close(self) -> None:
        """Close the underlying gRPC channel, if one was opened."""
        async with self._lock:
            if self._channel is not None:
                await self._channel.close(None)
                self._channel = None

    async def assist(self, text_query: str) -> tuple[str, bytes | None, bytes]:
        """Send a text request to the Assistant and return the response as a tuple of: [text, html, audio]."""
        assistant = embedded_assistant_pb2_grpc.EmbeddedAssistantStub(
            await self._get_channel()
        )
        result = _AssistResult()
        async for resp in assistant.Assist(
            self._create_requests(text_query), timeout=self.deadline
        ):
            self._handle_response(resp, result)
        return result.as_tuple()

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

import google.auth.transport.grpc
import google.auth.transport.requests
import google.oauth2.credentials

from google.assistant.embedded.v1alpha2 import (
    embedded_assistant_pb2,
    embedded_assistant_pb2_grpc,
)

try:
    from . import assistant_helpers
except (SystemError, ImportError):
    import assistant_helpers


ASSISTANT_API_ENDPOINT = "embeddedassistant.googleapis.com"
DEFAULT_GRPC_DEADLINE = 60 * 3 + 5
PLAYING = embedded_assistant_pb2.ScreenOutConfig.PLAYING


class TextAssistant:
    """Assistant that supports text based conversations."""

    def __init__(
        self,
        credentials,
        language_code="en-US",
        device_model_id="default",
        device_id="default",
        display=False,
        audio_out=False,
        deadline_sec=DEFAULT_GRPC_DEADLINE,
        api_endpoint=ASSISTANT_API_ENDPOINT,
    ):
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
        self.language_code = language_code
        self.device_model_id = device_model_id
        self.device_id = device_id
        self.conversation_state = None
        # Force reset of first conversation.
        self.is_new_conversation = True
        self.display = display
        self.audio_out = audio_out
        # Create an authorized gRPC channel.
        channel = google.auth.transport.grpc.secure_authorized_channel(
            credentials, google.auth.transport.requests.Request(), api_endpoint
        )
        self.assistant = embedded_assistant_pb2_grpc.EmbeddedAssistantStub(channel)
        self.deadline = deadline_sec

    def __enter__(self):  # noqa: D105
        return self

    def __exit__(self, etype, e, traceback):  # noqa: D105
        if e:
            return False

    def assist(self, text_query):
        """Send a text request to the Assistant and return the response as a tuple of: [text, html, audio]."""

        def iter_assist_requests():
            config = embedded_assistant_pb2.AssistConfig(
                audio_out_config=embedded_assistant_pb2.AudioOutConfig(
                    encoding="MP3",
                    sample_rate_hertz=24000,
                    volume_percentage=100,
                ),
                dialog_state_in=embedded_assistant_pb2.DialogStateIn(
                    language_code=self.language_code,
                    conversation_state=self.conversation_state,
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
            yield req

        text_response = None
        html_response = None
        audio_response = b""
        for resp in self.assistant.Assist(iter_assist_requests(), self.deadline):
            assistant_helpers.log_assist_response_without_audio(resp)
            if resp.screen_out.data:
                html_response = resp.screen_out.data
            if resp.dialog_state_out.conversation_state:
                conversation_state = resp.dialog_state_out.conversation_state
                self.conversation_state = conversation_state
            if resp.dialog_state_out.supplemental_display_text:
                text_response = resp.dialog_state_out.supplemental_display_text
            if self.audio_out and resp.audio_out.audio_data:
                audio_response += resp.audio_out.audio_data
        return text_response, html_response, audio_response

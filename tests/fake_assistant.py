"""A fake Google Assistant gRPC service to test the clients against."""

from collections.abc import AsyncIterator, Iterator
from concurrent import futures
from dataclasses import dataclass, field

import grpc
import grpc.aio

from google.assistant.embedded.v1alpha2 import (
    embedded_assistant_pb2,
    embedded_assistant_pb2_grpc,
)


@dataclass
class FakeAssistant:
    """Canned responses for the fake service, and the requests it received.

    The requests are recorded so tests can assert on what the client sent,
    which is otherwise invisible.
    """

    text: str = ""
    html: bytes = b""
    audio_chunks: list[bytes] = field(default_factory=list)
    conversation_state: bytes = b""
    abort_with: grpc.StatusCode | None = None
    requests: list[embedded_assistant_pb2.AssistRequest] = field(default_factory=list)

    def responses(self) -> list[embedded_assistant_pb2.AssistResponse]:
        """Build the stream of responses to send back for one query.

        Each part is sent in its own message, and the audio in several, the way
        the real service streams them.
        """
        responses = []
        if self.html:
            responses.append(
                embedded_assistant_pb2.AssistResponse(
                    screen_out=embedded_assistant_pb2.ScreenOut(data=self.html)
                )
            )
        for chunk in self.audio_chunks:
            responses.append(
                embedded_assistant_pb2.AssistResponse(
                    audio_out=embedded_assistant_pb2.AudioOut(audio_data=chunk)
                )
            )
        responses.append(
            embedded_assistant_pb2.AssistResponse(
                dialog_state_out=embedded_assistant_pb2.DialogStateOut(
                    supplemental_display_text=self.text,
                    conversation_state=self.conversation_state,
                )
            )
        )
        return responses


class _Servicer(embedded_assistant_pb2_grpc.EmbeddedAssistantServicer):
    """Synchronous implementation of the fake service."""

    def __init__(self, fake: FakeAssistant) -> None:
        self.fake = fake

    def Assist(  # noqa: N802
        self,
        request_iterator: Iterator[embedded_assistant_pb2.AssistRequest],
        context: grpc.ServicerContext,
    ) -> Iterator[embedded_assistant_pb2.AssistResponse]:
        """Record the requests and stream back the canned responses."""
        self.fake.requests.extend(request_iterator)
        if self.fake.abort_with is not None:
            context.abort(self.fake.abort_with, "fake failure")
        yield from self.fake.responses()


class _AsyncServicer(embedded_assistant_pb2_grpc.EmbeddedAssistantServicer):
    """Asyncio implementation of the fake service."""

    def __init__(self, fake: FakeAssistant) -> None:
        self.fake = fake

    async def Assist(  # noqa: N802
        self,
        request_iterator: AsyncIterator[embedded_assistant_pb2.AssistRequest],
        context: grpc.aio.ServicerContext,  # type: ignore[type-arg]
    ) -> AsyncIterator[embedded_assistant_pb2.AssistResponse]:
        """Record the requests and stream back the canned responses."""
        async for request in request_iterator:
            self.fake.requests.append(request)
        if self.fake.abort_with is not None:
            await context.abort(self.fake.abort_with, "fake failure")
        for response in self.fake.responses():
            yield response


def serve(fake: FakeAssistant) -> tuple[grpc.Server, str]:
    """Start a synchronous fake service on a free port, and return it and its address."""
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=2))
    embedded_assistant_pb2_grpc.add_EmbeddedAssistantServicer_to_server(
        _Servicer(fake), server
    )
    port = server.add_insecure_port("localhost:0")
    server.start()
    return server, f"localhost:{port}"


async def serve_async(fake: FakeAssistant) -> tuple[grpc.aio.Server, str]:
    """Start an asyncio fake service on a free port, and return it and its address."""
    server = grpc.aio.server()
    embedded_assistant_pb2_grpc.add_EmbeddedAssistantServicer_to_server(
        _AsyncServicer(fake), server
    )
    port = server.add_insecure_port("localhost:0")
    await server.start()
    return server, f"localhost:{port}"

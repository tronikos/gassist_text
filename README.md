# gassist_text

A Python library for interacting with Google Assistant API via text.

## Credits

Uses <https://pypi.org/project/google-assistant-grpc/>. See instructions there how to get `credentials.json`.

Code is essentially a copy of <https://github.com/googlesamples/assistant-sdk-python/blob/master/google-assistant-sdk/googlesamples/assistant/grpc/textinput.py> wrapped in a package.

## Example

```python
import json
import google.oauth2.credentials
with open('/path/to/credentials.json', 'r') as f:
    credentials = google.oauth2.credentials.Credentials(token=None, **json.load(f))

from gassist_text import TextAssistant
with TextAssistant(credentials) as assistant:
    print(assistant.assist('tell me a joke')[0])
    print(assistant.assist('another one')[0])
```

### Async example

`TextAssistantAsync` is the asyncio equivalent of `TextAssistant`. It has the same
constructor and returns the same `(text, html, audio)` tuple, but `assist()` is a
coroutine and nothing blocks the event loop.

```python
import asyncio
import json
import google.oauth2.credentials
from gassist_text import TextAssistantAsync

with open('/path/to/credentials.json', 'r') as f:
    credentials = google.oauth2.credentials.Credentials(token=None, **json.load(f))

async def main():
    async with TextAssistantAsync(credentials) as assistant:
        print((await assistant.assist('tell me a joke'))[0])
        print((await assistant.assist('another one'))[0])

asyncio.run(main())
```

Notes:

- It is built on [`grpc.aio`](https://grpc.github.io/grpc/python/grpc_asyncio.html),
  which ships with `grpcio`; no extra dependency is needed.
- The gRPC channel is created on the first `assist()` call, so it binds to the event
  loop that actually uses it. Constructing the object outside of a running loop is fine.
- Refreshing the OAuth2 access token is blocking, but gRPC calls the auth metadata
  plugin on its own thread, so the event loop is not blocked.
- Neither class is safe for concurrent use: both keep the conversation state of a
  single conversation. Use one instance per conversation, or serialize the calls.

## Limitations/Known issues

If you see the issued commands in [My Google Activity](https://myactivity.google.com/myactivity) the library is working fine. If the commands don't have the expected outcome, don't open an issue in this repository. You should instead report the issue directly to [Google](https://github.com/googlesamples/assistant-sdk-python/issues). Examples of known Google Assistant API issues:

- Broadcast commands don't work unless speakers and device that runs this library are in the same network and IPv6 is disabled in the router
- Most queries for media controls don't work
  - not working: e.g. play music on kitchen speaker, stop kitchen speaker
  - working: e.g. play news on kitchen speaker, play rain sounds on bedroom speaker
- Routines don't work
- Commands that need to verify your identity through voice match don't work

To get personal results working you need to create an OAuth client ID of Desktop app, see step by step instructions [in this article](https://www.home-assistant.io/integrations/google_assistant_sdk/#enable-personal-results-for-advanced-users).

## Development environment

```sh
python3 -m venv .venv
source .venv/bin/activate
# for Windows CMD:
# .venv\Scripts\activate.bat
# for Windows PowerShell:
# .venv\Scripts\Activate.ps1

# Install dependencies
python -m pip install --upgrade pip
python -m pip install -e .

# Generate embedded_assistant_pb2.py and embedded_assistant_pb2_grpc.py,
# and the .pyi type stubs that let mypy check the protobuf messages
python -m pip install grpcio-tools mypy-protobuf
python -m grpc_tools.protoc -Isrc --python_out=src --grpc_python_out=src --mypy_out=src --mypy_grpc_out=src src/google/assistant/embedded/v1alpha2/embedded_assistant.proto

# Run pre-commit
python -m pip install pre-commit
pre-commit autoupdate
pre-commit install
pre-commit run --all-files

# Alternative: run formatter, lint
python -m pip install isort black flake8 ruff
isort . ; black . ; flake8 . ; ruff check . --fix

# Run tests
python -m pip install pytest
pytest

# Run command line interactive tool
python -m pip install click beautifulsoup4
python demo.py --display --audio_out
# ... or exercise the asyncio client
python demo.py --display --audio_out --use-async

# Build package
python -m pip install build
python -m build
```

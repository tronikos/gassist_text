# gassist_text

A Python library for interacting with Google Assistant API via text

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

## How to run

```sh
python3 -m venv venv
source venv/bin/activate
pip3 install -r requirements.txt

# Run command line interactive tool
python3 gassist_text/textinput.py
```

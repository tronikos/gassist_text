"""Command line interactive tool for TextAssistant."""
import json
import logging
import os

from bs4 import BeautifulSoup
import click
import google.oauth2.credentials

from gassist_text import TextAssistant

try:
    from . import browser_helpers
except (SystemError, ImportError):
    import browser_helpers


ASSISTANT_API_ENDPOINT = "embeddedassistant.googleapis.com"
DEFAULT_GRPC_DEADLINE = 60 * 3 + 5


@click.command()
@click.option(
    "--api-endpoint",
    default=ASSISTANT_API_ENDPOINT,
    metavar="<api endpoint>",
    show_default=True,
    help="Address of Google Assistant API service.",
)
@click.option(
    "--credentials",
    metavar="<credentials>",
    show_default=True,
    default=os.path.join(click.get_app_dir("google-oauthlib-tool"), "credentials.json"),
    help="Path to read OAuth2 credentials.",
)
@click.option(
    "--device-model-id",
    metavar="<device model id>",
    required=True,
    default="default",
    help=(
        "Unique device model identifier, "
        "if not specified, it is read from --device-config"
    ),
)
@click.option(
    "--device-id",
    metavar="<device id>",
    required=True,
    default="default",
    help=(
        "Unique registered device instance identifier, "
        "if not specified, it is read from --device-config, "
        "if no device_config found: a new device is registered "
        "using a unique id and a new device config is saved"
    ),
)
@click.option(
    "--lang",
    show_default=True,
    metavar="<language code>",
    default="en-US",
    help="Language code of the Assistant",
)
@click.option(
    "--display",
    is_flag=True,
    default=False,
    help="Enable visual display of Assistant responses in HTML.",
)
@click.option("--audio_out", is_flag=True, default=False, help="Enable audio response.")
@click.option("--verbose", "-v", is_flag=True, default=False, help="Verbose logging.")
@click.option(
    "--grpc-deadline",
    default=DEFAULT_GRPC_DEADLINE,
    metavar="<grpc deadline>",
    show_default=True,
    help="gRPC deadline in seconds",
)
def _main(
    api_endpoint,
    credentials,
    device_model_id,
    device_id,
    lang,
    display,
    audio_out,
    verbose,
    grpc_deadline,
    *args,
    **kwargs
):
    system_browser = browser_helpers.system_browser
    # Setup logging.
    logging.basicConfig(level=logging.DEBUG if verbose else logging.INFO)

    # Load OAuth 2.0 credentials.
    try:
        with open(credentials) as f:
            credentials = google.oauth2.credentials.Credentials(
                token=None, **json.load(f)
            )
            http_request = google.auth.transport.requests.Request()
            credentials.refresh(http_request)
    except Exception as e:
        logging.error("Error loading credentials: %s", e)
        logging.error(
            "Run google-oauthlib-tool to initialize " "new OAuth 2.0 credentials."
        )
        return

    with TextAssistant(
        credentials,
        lang,
        device_model_id,
        device_id,
        display,
        audio_out,
        grpc_deadline,
        api_endpoint,
    ) as assistant:
        while True:
            query = click.prompt("")
            click.echo("<you> %s" % query)
            response_text, response_html, audio_response = assistant.assist(
                text_query=query
            )
            if response_text:
                click.echo("<@assistant> %s" % response_text)
            if response_html:
                html = BeautifulSoup(response_html, "html.parser")
                card_content = html.find("div", id="assistant-card-content")
                if card_content:
                    html = card_content
                click.echo(
                    "<@assistant (parsed from html)> %s"
                    % html.get_text(separator="\n", strip=True)
                )
                system_browser.display(
                    response_html, "google-assistant-sdk-screen-out.html"
                )
            if audio_response:
                system_browser.display(
                    audio_response, "google-assistant-sdk-audio-out.mp3"
                )


if __name__ == "__main__":
    _main()

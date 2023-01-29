"""Tests for TextAssistant."""

import unittest

import google.oauth2.credentials
import grpc

from gassist_text import TextAssistant


class MyTestCase(unittest.TestCase):
    def test_textinput(self):
        credentials = google.oauth2.credentials.Credentials(token=None)
        with TextAssistant(credentials) as assistant:
            self.assertRaises(
                grpc._channel._MultiThreadedRendezvous,
                assistant.assist,
                "tell me a joke",
            )

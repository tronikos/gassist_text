# Copyright (C) 2018 Google Inc.
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

"""Helpers for storing and opening HTML files."""

import os.path
import tempfile
import webbrowser


class SystemBrowser:
    """Class that can store HTML files in a temp directory and open them using the system Web browser."""

    def __init__(self) -> None:
        """Initialize temp directory."""
        self.tempdir = tempfile.mkdtemp()

    def display(self, contents: bytes, filename: str) -> None:
        """Store HTML contents in a file in the temp directory and open it."""
        full_filename = os.path.join(self.tempdir, filename)
        with open(full_filename, "wb") as f:
            f.write(contents)
        webbrowser.open(full_filename, new=0)


system_browser = SystemBrowser()

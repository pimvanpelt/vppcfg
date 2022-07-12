""" module to help locate unittest resources """
#!/usr/bin/env python
#
# Copyright (c) 2022 Ray Kinsella
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at:
#     http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# -*- coding: utf-8 -*-

import os


class UnitTestYaml:
    """Helper classes to find and load unit test yaml resources"""

    def __init__(self, fpath):
        self.file = None
        self.filename = fpath
        self.resdir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "../unittest")
        )

    def __enter__(self):
        self.file = open(
            os.path.join(self.resdir, self.filename), "r", encoding="utf-8"
        )
        return self.file

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.file.close()

    def __str__(self):
        return self.file

#
# Copyright (c) 2022 Pim van Pelt
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
""" Unit tests for MAC addresses """
import unittest
from . import mac


class TestMACMethods(unittest.TestCase):
    def test_is_valid(self):
        self.assertTrue(mac.is_valid("00:01:02:03:04:05"))
        self.assertTrue(mac.is_valid("00-01-02-03-04-05"))
        self.assertTrue(mac.is_valid("0001.0203.0405"))
        self.assertFalse(mac.is_valid("hoi"))

    def test_is_local(self):
        self.assertTrue(mac.is_local("02:00:00:00:00:00"))
        self.assertFalse(mac.is_local("00:00:00:00:00:00"))

    def test_is_multicast(self):
        self.assertTrue(mac.is_multicast("01:00:00:00:00:00"))
        self.assertFalse(mac.is_multicast("00:00:00:00:00:00"))

    def test_is_unicast(self):
        self.assertFalse(mac.is_unicast("01:00:00:00:00:00"))
        self.assertTrue(mac.is_unicast("00:00:00:00:00:00"))

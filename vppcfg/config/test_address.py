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
""" Unit tests for addresses """
import unittest
import yaml
from . import address


class TestAddressMethods(unittest.TestCase):
    def test_get_canonical(self):
        self.assertEqual(address.get_canonical("0.0.0.0"), "0.0.0.0")
        self.assertEqual(address.get_canonical("0.0.0.0/0"), "0.0.0.0/0")
        self.assertEqual(address.get_canonical("192.168.1.1"), "192.168.1.1")
        self.assertEqual(address.get_canonical("192.168.1.1/32"), "192.168.1.1/32")
        self.assertEqual(address.get_canonical("2001:db8::1"), "2001:db8::1")
        self.assertEqual(address.get_canonical("2001:db8::1/64"), "2001:db8::1/64")

        self.assertEqual(address.get_canonical("2001:dB8::1/128"), "2001:db8::1/128")
        self.assertEqual(address.get_canonical("2001:db8:0::1/128"), "2001:db8::1/128")
        self.assertEqual(address.get_canonical("2001:db8::0:1"), "2001:db8::1")

    def test_is_canonical(self):
        self.assertTrue(address.is_canonical("0.0.0.0"))
        self.assertTrue(address.is_canonical("0.0.0.0/0"))
        self.assertTrue(address.is_canonical("192.168.1.1"))
        self.assertTrue(address.is_canonical("192.168.1.1/32"))
        self.assertTrue(address.is_canonical("2001:db8::1"))
        self.assertTrue(address.is_canonical("2001:db8::1/64"))

        self.assertFalse(address.is_canonical("2001:dB8::1/128"))  # Capitals
        self.assertFalse(address.is_canonical("2001:db8:0::1/128"))  # Spurious 0
        self.assertFalse(address.is_canonical("2001:db8::0:1"))  # Spurious 0

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
""" Unit tests for taps """
import unittest
from . import acl


class TestACLMethods(unittest.TestCase):
    def test_get_port_low_high(self):
        lo, hi = acl.get_port_low_high(80)
        self.assertEqual(80, lo)
        self.assertEqual(80, hi)

        lo, hi = acl.get_port_low_high("80")
        self.assertEqual(80, lo)
        self.assertEqual(80, hi)

        lo, hi = acl.get_port_low_high("www")
        self.assertEqual(80, lo)
        self.assertEqual(80, hi)

        lo, hi = acl.get_port_low_high("any")
        self.assertEqual(0, lo)
        self.assertEqual(65535, hi)

        lo, hi = acl.get_port_low_high("-1024")
        self.assertEqual(0, lo)
        self.assertEqual(1024, hi)

        lo, hi = acl.get_port_low_high("1024-")
        self.assertEqual(1024, lo)
        self.assertEqual(65535, hi)

        lo, hi = acl.get_port_low_high("1000-2000")
        self.assertEqual(1000, lo)
        self.assertEqual(2000, hi)

        lo, hi = acl.get_port_low_high("0-65535")
        self.assertEqual(0, lo)
        self.assertEqual(65535, hi)

        lo, hi = acl.get_port_low_high("bla")
        self.assertIsNone(lo)
        self.assertIsNone(hi)

        lo, hi = acl.get_port_low_high("foo-bar")
        self.assertIsNone(lo)
        self.assertIsNone(hi)

    def test_get_protocol(self):
        proto = acl.get_protocol(1)
        self.assertEqual(1, proto)

        proto = acl.get_protocol("icmp")
        self.assertEqual(1, proto)

        proto = acl.get_protocol("unknown")
        self.assertIsNone(proto)

    def test_get_icmp_low_high(self):
        lo, hi = acl.get_icmp_low_high(3)
        self.assertEqual(3, lo)
        self.assertEqual(3, hi)

        lo, hi = acl.get_icmp_low_high("3")
        self.assertEqual(3, lo)
        self.assertEqual(3, hi)

        lo, hi = acl.get_icmp_low_high("any")
        self.assertEqual(0, lo)
        self.assertEqual(255, hi)

        lo, hi = acl.get_icmp_low_high("10-")
        self.assertEqual(10, lo)
        self.assertEqual(255, hi)

        lo, hi = acl.get_icmp_low_high("-10")
        self.assertEqual(0, lo)
        self.assertEqual(10, hi)

        lo, hi = acl.get_icmp_low_high("10-20")
        self.assertEqual(10, lo)
        self.assertEqual(20, hi)

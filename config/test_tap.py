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
import yaml
import config.tap as tap


class TestTAPMethods(unittest.TestCase):
    def setUp(self):
        with open("unittest/test_tap.yaml", "r") as f:
            self.cfg = yaml.load(f, Loader=yaml.FullLoader)

    def test_get_by_name(self):
        ifname, iface = tap.get_by_name(self.cfg, "tap0")
        self.assertIsNotNone(iface)
        self.assertEqual("tap0", ifname)

        ifname, iface = tap.get_by_name(self.cfg, "tap-noexist")
        self.assertIsNone(ifname)
        self.assertIsNone(iface)

    def test_is_tap(self):
        self.assertTrue(tap.is_tap(self.cfg, "tap0"))
        self.assertTrue(tap.is_tap(self.cfg, "tap1"))
        self.assertFalse(tap.is_tap(self.cfg, "tap-noexist"))

    def test_is_host_name_unique(self):
        self.assertTrue(tap.is_host_name_unique(self.cfg, "tap0"))
        self.assertTrue(tap.is_host_name_unique(self.cfg, "tap1"))
        self.assertTrue(tap.is_host_name_unique(self.cfg, "tap-noexist"))
        self.assertFalse(tap.is_host_name_unique(self.cfg, "vpp-tap"))

    def test_enumerators(self):
        ifs = tap.get_taps(self.cfg)
        self.assertEqual(len(ifs), 4)
        self.assertIn("tap0", ifs)
        self.assertIn("tap1", ifs)
        self.assertNotIn("tap-noexist", ifs)

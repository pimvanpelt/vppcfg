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
""" Unit tests for loopbacks """
import unittest
import yaml
import config.loopback as loopback


class TestLoopbackMethods(unittest.TestCase):
    def setUp(self):
        with open("unittest/test_loopback.yaml", "r") as f:
            self.cfg = yaml.load(f, Loader=yaml.FullLoader)

    def test_get_by_lcp_name(self):
        ifname, iface = loopback.get_by_lcp_name(self.cfg, "loop56789012345")
        self.assertIsNotNone(iface)
        self.assertEqual("loop1", ifname)

        ifname, iface = loopback.get_by_lcp_name(self.cfg, "lcp-noexist")
        self.assertIsNone(iface)
        self.assertIsNone(ifname)

    def test_get_by_name(self):
        ifname, iface = loopback.get_by_name(self.cfg, "loop1")
        self.assertIsNotNone(iface)
        self.assertEqual("loop1", ifname)
        self.assertEqual(iface["mtu"], 2000)

        ifname, iface = loopback.get_by_name(self.cfg, "loop-noexist")
        self.assertIsNone(ifname)
        self.assertIsNone(iface)

    def test_enumerators(self):
        ifs = loopback.get_loopbacks(self.cfg)
        self.assertEqual(len(ifs), 3)
        self.assertIn("loop0", ifs)
        self.assertIn("loop1", ifs)
        self.assertIn("loop2", ifs)
        self.assertNotIn("loop-noexist", ifs)

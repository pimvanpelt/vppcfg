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
""" Unit tests for LCPs """
import unittest
import yaml
import config.lcp as lcp
import config.interface as interface


class TestLCPMethods(unittest.TestCase):
    def setUp(self):
        with open("unittest/test_lcp.yaml", "r") as f:
            self.cfg = yaml.load(f, Loader=yaml.FullLoader)

    def test_enumerators(self):
        lcps = lcp.get_lcps(self.cfg)
        self.assertIn("e1", lcps)
        self.assertIn("foo", lcps)
        self.assertIn("e2", lcps)
        loopback_lcps = lcp.get_lcps(self.cfg, interfaces=False, bridgedomains=False)
        self.assertIn("thrice", loopback_lcps)
        self.assertNotIn("e1", loopback_lcps)

    def test_lcp(self):
        self.assertTrue(lcp.is_unique(self.cfg, "e1"))
        self.assertTrue(lcp.is_unique(self.cfg, "foo"))
        self.assertTrue(lcp.is_unique(self.cfg, "notexist"))

        self.assertFalse(lcp.is_unique(self.cfg, "twice"))
        self.assertFalse(lcp.is_unique(self.cfg, "thrice"))

    def test_qinx(self):
        qinx_ifname, qinx_iface = interface.get_by_name(
            self.cfg, "GigabitEthernet1/0/1.201"
        )
        mid_ifname, mid_iface = interface.get_qinx_parent_by_name(
            self.cfg, "GigabitEthernet1/0/1.201"
        )
        parent_ifname, parent_iface = interface.get_parent_by_name(
            self.cfg, "GigabitEthernet1/0/1.201"
        )

        self.assertEqual(qinx_ifname, "GigabitEthernet1/0/1.201")
        self.assertEqual(mid_ifname, "GigabitEthernet1/0/1.200")
        self.assertEqual(parent_ifname, "GigabitEthernet1/0/1")

        qinx_ifname, qinx_iface = interface.get_by_name(
            self.cfg, "GigabitEthernet1/0/1.201"
        )
        mid_ifname, mid_iface = interface.get_qinx_parent_by_name(
            self.cfg, "GigabitEthernet1/0/1.201"
        )
        parent_ifname, parent_iface = interface.get_parent_by_name(
            self.cfg, "GigabitEthernet1/0/1.201"
        )

        self.assertEqual(qinx_ifname, "GigabitEthernet1/0/1.201")
        self.assertEqual(mid_ifname, "GigabitEthernet1/0/1.200")
        self.assertEqual(parent_ifname, "GigabitEthernet1/0/1")

        ifname, iface = interface.get_qinx_parent_by_name(
            self.cfg, "GigabitEthernet1/0/1.100"
        )
        self.assertIsNone(ifname)
        self.assertIsNone(iface)

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
""" Unit tests for bridgedomains """
import unittest
import yaml
from . import bridgedomain
from .unittestyaml import UnitTestYaml


class TestBridgeDomainMethods(unittest.TestCase):
    def setUp(self):
        with UnitTestYaml("test_bridgedomain.yaml") as f:
            self.cfg = yaml.load(f, Loader=yaml.FullLoader)

    def test_get_by_name(self):
        ifname, iface = bridgedomain.get_by_name(self.cfg, "bd10")
        self.assertIsNotNone(iface)
        self.assertEqual("bd10", ifname)
        self.assertEqual(iface["mtu"], 3000)
        self.assertIn("BondEthernet0", iface["interfaces"])

        ifname, iface = bridgedomain.get_by_name(self.cfg, "bd-notexist")
        self.assertIsNone(iface)
        self.assertIsNone(ifname)

    def test_is_bridgedomain(self):
        self.assertTrue(bridgedomain.is_bridgedomain(self.cfg, "bd10"))
        self.assertTrue(bridgedomain.is_bridgedomain(self.cfg, "bd11"))
        self.assertFalse(bridgedomain.is_bridgedomain(self.cfg, "bd-notexist"))
        self.assertFalse(bridgedomain.is_bridgedomain(self.cfg, "GigabitEthernet1/0/0"))

    def test_members(self):
        self.assertTrue(
            bridgedomain.is_bridge_interface(self.cfg, "GigabitEthernet1/0/0")
        )
        self.assertTrue(
            bridgedomain.is_bridge_interface(self.cfg, "GigabitEthernet2/0/0.100")
        )
        self.assertFalse(
            bridgedomain.is_bridge_interface(self.cfg, "GigabitEthernet3/0/0")
        )
        self.assertFalse(
            bridgedomain.is_bridge_interface(self.cfg, "GigabitEthernet3/0/0.100")
        )

    def test_unique(self):
        self.assertFalse(
            bridgedomain.is_bridge_interface_unique(self.cfg, "GigabitEthernet1/0/0")
        )
        self.assertTrue(
            bridgedomain.is_bridge_interface_unique(
                self.cfg, "GigabitEthernet2/0/0.100"
            )
        )

    def test_enumerators(self):
        ifs = bridgedomain.get_bridge_interfaces(self.cfg)
        self.assertEqual(len(ifs), 8)
        self.assertIn("BondEthernet0", ifs)
        self.assertIn("GigabitEthernet1/0/0", ifs)
        self.assertIn("GigabitEthernet2/0/0.100", ifs)

    def test_bvi_unique(self):
        self.assertTrue(bridgedomain.bvi_unique(self.cfg, "loop0"))
        self.assertFalse(bridgedomain.bvi_unique(self.cfg, "loop1"))
        self.assertTrue(bridgedomain.bvi_unique(self.cfg, "loop2"))

    def test_get_bridgedomains(self):
        ifs = bridgedomain.get_bridgedomains(self.cfg)
        self.assertEqual(len(ifs), 6)

    def test_get_settings(self):
        settings = bridgedomain.get_settings(self.cfg, "bd1")
        self.assertIsNone(settings)

        settings = bridgedomain.get_settings(self.cfg, "bd10")
        self.assertTrue(settings["learn"])
        self.assertTrue(settings["unknown-unicast-flood"])
        self.assertTrue(settings["unicast-flood"])
        self.assertEqual(settings["mac-age-minutes"], 0)

        settings = bridgedomain.get_settings(self.cfg, "bd11")
        self.assertTrue(settings["learn"])
        self.assertFalse(settings["unknown-unicast-flood"])
        self.assertFalse(settings["unicast-flood"])
        self.assertEqual(settings["mac-age-minutes"], 10)

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
""" Unit tests for vxlan_tunnels """
import unittest
import yaml
from . import vxlan_tunnel
from .unittestyaml import UnitTestYaml


class TestVXLANMethods(unittest.TestCase):
    def setUp(self):
        with UnitTestYaml("test_vxlan_tunnel.yaml") as f:
            self.cfg = yaml.load(f, Loader=yaml.FullLoader)

    def test_get_by_name(self):
        ifname, iface = vxlan_tunnel.get_by_name(self.cfg, "vxlan_tunnel0")
        self.assertIsNotNone(iface)
        self.assertEqual("vxlan_tunnel0", ifname)

        ifname, iface = vxlan_tunnel.get_by_name(self.cfg, "vxlan_tunnel-noexist")
        self.assertIsNone(ifname)
        self.assertIsNone(iface)

    def test_is_vxlan_tunnel(self):
        self.assertTrue(vxlan_tunnel.is_vxlan_tunnel(self.cfg, "vxlan_tunnel0"))
        self.assertFalse(vxlan_tunnel.is_vxlan_tunnel(self.cfg, "vxlan_tunnel-noexist"))
        self.assertFalse(vxlan_tunnel.is_vxlan_tunnel(self.cfg, "GigabitEthernet1/0/0"))

    def test_enumerators(self):
        ifs = vxlan_tunnel.get_vxlan_tunnels(self.cfg)
        self.assertEqual(len(ifs), 4)
        self.assertIn("vxlan_tunnel0", ifs)
        self.assertIn("vxlan_tunnel1", ifs)
        self.assertIn("vxlan_tunnel2", ifs)
        self.assertIn("vxlan_tunnel3", ifs)
        self.assertNotIn("vxlan_tunnel-noexist", ifs)

    def test_vni_unique(self):
        self.assertTrue(vxlan_tunnel.vni_unique(self.cfg, 100))
        self.assertFalse(vxlan_tunnel.vni_unique(self.cfg, 101))
        self.assertTrue(vxlan_tunnel.vni_unique(self.cfg, 102))

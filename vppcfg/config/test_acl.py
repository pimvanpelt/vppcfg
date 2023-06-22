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
from . import acl
from .unittestyaml import UnitTestYaml


class TestACLMethods(unittest.TestCase):
    def setUp(self):
        with UnitTestYaml("test_acl.yaml") as f:
            self.cfg = yaml.load(f, Loader=yaml.FullLoader)

    def test_get_acls(self):
        acllist = acl.get_acls(self.cfg)
        self.assertIsInstance(acllist, list)
        self.assertEqual(2, len(acllist))

    def test_get_by_name(self):
        aclname, _acl = acl.get_by_name(self.cfg, "deny-all")
        self.assertIsNotNone(_acl)
        self.assertEqual("deny-all", aclname)

        aclname, _acl = acl.get_by_name(self.cfg, "acl-noexist")
        self.assertIsNone(aclname)
        self.assertIsNone(_acl)

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

    def test_is_ip(self):
        self.assertTrue(acl.is_ip("192.0.2.1"))
        self.assertTrue(acl.is_ip("192.0.2.1/24"))
        self.assertTrue(acl.is_ip("192.0.2.0/24"))
        self.assertTrue(acl.is_ip("2001:db8::1"))
        self.assertTrue(acl.is_ip("2001:db8::1/64"))
        self.assertTrue(acl.is_ip("2001:db8::/64"))
        self.assertFalse(acl.is_ip(True))
        self.assertFalse(acl.is_ip("String"))
        self.assertFalse(acl.is_ip([]))
        self.assertFalse(acl.is_ip({}))

    def test_get_network_list(self):
        for s in ["192.0.2.1", "192.0.2.1/24", "2001:db8::1", "2001:db8::1/64"]:
            l = acl.get_network_list(self.cfg, s)
            self.assertIsInstance(l, list)
            self.assertEquals(1, len(l))
            n = l[0]

        l = acl.get_network_list(self.cfg, "trusted")
        self.assertIsInstance(l, list)
        self.assertEquals(5, len(l))

        l = acl.get_network_list(self.cfg, "trusted", want_ipv6=False)
        self.assertIsInstance(l, list)
        self.assertEquals(2, len(l))

        l = acl.get_network_list(self.cfg, "trusted", want_ipv4=False)
        self.assertIsInstance(l, list)
        self.assertEquals(3, len(l))

        l = acl.get_network_list(self.cfg, "trusted", want_ipv4=False, want_ipv6=False)
        self.assertIsInstance(l, list)
        self.assertEquals(0, len(l))

        l = acl.get_network_list(self.cfg, "pl-notexist")
        self.assertIsInstance(l, list)
        self.assertEquals(0, len(l))

    def test_network_list_has_family(self):
        l = acl.get_network_list(self.cfg, "trusted")
        self.assertTrue(acl.network_list_has_family(l, 4))
        self.assertTrue(acl.network_list_has_family(l, 6))

        l = acl.get_network_list(self.cfg, "trusted", want_ipv4=False)
        self.assertFalse(acl.network_list_has_family(l, 4))
        self.assertTrue(acl.network_list_has_family(l, 6))

        l = acl.get_network_list(self.cfg, "trusted", want_ipv6=False)
        self.assertTrue(acl.network_list_has_family(l, 4))
        self.assertFalse(acl.network_list_has_family(l, 6))

        l = acl.get_network_list(self.cfg, "trusted", want_ipv4=False, want_ipv6=False)
        self.assertFalse(acl.network_list_has_family(l, 4))
        self.assertFalse(acl.network_list_has_family(l, 6))

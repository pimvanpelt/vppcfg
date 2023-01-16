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
from . import prefixlist
from .unittestyaml import UnitTestYaml


class TestACLMethods(unittest.TestCase):
    def setUp(self):
        with UnitTestYaml("test_prefixlist.yaml") as f:
            self.cfg = yaml.load(f, Loader=yaml.FullLoader)

    def test_get_prefixlists(self):
        plist = prefixlist.get_prefixlists(self.cfg)
        self.assertIsInstance(plist, list)
        self.assertEqual(5, len(plist))

    def test_get_by_name(self):
        plname, _pl = prefixlist.get_by_name(self.cfg, "trusted")
        self.assertIsNotNone(_pl)
        self.assertEqual("trusted", plname)

        plname, _pl = prefixlist.get_by_name(self.cfg, "pl-noexist")
        self.assertIsNone(plname)
        self.assertIsNone(_pl)

    def test_count(self):
        v4, v6 = prefixlist.count(self.cfg, "trusted")
        self.assertEqual(2, v4)
        self.assertEqual(2, v6)

        v4, v6 = prefixlist.count(self.cfg, "empty")
        self.assertEqual(0, v4)
        self.assertEqual(0, v6)

        v4, v6 = prefixlist.count(self.cfg, "pl-noexist")
        self.assertEqual(0, v4)
        self.assertEqual(0, v6)

    def test_count_ipv4(self):
        self.assertEqual(2, prefixlist.count_ipv4(self.cfg, "trusted"))
        self.assertEqual(0, prefixlist.count_ipv4(self.cfg, "empty"))
        self.assertEqual(0, prefixlist.count_ipv4(self.cfg, "pl-noexist"))

    def test_count_ipv6(self):
        self.assertEqual(2, prefixlist.count_ipv6(self.cfg, "trusted"))
        self.assertEqual(0, prefixlist.count_ipv6(self.cfg, "empty"))
        self.assertEqual(0, prefixlist.count_ipv6(self.cfg, "pl-noexist"))

    def test_has_ipv4(self):
        self.assertTrue(prefixlist.has_ipv4(self.cfg, "trusted"))
        self.assertFalse(prefixlist.has_ipv4(self.cfg, "empty"))
        self.assertFalse(prefixlist.has_ipv4(self.cfg, "pl-noexist"))

    def test_has_ipv6(self):
        self.assertTrue(prefixlist.has_ipv6(self.cfg, "trusted"))
        self.assertFalse(prefixlist.has_ipv6(self.cfg, "empty"))
        self.assertFalse(prefixlist.has_ipv6(self.cfg, "pl-noexist"))

    def test_is_empty(self):
        self.assertFalse(prefixlist.is_empty(self.cfg, "trusted"))
        self.assertTrue(prefixlist.is_empty(self.cfg, "empty"))
        self.assertTrue(prefixlist.is_empty(self.cfg, "pl-noexist"))

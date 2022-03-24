import unittest
import yaml
import config.bridgedomain as bridgedomain

class TestBridgeDomainMethods(unittest.TestCase):
    def setUp(self):
        with open("unittest/test_bridgedomain.yaml", "r") as f:
            self.cfg = yaml.load(f, Loader = yaml.FullLoader)

    def test_get_by_lcp_name(self):
        ifname, iface = bridgedomain.get_by_lcp_name(self.cfg, "bvi12")
        self.assertIsNotNone(iface)
        self.assertEqual("bd12", ifname)

        ifname, iface = bridgedomain.get_by_lcp_name(self.cfg, "bvi-noexist")
        self.assertIsNone(iface)
        self.assertIsNone(ifname)

    def test_get_by_name(self):
        ifname, iface = bridgedomain.get_by_name(self.cfg, "bd10")
        self.assertIsNotNone(iface)
        self.assertEqual("bd10", ifname)
        self.assertEqual(iface['mtu'], 3000)
        self.assertIn("BondEthernet0", iface['interfaces'])

        ifname, iface = bridgedomain.get_by_name(self.cfg, "bd-notexist")
        self.assertIsNone(iface)
        self.assertIsNone(ifname)

    def test_is_bridgedomain(self):
        self.assertTrue(bridgedomain.is_bridgedomain(self.cfg, "bd10"))
        self.assertTrue(bridgedomain.is_bridgedomain(self.cfg, "bd11"))
        self.assertTrue(bridgedomain.is_bridgedomain(self.cfg, "bd12"))
        self.assertFalse(bridgedomain.is_bridgedomain(self.cfg, "bd-notexist"))
        self.assertFalse(bridgedomain.is_bridgedomain(self.cfg, "GigabitEthernet1/0/0"))

    def test_is_bvi(self):
        self.assertFalse(bridgedomain.is_bvi(self.cfg, "bvi10"))
        self.assertTrue(bridgedomain.is_bvi(self.cfg, "bvi11"))
        self.assertTrue(bridgedomain.is_bvi(self.cfg, "bvi12"))
        self.assertFalse(bridgedomain.is_bvi(self.cfg, "bvi-notexist"))
        self.assertFalse(bridgedomain.is_bvi(self.cfg, "GigabitEthernet1/0/0"))

    def test_members(self):
        self.assertTrue(bridgedomain.is_bridge_interface(self.cfg, "GigabitEthernet1/0/0"))
        self.assertTrue(bridgedomain.is_bridge_interface(self.cfg, "GigabitEthernet2/0/0.100"))
        self.assertFalse(bridgedomain.is_bridge_interface(self.cfg, "GigabitEthernet3/0/0"))
        self.assertFalse(bridgedomain.is_bridge_interface(self.cfg, "GigabitEthernet3/0/0.100"))

    def test_unique(self):
        self.assertFalse(bridgedomain.is_bridge_interface_unique(self.cfg, "GigabitEthernet1/0/0"))
        self.assertTrue(bridgedomain.is_bridge_interface_unique(self.cfg, "GigabitEthernet2/0/0.100"))

    def test_enumerators(self):
        ifs = bridgedomain.get_bridge_interfaces(self.cfg)
        self.assertEqual(len(ifs), 8)
        self.assertIn("BondEthernet0", ifs)
        self.assertIn("GigabitEthernet1/0/0", ifs)
        self.assertIn("GigabitEthernet2/0/0.100", ifs)

    def test_get_bridgedomains(self):
        ifs = bridgedomain.get_bridgedomains(self.cfg)
        self.assertEqual(len(ifs), 3)

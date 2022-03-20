import unittest
import yaml
import validator.bridgedomain as bridgedomain

class TestBridgeDomainMethods(unittest.TestCase):
    def setUp(self):
        with open("unittest/test_bridgedomain.yaml", "r") as f:
            self.cfg = yaml.load(f, Loader = yaml.FullLoader)

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

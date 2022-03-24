import unittest
import yaml
import config.bondethernet as bondethernet

class TestBondEthernetMethods(unittest.TestCase):
    def setUp(self):
        with open("unittest/test_bondethernet.yaml", "r") as f:
            self.cfg = yaml.load(f, Loader = yaml.FullLoader)

    def test_get_by_name(self):
        ifname, iface = bondethernet.get_by_name(self.cfg, "BondEthernet0")
        self.assertIsNotNone(iface)
        self.assertEqual("BondEthernet0", ifname)
        self.assertIn("GigabitEthernet1/0/0", iface['interfaces'])
        self.assertNotIn("GigabitEthernet2/0/0", iface['interfaces'])

        ifname, iface = bondethernet.get_by_name(self.cfg, "BondEthernet-notexist")
        self.assertIsNone(iface)
        self.assertIsNone(ifname)

    def test_members(self):
        self.assertTrue(bondethernet.is_bond_member(self.cfg, "GigabitEthernet1/0/0"))
        self.assertTrue(bondethernet.is_bond_member(self.cfg, "GigabitEthernet1/0/1"))
        self.assertFalse(bondethernet.is_bond_member(self.cfg, "GigabitEthernet2/0/0"))
        self.assertFalse(bondethernet.is_bond_member(self.cfg, "GigabitEthernet2/0/0.100"))

    def test_is_bondethernet(self):
        self.assertTrue(bondethernet.is_bondethernet(self.cfg, "BondEthernet0"))
        self.assertFalse(bondethernet.is_bondethernet(self.cfg, "BondEthernet-notexist"))
        self.assertFalse(bondethernet.is_bondethernet(self.cfg, "GigabitEthernet1/0/0"))

    def test_enumerators(self):
        ifs = bondethernet.get_bondethernets(self.cfg)
        self.assertEqual(len(ifs), 1)
        self.assertIn("BondEthernet0", ifs)
        self.assertNotIn("BondEthernet-noexist", ifs)


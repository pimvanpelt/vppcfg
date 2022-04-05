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
        self.assertEqual(len(ifs), 3)
        self.assertIn("BondEthernet0", ifs)
        self.assertIn("BondEthernet1", ifs)
        self.assertIn("BondEthernet2", ifs)
        self.assertNotIn("BondEthernet-noexist", ifs)

    def test_get_mode(self):
        self.assertEqual('lacp', bondethernet.get_mode(self.cfg, "BondEthernet0"))
        self.assertEqual('xor', bondethernet.get_mode(self.cfg, "BondEthernet1"))

    def test_mode_to_int(self):
        self.assertEqual(1, bondethernet.mode_to_int("round-robin"))
        self.assertEqual(2, bondethernet.mode_to_int("active-backup"))
        self.assertEqual(3, bondethernet.mode_to_int("xor"))
        self.assertEqual(4, bondethernet.mode_to_int("broadcast"))
        self.assertEqual(5, bondethernet.mode_to_int("lacp"))
        self.assertEqual(-1, bondethernet.mode_to_int("not-exist"))

    def test_get_lb(self):
        self.assertEqual('l34', bondethernet.get_lb(self.cfg, "BondEthernet0"))
        self.assertEqual('l2', bondethernet.get_lb(self.cfg, "BondEthernet1"))
        self.assertIsNone(bondethernet.get_lb(self.cfg, "BondEthernet2"))

    def test_lb_to_int(self):
        self.assertEqual(0, bondethernet.lb_to_int("l2"))
        self.assertEqual(1, bondethernet.lb_to_int("l34"))
        self.assertEqual(2, bondethernet.lb_to_int("l23"))
        self.assertEqual(3, bondethernet.lb_to_int("round-robin"))
        self.assertEqual(4, bondethernet.lb_to_int("broadcast"))
        self.assertEqual(5, bondethernet.lb_to_int("active-backup"))
        self.assertEqual(-1, bondethernet.lb_to_int("not-exist"))

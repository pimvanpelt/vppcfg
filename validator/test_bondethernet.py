import unittest
import yaml
import validator.bondethernet as bondethernet

class TestBondEthernetMethods(unittest.TestCase):
    def setUp(self):
        with open("unittest/test_bondethernet.yaml", "r") as f:
            self.cfg = yaml.load(f, Loader = yaml.FullLoader)

    def test_members(self):
        self.assertTrue(bondethernet.is_bond_member(self.cfg, "GigabitEthernet1/0/0"))
        self.assertTrue(bondethernet.is_bond_member(self.cfg, "GigabitEthernet1/0/1"))
        self.assertFalse(bondethernet.is_bond_member(self.cfg, "GigabitEthernet2/0/0"))
        self.assertFalse(bondethernet.is_bond_member(self.cfg, "GigabitEthernet2/0/0.100"))

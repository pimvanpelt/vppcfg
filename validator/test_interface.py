import unittest
import yaml
import validator.interface as interface

class TestInterfaceMethods(unittest.TestCase):
    def setUp(self):
        with open("unittest/test_interface.yaml", "r") as f:
            self.cfg = yaml.load(f, Loader = yaml.FullLoader)

    def test_enumerators(self):
        ifs = interface.get_interfaces(self.cfg)
        self.assertEqual(len(ifs), 15)
        self.assertIn("GigabitEthernet1/0/1", ifs)
        self.assertIn("GigabitEthernet1/0/1.200", ifs)
        self.assertIn("GigabitEthernet1/0/1.204", ifs)

        ifs = interface.get_sub_interfaces(self.cfg)
        self.assertEqual(len(ifs), 10)
        self.assertNotIn("GigabitEthernet1/0/1", ifs)
        self.assertIn("GigabitEthernet1/0/1.200", ifs)
        self.assertIn("GigabitEthernet1/0/1.204", ifs)

        ifs = interface.get_qinx_interfaces(self.cfg)
        self.assertEqual(len(ifs), 3)
        self.assertNotIn("GigabitEthernet1/0/1.200", ifs)
        self.assertIn("GigabitEthernet1/0/1.204", ifs)

    def test_mtu(self):
        self.assertEqual(interface.get_mtu(self.cfg, "GigabitEthernet1/0/1"), 9216)
        self.assertEqual(interface.get_mtu(self.cfg, "GigabitEthernet1/0/1.200"), 9000)
        self.assertEqual(interface.get_mtu(self.cfg, "GigabitEthernet1/0/1.201"), 1500)

    def test_encapsulation(self):
        self.assertTrue(interface.valid_encapsulation(self.cfg, "GigabitEthernet1/0/1.200"))
        self.assertTrue(interface.unique_encapsulation(self.cfg, "GigabitEthernet1/0/1.200"))
        self.assertEqual(interface.get_encapsulation(self.cfg, "GigabitEthernet1/0/1.200"),
            { 'dot1q': 1000, 'dot1ad': 0, 'inner-dot1q': 0, 'exact-match': False })
        self.assertEqual(interface.get_encapsulation(self.cfg, "GigabitEthernet1/0/1.201"),
            { 'dot1q': 0, 'dot1ad': 1000, 'inner-dot1q': 0, 'exact-match': False })
        self.assertEqual(interface.get_encapsulation(self.cfg, "GigabitEthernet1/0/1.202"),
            { 'dot1q': 1000, 'dot1ad': 0, 'inner-dot1q': 1234, 'exact-match': False })
        self.assertEqual(interface.get_encapsulation(self.cfg, "GigabitEthernet1/0/1.203"),
            { 'dot1q': 0, 'dot1ad': 1000, 'inner-dot1q': 1000, 'exact-match': False })
        self.assertEqual(interface.get_encapsulation(self.cfg, "GigabitEthernet1/0/1.204"),
            { 'dot1q': 0, 'dot1ad': 1000, 'inner-dot1q': 1000, 'exact-match': True })

        self.assertFalse(interface.valid_encapsulation(self.cfg, "GigabitEthernet1/0/0.100"))
        self.assertFalse(interface.valid_encapsulation(self.cfg, "GigabitEthernet1/0/0.101"))

        self.assertFalse(interface.unique_encapsulation(self.cfg, "GigabitEthernet1/0/0.102"))
        self.assertFalse(interface.unique_encapsulation(self.cfg, "GigabitEthernet1/0/0.103"))

    def test_has_sub(self):
        self.assertTrue(interface.has_sub(self.cfg, "GigabitEthernet1/0/1"))
        self.assertFalse(interface.has_sub(self.cfg, "GigabitEthernet1/0/1.200"))
        self.assertFalse(interface.has_sub(self.cfg, "GigabitEthernet2/0/0"))
        self.assertFalse(interface.has_sub(self.cfg, "GigabitEthernet3/0/0"))

    def test_is_sub(self):
        self.assertFalse(interface.is_sub(self.cfg, "GigabitEthernet1/0/1"))
        self.assertTrue(interface.is_sub(self.cfg, "GigabitEthernet1/0/1.200"))

    def test_is_qinx(self):
        self.assertTrue(interface.is_qinx(self.cfg, "GigabitEthernet1/0/1.202"))
        self.assertTrue(interface.is_qinx(self.cfg, "GigabitEthernet1/0/1.203"))
        self.assertTrue(interface.is_qinx(self.cfg, "GigabitEthernet1/0/1.204"))

        self.assertFalse(interface.is_qinx(self.cfg, "GigabitEthernet1/0/1"))
        self.assertFalse(interface.is_qinx(self.cfg, "GigabitEthernet1/0/1.200"))
        self.assertFalse(interface.is_qinx(self.cfg, "GigabitEthernet1/0/1.201"))

    def test_lcp(self):
        self.assertIsNone(interface.get_lcp(self.cfg, "GigabitEthernet1/0/0"))
        self.assertIsNone(interface.get_lcp(self.cfg, "GigabitEthernet1/0/0.100"))

        self.assertEqual(interface.get_lcp(self.cfg, "GigabitEthernet1/0/1"), "e1")
        self.assertEqual(interface.get_lcp(self.cfg, "GigabitEthernet1/0/1.100"), "foo")

        self.assertEqual(interface.get_lcp(self.cfg, "GigabitEthernet1/0/1.200"), "e1.1000")
        self.assertEqual(interface.get_lcp(self.cfg, "GigabitEthernet1/0/1.201"), "e1.1000")

        ## TODO(pim) - sub 201-203 cannot have an LCP, their encap is not exact-match
        ## self.assertIsNone(interface.get_lcp(self.cfg, "GigabitEthernet1/0/1.200"))
        ## self.assertIsNone(interface.get_lcp(self.cfg, "GigabitEthernet1/0/1.201"))
        ## self.assertIsNone(interface.get_lcp(self.cfg, "GigabitEthernet1/0/1.202"))
        ## self.assertIsNone(interface.get_lcp(self.cfg, "GigabitEthernet1/0/1.203"))
        self.assertEqual(interface.get_lcp(self.cfg, "GigabitEthernet1/0/1.204"), "e1.1000.1000")

    def test_address(self):
        self.assertFalse(interface.has_address(self.cfg, "GigabitEthernet1/0/0"))
        self.assertFalse(interface.has_address(self.cfg, "GigabitEthernet1/0/0.100"))

        self.assertTrue(interface.has_address(self.cfg, "GigabitEthernet1/0/1"))
        self.assertTrue(interface.has_address(self.cfg, "GigabitEthernet1/0/1.100"))

    def test_lx2c(self):
        l2xc_ifs = interface.get_l2xc_interfaces(self.cfg)
        l2xc_target_ifs = interface.get_l2xc_target_interfaces(self.cfg)

        self.assertIn("GigabitEthernet3/0/0", l2xc_ifs)
        self.assertIn("GigabitEthernet3/0/0", l2xc_target_ifs)
        self.assertTrue(interface.is_l2xc_interface(self.cfg, "GigabitEthernet3/0/0"))
        self.assertTrue(interface.is_l2xc_target_interface(self.cfg, "GigabitEthernet3/0/0"))

        self.assertNotIn("GigabitEthernet2/0/0", l2xc_ifs)
        self.assertNotIn("GigabitEthernet2/0/0", l2xc_target_ifs)
        self.assertFalse(interface.is_l2xc_interface(self.cfg, "GigabitEthernet2/0/0"))
        self.assertFalse(interface.is_l2xc_target_interface(self.cfg, "GigabitEthernet2/0/0"))

    def test_l2(self):
        self.assertTrue(interface.is_l2(self.cfg, "GigabitEthernet3/0/0"))
        self.assertFalse(interface.is_l2(self.cfg, "GigabitEthernet1/0/0"))

    def test_l3(self):
        self.assertTrue(interface.is_l3(self.cfg, "GigabitEthernet1/0/0"))
        self.assertFalse(interface.is_l3(self.cfg, "GigabitEthernet3/0/0"))

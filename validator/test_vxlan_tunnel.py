import unittest
import yaml
import validator.vxlan_tunnel as vxlan_tunnel

class TestVXLANMethods(unittest.TestCase):
    def setUp(self):
        with open("unittest/test_vxlan_tunnel.yaml", "r") as f:
            self.cfg = yaml.load(f, Loader = yaml.FullLoader)

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

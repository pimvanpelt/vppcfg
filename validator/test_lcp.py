import unittest
import yaml
import validator.lcp as lcp
import validator.interface as interface

class TestLCPMethods(unittest.TestCase):
    def setUp(self):
        with open("unittest/test_lcp.yaml", "r") as f:
            self.cfg = yaml.load(f, Loader = yaml.FullLoader)

    def test_lcp(self):
        self.assertTrue(lcp.is_unique(self.cfg, "e1"))
        self.assertTrue(lcp.is_unique(self.cfg, "foo"))

        ## TODO(pim) - ensure that is_unique also takes synthesized LCPs into account
        ## self.assertFalse(lcp.is_unique(self.cfg, "e1.1000"))

    def test_qinx(self):
        qint_ifname, qinq_iface = interface.get_by_name(self.cfg, "GigabitEthernet1/0/1.201")
        mid_ifname, mid_iface = interface.get_qinx_parent_by_name(self.cfg, "GigabitEthernet1/0/1.201")
        parent_ifname, parent_iface = interface.get_parent_by_name(self.cfg, "GigabitEthernet1/0/1.201")

        # TODO(pim) - complete once get_*_by_name() returns a dict
        # print("qinq", qinq_iface)
        # print("mid", mid_iface)
        # print("parent", parent_iface)

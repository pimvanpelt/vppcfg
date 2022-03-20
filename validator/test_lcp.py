import unittest
import yaml
import validator.lcp as lcp

class TestInterfaceMethods(unittest.TestCase):
    def setUp(self):
        with open("unittest/TestInterfaceMethods.yaml", "r") as f:
            self.cfg = yaml.load(f, Loader = yaml.FullLoader)

    def test_lcp(self):
        self.assertTrue(lcp.is_unique(self.cfg, "e1"))
        self.assertTrue(lcp.is_unique(self.cfg, "foo"))

        ## TODO(pim) - ensure that is_unique also takes synthesized LCPs into account
        ## self.assertFalse(lcp.is_unique(self.cfg, "e1.1000"))

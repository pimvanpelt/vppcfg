import unittest
import config.mac as mac

class TestMACMethods(unittest.TestCase):
    def test_is_valid(self):
        self.assertTrue(mac.is_valid("00:01:02:03:04:05"))
        self.assertTrue(mac.is_valid("00-01-02-03-04-05"))
        self.assertTrue(mac.is_valid("0001.0203.0405"))
        self.assertFalse(mac.is_valid("hoi"))

    def test_is_local(self):
        self.assertTrue(mac.is_local("02:00:00:00:00:00"))
        self.assertFalse(mac.is_local("00:00:00:00:00:00"))

    def test_is_multicast(self):
        self.assertTrue(mac.is_multicast("01:00:00:00:00:00"))
        self.assertFalse(mac.is_multicast("00:00:00:00:00:00"))

    def test_is_unicast(self):
        self.assertFalse(mac.is_unicast("01:00:00:00:00:00"))
        self.assertTrue(mac.is_unicast("00:00:00:00:00:00"))

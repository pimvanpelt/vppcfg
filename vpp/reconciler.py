#!/usr/bin/env python
#
# Copyright (c) 2022 Pim van Pelt
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at:
#     http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# -*- coding: utf-8 -*-
import logging
import config.interface as interface
import config.bondethernet as bondethernet
import config.vxlan_tunnel as vxlan_tunnel
import config.lcp as lcp
from vpp.vppapi import VPPApi

class Reconciler():
    def __init__(self, cfg):
        self.logger = logging.getLogger('vppcfg.vppapi')
        self.logger.addHandler(logging.NullHandler())

        self.vpp = VPPApi()
        self.cfg = cfg

    def readconfig(self):
        return self.vpp.readconfig()

    def phys_exist(self, ifname_list):
        """ Return True if all interfaces in the `ifname_list` exist as physical interface names
        in VPP. Return False otherwise."""
        ret = True
        for ifname in ifname_list:
            if not ifname in self.vpp.config['interface_names']:
                self.logger.warning("Interface %s does not exist in VPP" % ifname)
                ret = False
        return ret

    def prune_addresses(self, ifname, address_list):
        """ Remove all addresses from interface ifname, except those in address_list """
        idx = self.vpp.config['interface_names'][ifname].sw_if_index
        for a in self.vpp.config['interface_addresses'][idx]:
            self.logger.info("> set interface ip address del %s %s" % (ifname, a))
        
    def prune(self):
        ret = True
        if not self.prune_addresses_set_interface_down():
            self.logger.warning("Could not prune addresses and set interfaces down from VPP that are not in the config")
            ret = False
        return ret

    def prune_addresses_set_interface_down(self):
        for ifname in self.vpp.get_qinx_interfaces() + self.vpp.get_dot1x_interfaces() + self.vpp.get_bondethernets() + self.vpp.get_vxlan_tunnels() + self.vpp.get_phys():
            if not ifname in interface.get_interfaces(self.cfg):
                self.logger.info("> set interface state %s down" % ifname)
                self.prune_addresses(ifname, [])

        return True

    def create(self):
        return False

    def sync(self):
        return False

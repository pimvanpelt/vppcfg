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
from vpp.vppapi import VPPApi

class Reconciler():
    def __init__(self, cfg):
        self.logger = logging.getLogger('vppcfg.vppapi')
        self.logger.addHandler(logging.NullHandler())

        self.vpp = VPPApi()

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
        
    def prune(self):
        return False

    def create(self):
        return False

    def sync(self):
        return False

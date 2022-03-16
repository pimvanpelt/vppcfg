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
import logging
import validator.interface as interface
import ipaddress

class NullHandler(logging.Handler):
    def emit(self, record):
        pass


def get_by_name(yaml, ifname):
    """ Return the VXLAN by name, if it exists. Return None otherwise. """
    try:
        if ifname in yaml['vxlan_tunnels']:
            return yaml['vxlan_tunnels'][ifname]
    except:
        pass
    return None

def vni_unique(yaml, vni):
    """ Return True if the VNI is unique amongst all VXLANs """
    if not 'vxlan_tunnels' in yaml:
        return True

    ncount = 0
    for ifname, iface in yaml['vxlan_tunnels'].items():
        if iface['vni'] == vni:
            ncount = ncount + 1

    return ncount < 2


def validate_vxlan_tunnels(yaml):
    result = True
    msgs = []
    logger = logging.getLogger('vppcfg.validator')
    logger.addHandler(NullHandler())

    if not 'vxlan_tunnels' in yaml:
        return result, msgs

    for ifname, iface in yaml['vxlan_tunnels'].items():
        logger.debug("vxlan_tunnel %s: %s" % (ifname, iface))
        vni = iface['vni']
        if not vni_unique(yaml, vni):
            msgs.append("vxlan_tunnel %s VNI %d is not unique" % (ifname, vni))
            result = False
        local = ipaddress.ip_address(iface['local'])
        remote = ipaddress.ip_address(iface['remote'])
        if local.version != remote.version:
            msgs.append("vxlan_tunnel %s local and remote are not the same address family" % (ifname))
            result = False

    return result, msgs

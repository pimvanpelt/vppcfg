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
import config.interface as interface
import ipaddress

def get_by_name(yaml, ifname):
    """ Return the VXLAN by name, if it exists. Return None otherwise. """
    try:
        if ifname in yaml['vxlan_tunnels']:
            return ifname, yaml['vxlan_tunnels'][ifname]
    except:
        pass
    return None, None


def is_vxlan_tunnel(yaml, ifname):
    """ Returns True if the interface name is an existing VXLAN Tunnel. """
    ifname, iface = get_by_name(yaml, ifname)
    return not iface == None


def vni_unique(yaml, vni):
    """ Return True if the VNI is unique amongst all VXLANs """
    if not 'vxlan_tunnels' in yaml:
        return True

    ncount = 0
    for ifname, iface in yaml['vxlan_tunnels'].items():
        if iface['vni'] == vni:
            ncount = ncount + 1

    return ncount < 2


def get_vxlan_tunnels(yaml):
    """ Returns a list of all VXLAN tunnel interface names. """
    ret = []
    if not 'vxlan_tunnels' in yaml:
        return ret

    for ifname, iface in yaml['vxlan_tunnels'].items():
        ret.append(ifname)
    return ret


def validate_vxlan_tunnels(yaml):
    result = True
    msgs = []
    logger = logging.getLogger('vppcfg.config')
    logger.addHandler(logging.NullHandler())

    if not 'vxlan_tunnels' in yaml:
        return result, msgs

    for ifname, iface in yaml['vxlan_tunnels'].items():
        logger.debug(f"vxlan_tunnel {ifname}: {iface}")
        instance = int(ifname[12:])
        if instance > 2147483647:
            msgs.append(f"vxlan_tunnel {ifname} has instance {int(instance)} which is too large")
            result = False

        vni = iface['vni']
        if not vni_unique(yaml, vni):
            msgs.append(f"vxlan_tunnel {ifname} VNI {int(vni)} is not unique")
            result = False
        local = ipaddress.ip_address(iface['local'])
        remote = ipaddress.ip_address(iface['remote'])
        if local.version != remote.version:
            msgs.append(f"vxlan_tunnel {ifname} local and remote are not the same address family")
            result = False

    return result, msgs

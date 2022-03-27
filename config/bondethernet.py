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

def get_bondethernets(yaml):
    """ Return a list of all bondethernets. """
    ret = []
    if 'bondethernets' in yaml:
        for ifname, iface in yaml['bondethernets'].items():
            ret.append(ifname)
    return ret


def get_by_name(yaml, ifname):
    """ Return the BondEthernet by name, if it exists. Return None,None otherwise. """
    try:
        if ifname in yaml['bondethernets']:
            return ifname, yaml['bondethernets'][ifname]
    except:
        pass
    return None, None


def is_bondethernet(yaml, ifname):
    """ Returns True if the interface name is an existing BondEthernet. """
    ifname, iface = get_by_name(yaml, ifname)
    return not iface == None


def is_bond_member(yaml, ifname):
    """ Returns True if this interface is a member of a BondEthernet. """
    if not 'bondethernets' in yaml:
        return False

    for bond, iface in yaml['bondethernets'].items():
        if not 'interfaces' in iface:
            continue
        if ifname in iface['interfaces']:
            return True
    return False


def validate_bondethernets(yaml):
    result = True
    msgs = []
    logger = logging.getLogger('vppcfg.config')
    logger.addHandler(logging.NullHandler())

    if not 'bondethernets' in yaml:
        return result, msgs

    for ifname, iface in yaml['bondethernets'].items():
        logger.debug("bondethernet %s: %s" % (ifname, iface))
        bond_ifname, bond_iface = interface.get_by_name(yaml, ifname)
        bond_mtu = 1500
        if not bond_iface:
            msgs.append("bondethernet %s does not exist in interfaces" % (ifname))
            result = False
        else:
            bond_mtu = interface.get_mtu(yaml, bond_ifname)

        for member in iface['interfaces']:
            if (None, None) == interface.get_by_name(yaml, member):
                msgs.append("bondethernet %s member %s does not exist" % (ifname, member))
                result = False
                continue

            if interface.has_sub(yaml, member):
                msgs.append("bondethernet %s member %s has sub-interface(s)" % (ifname, member))
                result = False
            if interface.has_lcp(yaml, member):
                msgs.append("bondethernet %s member %s has an LCP" % (ifname, member))
                result = False
            if interface.has_address(yaml, member):
                msgs.append("bondethernet %s member %s has an address" % (ifname, member))
                result = False
            member_mtu = interface.get_mtu(yaml, member)
            if  member_mtu != bond_mtu:
                msgs.append("bondethernet %s member %s MTU %d does not match BondEthernet MTU %d" % (ifname, member, member_mtu, bond_mtu))
                result = False
    return result, msgs

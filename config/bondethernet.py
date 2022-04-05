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


def get_mode(yaml, ifname):
    """ Return the mode of the BondEthernet as a string, defaulting to 'lacp'
        if no mode is given. Return None if the bond interface doesn't exist.

        Return values: 'round-robin','active-backup','broadcast','lacp','xor'
        """
    ifname, iface = get_by_name(yaml, ifname)
    if not iface:
        return None

    if not 'mode' in iface:
        return 'lacp'
    return iface['mode']


def mode_to_int(mode):
    """ Returns the integer representation in VPP of a given bondethernet mode,
        or -1 if 'mode' is not a valid string.

        See src/vnet/bonding/bond.api and schema.yaml for valid pairs. """

    ret = { 'round-robin': 1, 'active-backup': 2, 'xor': 3, 'broadcast': 4, 'lacp': 5 }
    try:
        return ret[mode]
    except:
        pass
    return -1


def int_to_mode(mode):
    """ Returns the string representation in VPP of a given bondethernet mode,
        or "" if 'mode' is not a valid id.

        See src/vnet/bonding/bond.api and schema.yaml for valid pairs. """

    ret = { 1: 'round-robin', 2: 'active-backup', 3: 'xor', 4: 'broadcast', 5: 'lacp' }
    try:
        return ret[mode]
    except:
        pass
    return ""


def get_lb(yaml, ifname):
    """ Return the loadbalance strategy of the BondEthernet as a string. Only
        'xor' and 'lacp' modes have loadbalance strategies, so return None if
        those modes are not used.

        Return values: 'l2', 'l23', 'l34', with 'l34' being the default if
        the bond is in xor/lacp mode without a load-balance strategy set
        explicitly."""
    ifname, iface = get_by_name(yaml, ifname)
    if not iface:
        return None
    mode = get_mode(yaml, ifname)
    if not mode in ['xor','lacp']:
        return None

    if not 'load-balance' in iface:
        return 'l34'
    return iface['load-balance']


def lb_to_int(lb):
    """ Returns the integer representation in VPP of a given load-balance strategy,
        or -1 if 'lb' is not a valid string.

        See src/vnet/bonding/bond.api and schema.yaml for valid pairs, although
        bond.api defined more than we use in vppcfg. """

    ret = { 'l2': 0, 'l34': 1, 'l23': 2, 'round-robin': 3, 'broadcast': 4, 'active-backup': 5 }
    try:
        return ret[lb]
    except:
        pass
    return -1


def int_to_lb(lb):
    """ Returns the string representation in VPP of a given load-balance strategy,
        or "" if 'lb' is not a valid int.

        See src/vnet/bonding/bond.api and schema.yaml for valid pairs, although
        bond.api defined more than we use in vppcfg. """

    ret = { 0: 'l2', 1: 'l34', 2: 'l23', 3: 'round-robin', 4: 'broadcast', 5: 'active-backup' }
    try:
        return ret[lb]
    except:
        pass
    return ""


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
        instance = int(ifname[12:])
        if instance > 4294967294:
            msgs.append("bondethernet %s has instance %d which is too large" % (ifname, instance))
            result = False
        if not get_mode(yaml, bond_ifname) in ['xor','lacp'] and 'load-balance' in iface:
            msgs.append("bondethernet %s can only have load-balance if in mode XOR or LACP" % (ifname))
            result = False

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

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
import config.loopback as loopback
import config.lcp as lcp
import config.address as address


def get_bridgedomains(yaml):
    """ Return a list of all bridgedomains. """
    ret = []
    if not 'bridgedomains' in yaml:
        return ret
    for ifname, iface in yaml['bridgedomains'].items():
        ret.append(ifname)
    return ret


def get_by_name(yaml, ifname):
    """ Return the BridgeDomain by name (bd*), if it exists. Return None,None otherwise. """
    try:
        if ifname in yaml['bridgedomains']:
            return ifname, yaml['bridgedomains'][ifname]
    except:
        pass
    return None, None


def is_bridgedomain(yaml, ifname):
    """ Returns True if the name (bd*) is an existing bridgedomain. """
    ifname, iface = get_by_name(yaml, ifname)
    return not iface == None


def get_bridge_interfaces(yaml):
    """ Returns a list of all interfaces that are bridgedomain members """

    ret = []
    if not 'bridgedomains' in yaml:
        return ret

    for ifname, iface in yaml['bridgedomains'].items():
        if 'interfaces' in iface:
            ret.extend(iface['interfaces'])

    return ret

def is_bridge_interface_unique(yaml, ifname):
    """ Returns True if this interface is referenced in bridgedomains zero or one times """

    ifs = get_bridge_interfaces(yaml)
    return ifs.count(ifname) < 2


def is_bridge_interface(yaml, ifname):
    """ Returns True if this interface is a member of a BridgeDomain """

    return ifname in get_bridge_interfaces(yaml)


def bvi_unique(yaml, bviname):
    """ Returns True if the BVI identified by bviname is unique among all BridgeDomains. """
    if not 'bridgedomains' in yaml:
        return True
    n = 0
    for ifname, iface in yaml['bridgedomains'].items():
        if 'bvi' in iface and iface['bvi'] == bviname:
            n += 1
    return n<2


def validate_bridgedomains(yaml):
    result = True
    msgs = []
    logger = logging.getLogger('vppcfg.config')
    logger.addHandler(logging.NullHandler())

    if not 'bridgedomains' in yaml:
        return result, msgs

    for ifname, iface in yaml['bridgedomains'].items():
        logger.debug("bridgedomain %s" % iface)
        bd_mtu = 1500
        if 'mtu' in iface:
            bd_mtu = iface['mtu']
        instance = int(ifname[2:])
        if instance == 0:
            msgs.append("bridgedomain %s is reserved" % ifname)
            result = False
        elif instance > 16777215:
            msgs.append("bridgedomain %s has instance %d which is too large" % (ifname, instance))
            result = False

        if 'bvi' in iface:
            bviname = iface['bvi']
            if (None,None) == loopback.get_by_name(yaml, bviname):
                msgs.append("bridgedomain %s BVI %s does not exist" % (ifname, bviname))
                result = False
            if not bvi_unique(yaml, bviname):
                msgs.append("bridgedomain %s BVI %s is not unique" % (ifname, bviname))
                result = False

        if 'interfaces' in iface:
            for member in iface['interfaces']:
                if (None, None) == interface.get_by_name(yaml, member):
                    msgs.append("bridgedomain %s member %s does not exist" % (ifname, member))
                    result = False
                    continue

                if not is_bridge_interface_unique(yaml, member):
                    msgs.append("bridgedomain %s member %s is not unique" % (ifname, member))
                    result = False
                if interface.has_lcp(yaml, member):
                    msgs.append("bridgedomain %s member %s has an LCP" % (ifname, member))
                    result = False
                if interface.has_address(yaml, member):
                    msgs.append("bridgedomain %s member %s has an address" % (ifname, member))
                    result = False
                member_mtu = interface.get_mtu(yaml, member)
                if member_mtu != bd_mtu:
                    msgs.append("bridgedomain %s member %s has MTU %d, while bridge has %d" % (ifname, member, member_mtu, bd_mtu))
                    result = False


    return result, msgs

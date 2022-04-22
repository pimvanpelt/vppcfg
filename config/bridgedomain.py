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


def get_settings(yaml, ifname):
    ifname, iface = get_by_name(yaml, ifname)
    if not iface:
        return None

    settings = {
        'learn': True,
        'unicast-flood': True,
        'unknown-unicast-flood': True,
        'unicast-forward': True,
        'arp-termination': False,
        'arp-unicast-forward': False,
        'mac-age-minutes': 0,          ## 0 means disabled
        }
    if 'settings' in iface:
        if 'learn' in iface['settings']:
            settings['learn'] = iface['settings']['learn']
        if 'unicast-flood' in iface['settings']:
            settings['unicast-flood'] = iface['settings']['unicast-flood']
        if 'unknown-unicast-flood' in iface['settings']:
            settings['unknown-unicast-flood'] = iface['settings']['unknown-unicast-flood']
        if 'unicast-forward' in iface['settings']:
            settings['unicast-forward'] = iface['settings']['unicast-forward']
        if 'arp-termination' in iface['settings']:
            settings['arp-termination'] = iface['settings']['arp-termination']
        if 'arp-unicast-forward' in iface['settings']:
            settings['arp-unicast-forward'] = iface['settings']['arp-unicast-forward']
        if 'mac-age-minutes' in iface['settings']:
            settings['mac-age-minutes'] = int(iface['settings']['mac-age-minutes'])
    return settings


def validate_bridgedomains(yaml):
    result = True
    msgs = []
    logger = logging.getLogger('vppcfg.config')
    logger.addHandler(logging.NullHandler())

    if not 'bridgedomains' in yaml:
        return result, msgs

    for ifname, iface in yaml['bridgedomains'].items():
        logger.debug(f"bridgedomain {iface}")
        bd_mtu = 1500
        if 'mtu' in iface:
            bd_mtu = iface['mtu']
        instance = int(ifname[2:])
        if instance == 0:
            msgs.append(f"bridgedomain {ifname} is reserved")
            result = False
        elif instance > 16777215:
            msgs.append(f"bridgedomain {ifname} has instance {int(instance)} which is too large")
            result = False

        if 'bvi' in iface:
            bviname = iface['bvi']
            bvi_ifname, bvi_iface = loopback.get_by_name(yaml,iface['bvi'])
            if not bvi_unique(yaml, bvi_ifname):
                msgs.append(f"bridgedomain {ifname} BVI {bvi_ifname} is not unique")
                result = False
            if not bvi_iface:
                msgs.append(f"bridgedomain {ifname} BVI {bvi_ifname} does not exist")
                result = False
                continue

            bvi_mtu = 1500
            if 'mtu' in bvi_iface:
                bvi_mtu = bvi_iface['mtu']
            if bvi_mtu != bd_mtu:
                msgs.append(f"bridgedomain {ifname} BVI {bvi_ifname} has MTU {int(bvi_mtu)}, while bridge has {int(bd_mtu)}")
                result = False

        if 'interfaces' in iface:
            for member in iface['interfaces']:
                if (None, None) == interface.get_by_name(yaml, member):
                    msgs.append(f"bridgedomain {ifname} member {member} does not exist")
                    result = False
                    continue

                if not is_bridge_interface_unique(yaml, member):
                    msgs.append(f"bridgedomain {ifname} member {member} is not unique")
                    result = False
                if interface.has_lcp(yaml, member):
                    msgs.append(f"bridgedomain {ifname} member {member} has an LCP")
                    result = False
                if interface.has_address(yaml, member):
                    msgs.append(f"bridgedomain {ifname} member {member} has an address")
                    result = False
                member_mtu = interface.get_mtu(yaml, member)
                if member_mtu != bd_mtu:
                    msgs.append(f"bridgedomain {ifname} member {member} has MTU {int(member_mtu)}, while bridge has {int(bd_mtu)}")
                    result = False


    return result, msgs

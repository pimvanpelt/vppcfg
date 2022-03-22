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
import validator.lcp as lcp
import validator.address as address

class NullHandler(logging.Handler):
    def emit(self, record):
        pass


def get_bridgedomains(yaml):
    """ Return a list of all bridgedomains. """
    ret = []
    if not 'bridgedomains' in yaml:
        return ret
    for ifname, iface in yaml['bridgedomains'].items():
        ret.append(ifname)
    return ret


def get_by_name(yaml, ifname):
    """ Return the BridgeDomain by name, if it exists. Return None,None otherwise. """
    try:
        if ifname in yaml['bridgedomains']:
            return ifname, yaml['bridgedomains'][ifname]
    except:
        pass
    return None, None


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


def validate_bridgedomains(yaml):
    result = True
    msgs = []
    logger = logging.getLogger('vppcfg.validator')
    logger.addHandler(NullHandler())

    if not 'bridgedomains' in yaml:
        return result, msgs

    for ifname, iface in yaml['bridgedomains'].items():
        logger.debug("bridgedomain %s" % iface)
        bd_mtu = 1500
        if 'mtu' in iface:
            bd_mtu = iface['mtu']

        if 'addresses' in iface and not 'lcp' in iface:
            msgs.append("bridgedomain %s has an address but no LCP" % ifname)
            result = False
        if 'lcp' in iface and not lcp.is_unique(yaml, iface['lcp']):
            msgs.append("bridgedomain %s does not have a unique LCP name %s" % (ifname, iface['lcp']))
            result = False          
        if 'addresses' in iface:
            for a in iface['addresses']:
                if not address.is_allowed(yaml, ifname, iface['addresses'], a):
                    msgs.append("bridgedomain %s IP address %s conflicts with another" % (ifname, a))
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

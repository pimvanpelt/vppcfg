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
import config.mac as mac

def get_taps(yaml):
    """ Return a list of all taps. """
    ret = []
    if 'taps' in yaml:
        for ifname, iface in yaml['taps'].items():
            ret.append(ifname)
    return ret


def get_by_name(yaml, ifname):
    """ Return the tap by name, if it exists. Return None otherwise. """
    try:
        if ifname in yaml['taps']:
            return ifname, yaml['taps'][ifname]
    except:
        pass
    return None, None


def is_tap(yaml, ifname):
    """ Returns True if the interface name is an existing tap in the config.
        The TAP has to be explicitly named in the configuration, and notably
        a TAP belonging to a Linux Control Plane (LCP) will return False.
    """
    ifname, iface = get_by_name(yaml, ifname)
    return not iface == None


def is_host_name_unique(yaml, hostname):
    """ Returns True if there is at most one occurence of the given ifname amonst all host-names of TAPs. """
    if not 'taps' in yaml:
        return True
    host_names = []
    for tap_ifname, tap_iface in yaml['taps'].items():
        host_names.append(tap_iface['host']['name'])
    return host_names.count(hostname) < 2


def validate_taps(yaml):
    result = True
    msgs = []
    logger = logging.getLogger('vppcfg.config')
    logger.addHandler(logging.NullHandler())

    if not 'taps' in yaml:
        return result, msgs

    for ifname, iface in yaml['taps'].items():
        logger.debug("tap %s" % iface)
        instance = int(ifname[3:])

        ## NOTE(pim): 1024 is not off-by-one, tap1024 is precisely the highest permissible id
        if instance > 1024:
            msgs.append("tap %s has instance %d which is too large" % (ifname, instance))
            result = False

        if not is_host_name_unique(yaml, iface['host']['name']):
            msgs.append("tap %s does not have a unique host name %s" % (ifname, iface['host']['name']))
            result = False

        if 'rx-ring-size' in iface:
            n = iface['rx-ring-size']
            if n & (n-1) != 0:
                msgs.append("tap %s rx-ring-size must be a power of two" % (ifname))
                result = False

        if 'tx-ring-size' in iface:
            n = iface['tx-ring-size']
            if n & (n-1) != 0:
                msgs.append("tap %s tx-ring-size must be a power of two" % (ifname))
                result = False

        if 'namespace-create' in iface['host'] and iface['host']['namespace-create'] and not 'namespace' in iface['host']:
            msgs.append("tap %s namespace-create can only be set if namespace is set" % (ifname))
            result = False

        if 'bridge-create' in iface['host'] and iface['host']['bridge-create'] and not 'bridge' in iface['host']:
            msgs.append("tap %s bridge-create can only be set if bridge is set" % (ifname))
            result = False

        if 'mac' in iface['host'] and mac.is_multicast(iface['host']['mac']):
            msgs.append("tap %s host MAC address %s cannot be multicast" % (ifname, iface['host']['mac']))
            result = False

    return result, msgs

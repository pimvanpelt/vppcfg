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
from config import lcp
from config import address
from config import mac


def get_loopbacks(yaml):
    """Return a list of all loopbacks."""
    ret = []
    if "loopbacks" in yaml:
        for ifname, _iface in yaml["loopbacks"].items():
            ret.append(ifname)
    return ret


def get_by_lcp_name(yaml, lcpname):
    """Returns the loopback by a given lcp name, or None,None if it does not exist"""
    if not "loopbacks" in yaml:
        return None, None
    for ifname, iface in yaml["loopbacks"].items():
        if "lcp" in iface and iface["lcp"] == lcpname:
            return ifname, iface
    return None, None


def get_by_name(yaml, ifname):
    """Return the loopback by name, if it exists. Return None otherwise."""
    try:
        if ifname in yaml["loopbacks"]:
            return ifname, yaml["loopbacks"][ifname]
    except KeyError:
        pass
    return None, None


def is_loopback(yaml, ifname):
    """Returns True if the interface name is an existing loopback."""
    ifname, iface = get_by_name(yaml, ifname)
    return iface is not None


def validate_loopbacks(yaml):
    result = True
    msgs = []
    logger = logging.getLogger("vppcfg.config")
    logger.addHandler(logging.NullHandler())

    if not "loopbacks" in yaml:
        return result, msgs

    for ifname, iface in yaml["loopbacks"].items():
        logger.debug(f"loopback {iface}")
        instance = int(ifname[4:])
        if instance > 4095:
            msgs.append(
                f"loopback {ifname} has instance {int(instance)} which is too large"
            )
            result = False
        if "lcp" in iface and not lcp.is_unique(yaml, iface["lcp"]):
            msgs.append(
                f"loopback {ifname} does not have a unique LCP name {iface['lcp']}"
            )
            result = False
        if "addresses" in iface:
            for addr in iface["addresses"]:
                if not address.is_allowed(yaml, ifname, iface["addresses"], addr):
                    msgs.append(
                        f"loopback {ifname} IP address {addr} conflicts with another"
                    )
                    result = False
        if "mac" in iface and mac.is_multicast(iface["mac"]):
            msgs.append(
                f"loopback {ifname} MAC address {iface['mac']} cannot be multicast"
            )
            result = False

    return result, msgs

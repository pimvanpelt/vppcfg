#
# Copyright (c) 2023 Pim van Pelt
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
""" A vppcfg configuration module that validates prefixlists """
import logging
import socket
import ipaddress


def get_prefixlists(yaml):
    """Return a list of all prefixlists."""
    ret = []
    if "prefixlists" in yaml:
        for plname, _pl in yaml["prefixlists"].items():
            ret.append(plname)
    return ret


def get_by_name(yaml, plname):
    """Return the prefixlist by name, if it exists. Return None otherwise."""
    try:
        if plname in yaml["prefixlists"]:
            return plname, yaml["prefixlists"][plname]
    except KeyError:
        pass
    return None, None


def get_network_list(yaml, plname, want_ipv4=True, want_ipv6=True):
    """Returns a list of 0 or more ip_network elements, that represent the members
    in a prefixlist of given name. Return the empty list if the prefixlist doesn't
    exist. Optionally, want_ipv4 or want_ipv6 can be set to False to filter the list."""
    ret = []
    plname, pl = get_by_name(yaml, plname)
    if not pl:
        return ret
    for m in pl["members"]:
        ipn = ipaddress.ip_network(m, strict=False)
        if ipn.version == 4 and want_ipv4:
            ret.append(ipn)
        if ipn.version == 6 and want_ipv6:
            ret.append(ipn)
    return ret


def count(yaml, plname):
    """Return the number of IPv4 and IPv6 entries in the prefixlist.
    Returns 0, 0 if it doesn't exist"""
    v4, v6 = 0, 0

    plname, pl = get_by_name(yaml, plname)
    if not pl:
        return 0, 0
    for m in pl["members"]:
        ipn = ipaddress.ip_network(m, strict=False)
        if ipn.version == 4:
            v4 += 1
        elif ipn.version == 6:
            v6 += 1

    return v4, v6


def count_ipv4(yaml, plname):
    """Return the number of IPv4 entries in the prefixlist."""
    v4, v6 = count(yaml, plname)
    return v4


def count_ipv6(yaml, plname):
    """Return the number of IPv6 entries in the prefixlist."""
    v4, v6 = count(yaml, plname)
    return v6


def has_ipv4(yaml, plname):
    """Return True if the prefixlist has at least one IPv4 entry."""
    v4, v6 = count(yaml, plname)
    return v4 > 0


def has_ipv6(yaml, plname):
    """Return True if the prefixlist has at least one IPv6 entry."""
    v4, v6 = count(yaml, plname)
    return v6 > 0


def is_empty(yaml, plname):
    """Return True if the prefixlist has no entries."""
    v4, v6 = count(yaml, plname)
    return v4 + v6 == 0


def validate_prefixlists(yaml):
    """Validate the semantics of all YAML 'prefixlists' entries"""
    result = True
    msgs = []
    logger = logging.getLogger("vppcfg.config")
    logger.addHandler(logging.NullHandler())

    if not "prefixlists" in yaml:
        return result, msgs

    for plname, pl in yaml["prefixlists"].items():
        logger.debug(f"prefixlist {plname}: {pl}")
        members = 0
        for pl_member in pl["members"]:
            members += 1
            logger.debug(f"prefixlist {plname} member {members} is {pl_member}")

    return result, msgs

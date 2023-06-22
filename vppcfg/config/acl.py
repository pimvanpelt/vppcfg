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
""" A vppcfg configuration module that validates acls """
import logging
import socket
import ipaddress
from . import prefixlist


def get_acls(yaml):
    """Return a list of all acls."""
    ret = []
    if "acls" in yaml:
        for aclname, _acl in yaml["acls"].items():
            ret.append(aclname)
    return ret


def get_by_name(yaml, aclname):
    """Return the acl by name, if it exists. Return None otherwise."""
    try:
        if aclname in yaml["acls"]:
            return aclname, yaml["acls"][aclname]
    except KeyError:
        pass
    return None, None


def hydrate_term(acl_term):
    """Adds all defaults to an ACL term"""

    if "family" not in acl_term:
        acl_term["family"] = "any"
    if "source" not in acl_term:
        acl_term["source"] = "any"
    if "destination" not in acl_term:
        acl_term["destination"] = "any"

    if "protocol" not in acl_term or acl_term["protocol"] == "any":
        acl_term["protocol"] = 0

    if "source-port" not in acl_term:
        acl_term["source-port"] = "any"
    if "destination-port" not in acl_term:
        acl_term["destination-port"] = "any"
    if "icmp-code" not in acl_term:
        acl_term["icmp-code"] = "any"
    if "icmp-type" not in acl_term:
        acl_term["icmp-type"] = "any"

    return acl_term


def get_icmp_low_high(icmpstring):
    """For a given icmp string, which can be either an integer or a range of
    integers including start/stop being omitted, eg 0-255, 10- or -10, or the
    string "any", return a tuple of (lowport, highport) or (None, None) upon
    error"""
    if isinstance(icmpstring, int):
        return int(icmpstring), int(icmpstring)
    if "any" == icmpstring:
        return 0, 255

    try:
        icmp = int(icmpstring)
        if icmp > 0:
            return icmp, icmp
    except:
        pass

    if icmpstring.startswith("-"):
        icmp = int(icmpstring[1:])
        return 0, icmp

    if icmpstring.endswith("-"):
        icmp = int(icmpstring[:-1])
        return icmp, 255

    try:
        icmps = icmpstring.split("-")
        return int(icmps[0]), int(icmps[1])
    except:
        pass

    return None, None


def get_port_low_high(portstring):
    """For a given port string, which can be either an integer, a symbolic port name
    in /etc/services, a range of integers including start/stop being omitted, eg
    0-65535, 1024- or -1024, or the string "any", return a tuple of
    (lowport, highport) or (None, None) upon error"""
    if isinstance(portstring, int):
        return int(portstring), int(portstring)
    if "any" == portstring:
        return 0, 65535

    try:
        port = int(portstring)
        if port > 0:
            return port, port
    except:
        pass

    try:
        port = socket.getservbyname(portstring)
        return port, port
    except:
        pass

    if portstring.startswith("-"):
        port = int(portstring[1:])
        return 0, port

    if portstring.endswith("-"):
        port = int(portstring[:-1])
        return port, 65535

    try:
        ports = portstring.split("-")
        return int(ports[0]), int(ports[1])
    except:
        pass

    return None, None


def is_ip(ip_string):
    """Return True if the given ip_string is either an IPv4/IPv6 address or prefix."""
    if not isinstance(ip_string, str):
        return False

    try:
        ipn = ipaddress.ip_network(ip_string, strict=False)
        return True
    except:
        pass
    return False


def get_network_list(yaml, network_string, want_ipv4=True, want_ipv6=True):
    """Return the full list of source or destination address(es). This function resolves the
    'source' or 'destination' field, which can either be an IP address, a Prefix, or the name
    of a Prefix List. It returns a list of ip_network() objects, including prefix. IP addresses
    will receive prefixlen /32 or /128. Optionally, want_ipv4 or want_ipv6 can be set to False
    to filter the list."""

    ret = []
    if is_ip(network_string):
        ipn = ipaddress.ip_network(network_string, strict=False)
        if ipn.version == 4 and want_ipv4:
            ret = [ipn]
        if ipn.version == 6 and want_ipv6:
            ret = [ipn]
        return ret

    if network_string == "any":
        if want_ipv4:
            ret.append(ipaddress.ip_network("0.0.0.0/0"))
        if want_ipv6:
            ret.append(ipaddress.ip_network("::/0"))
        return ret

    return prefixlist.get_network_list(
        yaml, network_string, want_ipv4=want_ipv4, want_ipv6=want_ipv6
    )


def get_protocol(protostring):
    """For a given protocol string, which can be either an integer or a symbolic port
    name in /etc/protocols, return the protocol number as integer, or None if it cannot
    be determined."""
    if isinstance(protostring, int):
        return int(protostring)
    if "any" == protostring:
        return 0

    try:
        proto = int(protostring)
        if proto > 0:
            return proto
    except:
        pass

    try:
        proto = socket.getprotobyname(protostring)
        return proto
    except:
        pass

    return None


def network_list_has_family(network_list, version):
    """Returns True if the given list of ip_network() elements has at least one
    element with the specified version, which can be either 4 or 6. Return False
    otherwise"""
    for m in network_list:
        if m.version == version:
            return True
    return False


def validate_acls(yaml):
    """Validate the semantics of all YAML 'acls' entries"""
    result = True
    msgs = []
    logger = logging.getLogger("vppcfg.config")
    logger.addHandler(logging.NullHandler())

    if not "acls" in yaml:
        return result, msgs

    for aclname, acl in yaml["acls"].items():
        terms = 0
        for acl_term in acl["terms"]:
            terms += 1
            orig_acl_term = acl_term.copy()
            acl_term = hydrate_term(acl_term)
            logger.debug(
                f"acl {aclname} term {terms} orig {orig_acl_term} hydrated {acl_term}"
            )
            if acl_term["family"] == "ipv4":
                want_ipv4 = True
                want_ipv6 = False
            elif acl_term["family"] == "ipv6":
                want_ipv4 = False
                want_ipv6 = True
            else:
                want_ipv4 = True
                want_ipv6 = True

            src_network_list = get_network_list(
                yaml, acl_term["source"], want_ipv4=want_ipv4, want_ipv6=want_ipv6
            )
            dst_network_list = get_network_list(
                yaml, acl_term["destination"], want_ipv4=want_ipv4, want_ipv6=want_ipv6
            )
            logger.debug(
                f"acl {aclname} term {terms} src: {src_network_list} dst: {dst_network_list}"
            )
            if len(src_network_list) == 0:
                msgs.append(
                    f"acl {aclname} term {terms} family {acl_term['family']} has no source"
                )
                result = False
            if len(dst_network_list) == 0:
                msgs.append(
                    f"acl {aclname} term {terms} family {acl_term['family']} has no destination"
                )
                result = False
            if len(dst_network_list) == 0 or len(src_network_list) == 0:
                ## Pointless to continue if there's no src/dst at all
                continue

            src_network_has_ipv4 = network_list_has_family(src_network_list, 4)
            dst_network_has_ipv4 = network_list_has_family(dst_network_list, 4)
            src_network_has_ipv6 = network_list_has_family(src_network_list, 6)
            dst_network_has_ipv6 = network_list_has_family(dst_network_list, 6)

            if (
                src_network_has_ipv4 != dst_network_has_ipv4
                and src_network_has_ipv6 != dst_network_has_ipv6
            ):
                msgs.append(
                    f"acl {aclname} term {terms} source and destination family do not overlap"
                )
                result = False
                continue

            proto = get_protocol(acl_term["protocol"])
            if proto is None:
                msgs.append(f"acl {aclname} term {terms} could not understand protocol")
                result = False

            if not proto in [6, 17]:
                if "source-port" in orig_acl_term:
                    msgs.append(
                        f"acl {aclname} term {terms} source-port can only be specified for protocol tcp or udp"
                    )
                    result = False
                if "destination-port" in orig_acl_term:
                    msgs.append(
                        f"acl {aclname} term {terms} destination-port can only be specified for protocol tcp or udp"
                    )
                    result = False
            else:
                src_low_port, src_high_port = get_port_low_high(acl_term["source-port"])
                dst_low_port, dst_high_port = get_port_low_high(
                    acl_term["destination-port"]
                )

                if src_low_port is None or src_high_port is None:
                    msgs.append(
                        f"acl {aclname} term {terms} could not understand source-port"
                    )
                    result = False
                else:
                    if src_low_port > src_high_port:
                        msgs.append(
                            f"acl {aclname} term {terms} source-port low value is greater than high value"
                        )
                        result = False
                    if src_low_port < 0 or src_low_port > 65535:
                        msgs.append(
                            f"acl {aclname} term {terms} source-port low value is not between [0,65535]"
                        )
                        result = False
                    if src_high_port < 0 or src_high_port > 65535:
                        msgs.append(
                            f"acl {aclname} term {terms} source-port high value is not between [0,65535]"
                        )
                        result = False

                if dst_low_port is None or dst_high_port is None:
                    msgs.append(
                        f"acl {aclname} term {terms} could not understand destination-port"
                    )
                    result = False
                else:
                    if dst_low_port > dst_high_port:
                        msgs.append(
                            f"acl {aclname} term {terms} destination-port low value is greater than high value"
                        )
                        result = False
                    if dst_low_port < 0 or dst_low_port > 65535:
                        msgs.append(
                            f"acl {aclname} term {terms} destination-port low value is not between [0,65535]"
                        )
                        result = False
                    if dst_high_port < 0 or dst_high_port > 65535:
                        msgs.append(
                            f"acl {aclname} term {terms} destination-port high value is not between [0,65535]"
                        )
                        result = False

            if not proto in [1, 58]:
                if "icmp-code" in orig_acl_term:
                    msgs.append(
                        f"acl {aclname} term {terms} icmp-code can only be specified for protocol icmp or ipv6-icmp"
                    )
                    result = False
                if "icmp-type" in orig_acl_term:
                    msgs.append(
                        f"acl {aclname} term {terms} icmp-type can only be specified for protocol icmp or ipv6-icmp"
                    )
                    result = False
            else:
                icmp_code_low, icmp_code_high = get_icmp_low_high(acl_term["icmp-code"])
                icmp_type_low, icmp_type_high = get_icmp_low_high(acl_term["icmp-type"])
                if icmp_code_low > icmp_code_high:
                    msgs.append(
                        f"acl {aclname} term {terms} icmp-code low value is greater than high value"
                    )
                    result = False
                if icmp_type_low > icmp_type_high:
                    msgs.append(
                        f"acl {aclname} term {terms} icmp-type low value is greater than high value"
                    )
                    result = False

    return result, msgs

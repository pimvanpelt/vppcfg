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


def get_aclx(yaml):
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

    # Figure out the address family
    if "family" not in acl_term:
        if "source" in acl_term and ":" in acl_term["source"]:
            acl_term["family"] = "ipv6"
        elif "destination" in acl_term and ":" in acl_term["destination"]:
            acl_term["family"] = "ipv6"
        elif "source" in acl_term and "." in acl_term["source"]:
            acl_term["family"] = "ipv4"
        elif "destination" in acl_term and "." in acl_term["destination"]:
            acl_term["family"] = "ipv4"
        else:
            acl_term["family"] = "any"

    # Set source/destionation based on family, if they're omitted
    if acl_term["family"] == "ipv4" and "source" not in acl_term:
        acl_term["source"] = "0.0.0.0/0"
    if acl_term["family"] == "ipv4" and "destination" not in acl_term:
        acl_term["destination"] = "0.0.0.0/0"
    if acl_term["family"] == "ipv6" and "source" not in acl_term:
        acl_term["source"] = "::/0"
    if acl_term["family"] == "ipv6" and "destination" not in acl_term:
        acl_term["destination"] = "::/0"

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
            logger.debug(f"acl term {terms} orig {orig_acl_term} hydrated {acl_term}")
            if acl_term["family"] == "any":
                if "source" in acl_term:
                    msgs.append(f"acl term {terms} family any cannot have source")
                    result = False
                if "destination" in acl_term:
                    msgs.append(f"acl term {terms} family any cannot have destination")
                    result = False
            else:
                src = ipaddress.ip_network(acl_term["source"])
                dst = ipaddress.ip_network(acl_term["destination"])
                if src.version != dst.version:
                    msgs.append(
                        f"acl term {terms} source and destination have different address family"
                    )
                    result = False

            proto = get_protocol(acl_term["protocol"])
            if proto is None:
                msgs.append(f"acl term {terms} could not understand protocol")
                result = False

            if not proto in [6, 17]:
                if "source-port" in orig_acl_term:
                    msgs.append(
                        f"acl term {terms} source-port can only be specified for protocol tcp or udp"
                    )
                    result = False
                if "destination-port" in orig_acl_term:
                    msgs.append(
                        f"acl term {terms} destination-port can only be specified for protocol tcp or udp"
                    )
                    result = False

            if proto in [6, 17]:
                src_low_port, src_high_port = get_port_low_high(acl_term["source-port"])
                dst_low_port, dst_high_port = get_port_low_high(
                    acl_term["destination-port"]
                )

                if src_low_port is None or src_high_port is None:
                    msgs.append(f"acl term {terms} could not understand source port")
                    result = False
                else:
                    if src_low_port > src_high_port:
                        msgs.append(
                            f"acl term {terms} source low port is higher than source high port"
                        )
                        result = False
                    if src_low_port < 0 or src_low_port > 65535:
                        msgs.append(
                            f"acl term {terms} source low port is not between [0,65535]"
                        )
                        result = False
                    if src_high_port < 0 or src_high_port > 65535:
                        msgs.append(
                            f"acl term {terms} source high port is not between [0,65535]"
                        )
                        result = False

                if dst_low_port is None or dst_high_port is None:
                    msgs.append(
                        f"acl term {terms} could not understand destination port"
                    )
                    result = False
                else:
                    if dst_low_port > dst_high_port:
                        msgs.append(
                            f"acl term {terms} destination low port is higher than destination high port"
                        )
                        result = False
                    if dst_low_port < 0 or dst_low_port > 65535:
                        msgs.append(
                            f"acl term {terms} destination low port is not between [0,65535]"
                        )
                        result = False
                    if dst_high_port < 0 or dst_high_port > 65535:
                        msgs.append(
                            f"acl term {terms} destination high port is not between [0,65535]"
                        )
                        result = False

            if not proto in [1, 58]:
                if "icmp-code" in orig_acl_term:
                    msgs.append(
                        f"acl term {terms} icmp-code can only be specified for protocol icmp or icmp-ipv6"
                    )
                    result = False
                if "icmp-type" in orig_acl_term:
                    msgs.append(
                        f"acl term {terms} icmp-type can only be specified for protocol icmp or icmp-ipv6"
                    )
                    result = False
            if proto in [1, 58]:
                icmp_code_low, icmp_code_high = get_icmp_low_high(acl_term["icmp-code"])
                icmp_type_low, icmp_type_high = get_icmp_low_high(acl_term["icmp-type"])
                if icmp_code_low > icmp_code_high:
                    msgs.append(f"acl term {terms} icmp-code low value is higher than high value")
                    result = False
                if icmp_type_low > icmp_type_high:
                    msgs.append(f"acl term {terms} icmp-type low value is higher than high value")
                    result = False

    return result, msgs

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
""" A vppcfg configuration module that validates interfaces """
import logging
from . import bondethernet
from . import bridgedomain
from . import loopback
from . import vxlan_tunnel
from . import lcp
from . import address
from . import mac
from . import tap


def get_qinx_parent_by_name(yaml, ifname):
    """Returns the sub-interface which matches a QinAD or QinQ outer tag, or None,None
    if that sub-interface doesn't exist."""

    if not is_qinx(yaml, ifname):
        return None, None
    _qinx_ifname, qinx_iface = get_by_name(yaml, ifname)
    if not qinx_iface:
        return None, None

    qinx_encap = get_encapsulation(yaml, ifname)
    if not qinx_encap:
        return None, None

    parent_ifname, parent_iface = get_parent_by_name(yaml, ifname)
    if not parent_iface:
        return None, None

    for subid, sub_iface in parent_iface["sub-interfaces"].items():
        sub_ifname = f"{parent_ifname}.{int(subid)}"
        sub_encap = get_encapsulation(yaml, sub_ifname)
        if not sub_encap:
            continue
        if qinx_encap["dot1q"] > 0 and sub_encap["dot1q"] == qinx_encap["dot1q"]:
            return sub_ifname, sub_iface
        if qinx_encap["dot1ad"] > 0 and sub_encap["dot1ad"] == qinx_encap["dot1ad"]:
            return sub_ifname, sub_iface
    return None, None


def get_parent_by_name(yaml, ifname):
    """Returns the sub-interface's parent, or None,None if the sub-int doesn't exist."""
    if not ifname:
        return None, None

    try:
        parent_ifname, subid = ifname.split(".")
        subid = int(subid)
        iface = yaml["interfaces"][parent_ifname]
        return parent_ifname, iface
    except KeyError:
        pass
    except ValueError:
        pass
    return None, None


def get_by_lcp_name(yaml, lcpname):
    """Returns the interface or sub-interface by a given lcp name, or None,None if it does not exist"""
    if not "interfaces" in yaml:
        return None, None
    for ifname, iface in yaml["interfaces"].items():
        if "lcp" in iface and iface["lcp"] == lcpname:
            return ifname, iface
        if not "sub-interfaces" in iface:
            continue
        for subid, sub_iface in yaml["interfaces"][ifname]["sub-interfaces"].items():
            sub_ifname = f"{ifname}.{int(subid)}"
            if "lcp" in sub_iface and sub_iface["lcp"] == lcpname:
                return sub_ifname, sub_iface
    return None, None


def get_by_name(yaml, ifname):
    """Returns the interface or sub-interface by a given name, or None,None if it does not exist"""
    if "." in ifname:
        try:
            phy_ifname, subid = ifname.split(".")
            subid = int(subid)
            iface = yaml["interfaces"][phy_ifname]["sub-interfaces"][subid]
            return ifname, iface
        except ValueError:
            return None, None
        except KeyError:
            return None, None

    try:
        iface = yaml["interfaces"][ifname]
        return ifname, iface
    except KeyError:
        pass
    return None, None


def is_sub(yaml, ifname):
    """Returns True if this interface is a sub-interface"""
    _parent_ifname, parent_iface = get_parent_by_name(yaml, ifname)
    return isinstance(parent_iface, dict)


def has_sub(yaml, ifname):
    """Returns True if this interface has sub-interfaces"""
    if not "interfaces" in yaml:
        return False

    if ifname in yaml["interfaces"]:
        iface = yaml["interfaces"][ifname]
        if "sub-interfaces" in iface and len(iface["sub-interfaces"]) > 0:
            return True
    return False


def has_address(yaml, ifname):
    """Returns True if this interface or sub-interface has one or more addresses"""

    ifname, iface = get_by_name(yaml, ifname)
    if not iface:
        return False
    return "addresses" in iface


def get_l2xc_interfaces(yaml):
    """Returns a list of all interfaces that have an L2 CrossConnect"""
    ret = []
    if not "interfaces" in yaml:
        return ret
    for ifname, iface in yaml["interfaces"].items():
        if "l2xc" in iface:
            ret.append(ifname)
        if "sub-interfaces" in iface:
            for subid, sub_iface in iface["sub-interfaces"].items():
                sub_ifname = f"{ifname}.{int(subid)}"
                if "l2xc" in sub_iface:
                    ret.append(sub_ifname)

    return ret


def get_unnumbered_interfaces(yaml):
    """Returns a list of all interfaces that are unnumbered"""
    ret = []
    if not "interfaces" in yaml:
        return ret
    for ifname, iface in yaml["interfaces"].items():
        if "unnumbered" in iface:
            ret.append(ifname)
        if "sub-interfaces" in iface:
            for subid, sub_iface in iface["sub-interfaces"].items():
                sub_ifname = f"{ifname}.{int(subid)}"
                if "unnumbered" in sub_iface:
                    ret.append(sub_ifname)

    return ret


def is_l2xc_interface(yaml, ifname):
    """Returns True if this interface has an L2 CrossConnect"""

    return ifname in get_l2xc_interfaces(yaml)


def get_l2xc_target_interfaces(yaml):
    """Returns a list of all interfaces that are the target of an L2 CrossConnect"""
    ret = []
    if "interfaces" in yaml:
        for _ifname, iface in yaml["interfaces"].items():
            if "l2xc" in iface:
                ret.append(iface["l2xc"])
            if "sub-interfaces" in iface:
                for _subid, sub_iface in iface["sub-interfaces"].items():
                    if "l2xc" in sub_iface:
                        ret.append(sub_iface["l2xc"])

    return ret


def is_l2xc_target_interface(yaml, ifname):
    """Returns True if this interface is the target of an L2 CrossConnect"""

    return ifname in get_l2xc_target_interfaces(yaml)


def is_l2xc_target_interface_unique(yaml, ifname):
    """Returns True if this interface is referenced as an l2xc target zero or one times"""

    ifs = get_l2xc_target_interfaces(yaml)
    return ifs.count(ifname) < 2


def has_lcp(yaml, ifname):
    """Returns True if this interface or sub-interface has an LCP"""

    ifname, iface = get_by_name(yaml, ifname)
    if not iface:
        return False
    return "lcp" in iface


def valid_encapsulation(yaml, ifname):
    """Returns True if the sub interface has a valid encapsulation, or
    none at all"""
    ifname, iface = get_by_name(yaml, ifname)
    if not iface:
        return True
    if not "encapsulation" in iface:
        return True

    encap = iface["encapsulation"]
    if "dot1ad" in encap and "dot1q" in encap:
        return False
    if "inner-dot1q" in encap and not ("dot1ad" in encap or "dot1q" in encap):
        return False
    if "exact-match" in encap and not encap["exact-match"] and has_lcp(yaml, ifname):
        return False

    return True


def get_encapsulation(yaml, ifname):
    """Returns the encapsulation of an interface name as a fully formed dictionary:

    dot1q: int (default 0)
    dot1ad: int (default 0)
    inner-dot1q: int (default 0)
    exact-match: bool (default False)

    If the interface is not a sub-int with valid encapsulation, None is returned.
    """
    if not valid_encapsulation(yaml, ifname):
        return None

    ifname, iface = get_by_name(yaml, ifname)
    if not iface:
        return None

    _parent_ifname, parent_iface = get_parent_by_name(yaml, ifname)
    if not iface or not parent_iface:
        return None
    _parent_ifname, subid = ifname.split(".")

    dot1q = 0
    dot1ad = 0
    inner_dot1q = 0
    exact_match = False
    if not "encapsulation" in iface:
        dot1q = int(subid)
        exact_match = True
    else:
        if "dot1q" in iface["encapsulation"]:
            dot1q = iface["encapsulation"]["dot1q"]
        elif "dot1ad" in iface["encapsulation"]:
            dot1ad = iface["encapsulation"]["dot1ad"]
        if "inner-dot1q" in iface["encapsulation"]:
            inner_dot1q = iface["encapsulation"]["inner-dot1q"]
        if "exact-match" in iface["encapsulation"]:
            exact_match = iface["encapsulation"]["exact-match"]

    return {
        "dot1q": int(dot1q),
        "dot1ad": int(dot1ad),
        "inner-dot1q": int(inner_dot1q),
        "exact-match": bool(exact_match),
    }


def get_phys(yaml):
    """Return a list of all toplevel (ie. non-sub) interfaces which are
    assumed to be physical network cards, eg TenGigabitEthernet1/0/0. Note
    that derived/created interfaces such as Tunnels, BondEthernets and
    Loopbacks are not returned"""
    ret = []
    if not "interfaces" in yaml:
        return ret
    for ifname, _iface in yaml["interfaces"].items():
        if is_phy(yaml, ifname):
            ret.append(ifname)
    return ret


def is_phy(yaml, ifname):
    """Returns True if the ifname is the name of a physical network interface."""

    ifname, iface = get_by_name(yaml, ifname)
    if iface is None:
        return False
    if is_sub(yaml, ifname):
        return False

    if bondethernet.is_bondethernet(yaml, ifname):
        return False
    if loopback.is_loopback(yaml, ifname):
        return False
    if vxlan_tunnel.is_vxlan_tunnel(yaml, ifname):
        return False
    if tap.is_tap(yaml, ifname):
        return False
    return True


def get_interfaces(yaml):
    """Return a list of all interface and sub-interface names"""
    ret = []
    if not "interfaces" in yaml:
        return ret
    for ifname, iface in yaml["interfaces"].items():
        ret.append(ifname)
        if not "sub-interfaces" in iface:
            continue
        for subid, _sub_iface in iface["sub-interfaces"].items():
            ret.append(f"{ifname}.{int(subid)}")
    return ret


def get_sub_interfaces(yaml):
    """Return all interfaces which are a subinterface."""
    ret = []
    for ifname in get_interfaces(yaml):
        if is_sub(yaml, ifname):
            ret.append(ifname)
    return ret


def get_qinx_interfaces(yaml):
    """Return all interfaces which are double-tagged, either QinAD or QinQ.
    These interfaces will always have a valid encapsulation with 'inner-dot1q'
    set to non-zero.

    Note: this is always a strict subset of get_sub_interfaces()
    """
    ret = []
    for ifname in get_interfaces(yaml):
        if not is_sub(yaml, ifname):
            continue
        encap = get_encapsulation(yaml, ifname)
        if not encap:
            continue
        if encap["inner-dot1q"] > 0:
            ret.append(ifname)
    return ret


def is_qinx(yaml, ifname):
    """Returns True if the interface is a double-tagged (QinQ or QinAD) interface"""
    return ifname in get_qinx_interfaces(yaml)


def unique_encapsulation(yaml, sub_ifname):
    """Ensures that for the sub_ifname specified, there exist no other sub-ints on the
    parent with the same encapsulation."""
    new_ifname, iface = get_by_name(yaml, sub_ifname)
    parent_ifname, parent_iface = get_parent_by_name(yaml, new_ifname)
    if not iface or not parent_iface:
        return False

    sub_encap = get_encapsulation(yaml, new_ifname)
    if not sub_encap:
        return False

    ncount = 0
    for subid, _sibling_iface in parent_iface["sub-interfaces"].items():
        sibling_ifname = f"{parent_ifname}.{int(subid)}"
        sibling_encap = get_encapsulation(yaml, sibling_ifname)
        if sub_encap == sibling_encap and new_ifname != sibling_ifname:
            ncount = ncount + 1

    return ncount == 0


def is_l2(yaml, ifname):
    """Returns True if the interface is an L2XC source, L2XC target or a member of a bridgedomain"""
    if bridgedomain.is_bridge_interface(yaml, ifname):
        return True
    if is_l2xc_interface(yaml, ifname):
        return True
    if is_l2xc_target_interface(yaml, ifname):
        return True
    return False


def is_l3(yaml, ifname):
    """Returns True if the interface exists and is neither l2xc target nor bridgedomain"""
    return not is_l2(yaml, ifname)


def is_unnumbered(yaml, ifname):
    """Returns True if the interface exists and is unnumbered"""
    return ifname in get_unnumbered_interfaces(yaml)


def get_lcp(yaml, ifname):
    """Returns the LCP of the interface. If the interface is a sub-interface with L3
    enabled, synthesize it based on its parent, using smart QinQ syntax.
    Return None if no LCP can be found."""

    ifname, iface = get_by_name(yaml, ifname)
    if iface and "lcp" in iface:
        return iface["lcp"]
    return None


def get_mtu(yaml, ifname):
    """Returns MTU of the interface. If it's not set, return the parent's MTU, and
    return 1500 if no MTU was set on the sub-int or the parent."""
    ifname, iface = get_by_name(yaml, ifname)
    if iface and "mtu" in iface:
        return iface["mtu"]

    _parent_ifname, parent_iface = get_parent_by_name(yaml, ifname)
    if parent_iface and "mtu" in parent_iface:
        return parent_iface["mtu"]
    return 1500


def get_admin_state(yaml, ifname):
    """Return True if the interface admin state should be 'up'. Return False
    if it does not exist, or if it's set to 'down'."""
    ifname, iface = get_by_name(yaml, ifname)
    if not iface:
        return False
    if not "state" in iface:
        return True
    return iface["state"] == "up"


def validate_interfaces(yaml):
    """Validate the semantics of all YAML 'interfaces' entries"""
    result = True
    msgs = []
    logger = logging.getLogger("vppcfg.config")
    logger.addHandler(logging.NullHandler())

    if not "interfaces" in yaml:
        return result, msgs

    for ifname, iface in yaml["interfaces"].items():
        logger.debug(f"interface {iface}")
        if ifname.startswith("BondEthernet") and (
            None,
            None,
        ) == bondethernet.get_by_name(yaml, ifname):
            msgs.append(f"interface {ifname} does not exist in bondethernets")
            result = False
        if ifname.startswith("BondEthernet") and "mac" in iface:
            msgs.append(
                f"interface {ifname} is a member of bondethernet, cannot set MAC"
            )
            result = False
        if not "state" in iface:
            iface["state"] = "up"

        if "mac" in iface and mac.is_multicast(iface["mac"]):
            msgs.append(
                f"interface {ifname} MAC address {iface['mac']} cannot be multicast"
            )
            result = False

        if "device-type" in iface and not is_phy(yaml, ifname):
            msgs.append(f"interface {ifname} is not a PHY, cannot set device-type")
            result = False

        iface_mtu = get_mtu(yaml, ifname)
        iface_lcp = get_lcp(yaml, ifname)
        iface_address = has_address(yaml, ifname)

        if ifname.startswith("tap"):
            _tap_ifname, tap_iface = tap.get_by_name(yaml, ifname)
            if not tap_iface:
                msgs.append(f"interface {ifname} is a TAP but does not exist in taps")
                result = False
            elif "mtu" in tap_iface["host"]:
                host_mtu = tap_iface["host"]["mtu"]
                if host_mtu != iface_mtu:
                    msgs.append(
                        f"interface {ifname} is a TAP so its MTU {int(iface_mtu)} must match host MTU {int(host_mtu)}"
                    )
                    result = False
            if iface_address:
                msgs.append(f"interface {ifname} is a TAP so it cannot have an address")
                result = False
            if iface_lcp:
                msgs.append(f"interface {ifname} is a TAP so it cannot have an LCP")
                result = False
            if has_sub(yaml, ifname):
                msgs.append(
                    f"interface {ifname} is a TAP so it cannot have sub-interfaces"
                )
                result = False

        if is_l2(yaml, ifname) and iface_lcp:
            msgs.append(
                f"interface {ifname} is in L2 mode but has LCP name {iface_lcp}"
            )
            result = False
        if is_l2(yaml, ifname) and iface_address:
            msgs.append(f"interface {ifname} is in L2 mode but has an address")
            result = False
        if iface_lcp and not lcp.is_unique(yaml, iface_lcp):
            msgs.append(
                f"interface {ifname} does not have a unique LCP name {iface_lcp}"
            )
            result = False

        if "unnumbered" in iface:
            target = iface["unnumbered"]
            _, target_iface = loopback.get_by_name(yaml, target)
            if not target_iface:
                _, target_iface = get_by_name(yaml, target)
            if not target_iface:
                msgs.append(
                    f"interface {ifname} unnumbered target {target} does not exist"
                )
                result = False
            if is_l2(yaml, target):
                msgs.append(
                    f"interface {ifname} unnumbered target {target} cannot be in L2 mode"
                )
                result = False
            if is_unnumbered(yaml, target):
                msgs.append(
                    f"interface {ifname} unnumbered target {target} cannot also be unnumbered"
                )
                result = False
            if ifname == target:
                msgs.append(
                    f"interface {ifname} unnumbered target cannot point to itself"
                )
                result = False
            if has_address(yaml, ifname):
                msgs.append(
                    f"interface {ifname} cannot also have addresses when it is unnumbered"
                )
                result = False

        if "addresses" in iface:
            for addr in iface["addresses"]:
                if not address.is_allowed(yaml, ifname, iface["addresses"], addr):
                    msgs.append(
                        f"interface {ifname} IP address {addr} conflicts with another"
                    )
                    result = False
                if not address.is_canonical(addr):
                    canonical = address.get_canonical(addr)
                    msgs.append(
                        f"interface {ifname} IP address {addr} is not canonical, use {canonical}"
                    )
                    result = False

        if "l2xc" in iface:
            if has_sub(yaml, ifname):
                msgs.append(
                    f"interface {ifname} has l2xc so it cannot have sub-interfaces"
                )
                result = False
            if iface_lcp:
                msgs.append(f"interface {ifname} has l2xc so it cannot have an LCP")
                result = False
            if iface_address:
                msgs.append(f"interface {ifname} has l2xc so it cannot have an address")
                result = False
            if (None, None) == get_by_name(yaml, iface["l2xc"]):
                msgs.append(
                    f"interface {ifname} l2xc target {iface['l2xc']} does not exist"
                )
                result = False
            if iface["l2xc"] == ifname:
                msgs.append(f"interface {ifname} l2xc target cannot be itself")
                result = False
            target_mtu = get_mtu(yaml, iface["l2xc"])
            if target_mtu != iface_mtu:
                msgs.append(
                    f"interface {ifname} l2xc target MTU {int(target_mtu)} does not match source MTU {int(iface_mtu)}"
                )
                result = False
            if not is_l2xc_target_interface_unique(yaml, iface["l2xc"]):
                msgs.append(
                    f"interface {ifname} l2xc target {iface['l2xc']} is not unique"
                )
                result = False
            if bridgedomain.is_bridge_interface(yaml, iface["l2xc"]):
                msgs.append(
                    f"interface {ifname} l2xc target {iface['l2xc']} is in a bridgedomain"
                )
                result = False
            if has_lcp(yaml, iface["l2xc"]):
                msgs.append(
                    f"interface {ifname} l2xc target {iface['l2xc']} cannot have an LCP"
                )
                result = False
            if has_address(yaml, iface["l2xc"]):
                msgs.append(
                    f"interface {ifname} l2xc target {iface['l2xc']} cannot have an address"
                )
                result = False

        if has_sub(yaml, ifname):
            for sub_id, sub_iface in yaml["interfaces"][ifname][
                "sub-interfaces"
            ].items():
                logger.debug(f"sub-interface {sub_iface}")
                sub_ifname = f"{ifname}.{int(sub_id)}"
                if not sub_iface:
                    msgs.append(f"sub-interface {sub_ifname} has no config")
                    result = False
                    continue

                if not "state" in sub_iface:
                    sub_iface["state"] = "up"
                if sub_iface["state"] == "up" and iface["state"] == "down":
                    msgs.append(
                        f"sub-interface {sub_ifname} cannot be up if parent {ifname} is down"
                    )
                    result = False

                sub_mtu = get_mtu(yaml, sub_ifname)
                if sub_mtu > iface_mtu:
                    msgs.append(
                        f"sub-interface {sub_ifname} has MTU {int(sub_iface['mtu'])} higher than parent {ifname} MTU {int(iface_mtu)}"
                    )
                    result = False
                if is_qinx(yaml, sub_ifname):
                    mid_ifname, mid_iface = get_qinx_parent_by_name(yaml, sub_ifname)
                    mid_mtu = get_mtu(yaml, mid_ifname)
                    if sub_mtu > mid_mtu:
                        msgs.append(
                            f"sub-interface {sub_ifname} has MTU {int(sub_iface['mtu'])} higher than parent {mid_ifname} MTU {int(mid_mtu)}"
                        )
                        result = False

                sub_lcp = get_lcp(yaml, sub_ifname)
                if is_l2(yaml, sub_ifname) and sub_lcp:
                    msgs.append(
                        f"sub-interface {sub_ifname} is in L2 mode but has LCP name {sub_lcp}"
                    )
                    result = False
                if sub_lcp and not lcp.is_unique(yaml, sub_lcp):
                    msgs.append(
                        f"sub-interface {sub_ifname} does not have a unique LCP name {sub_lcp}"
                    )
                    result = False
                if sub_lcp and not iface_lcp:
                    msgs.append(
                        f"sub-interface {sub_ifname} has LCP name {sub_lcp} but {ifname} does not have an LCP"
                    )
                    result = False
                if sub_lcp and is_qinx(yaml, sub_ifname):
                    mid_ifname, mid_iface = get_qinx_parent_by_name(yaml, sub_ifname)
                    if not mid_iface:
                        msgs.append(
                            f"sub-interface {sub_ifname} is QinX and has LCP name {sub_lcp} which requires a parent"
                        )
                        result = False
                    elif not get_lcp(yaml, mid_ifname):
                        msgs.append(
                            f"sub-interface {sub_ifname} is QinX and has LCP name {sub_lcp} but {mid_ifname} does not have an LCP"
                        )
                        result = False

                encap = get_encapsulation(yaml, sub_ifname)
                if sub_lcp and (not encap or not encap["exact-match"]):
                    msgs.append(
                        f"sub-interface {sub_ifname} has LCP name {sub_lcp} but its encapsulation is not exact-match"
                    )
                    result = False

                if "unnumbered" in sub_iface:
                    target = sub_iface["unnumbered"]
                    _, target_iface = loopback.get_by_name(yaml, target)
                    if not target_iface:
                        _, target_iface = get_by_name(yaml, target)
                    if not target_iface:
                        msgs.append(
                            f"sub-interface {sub_ifname} unnumbered target {target} does not exist"
                        )
                        result = False
                    if is_l2(yaml, target):
                        msgs.append(
                            f"sub-interface {sub_ifname} unnumbered target {target} cannot be in L2 mode"
                        )
                        result = False
                    if is_unnumbered(yaml, target):
                        msgs.append(
                            f"sub-interface {sub_ifname} unnumbered target {target} cannot also be unnumbered"
                        )
                        result = False
                    if sub_ifname == target:
                        msgs.append(
                            f"sub-interface {sub_ifname} unnumbered target cannot point to itself"
                        )
                        result = False
                    if has_address(yaml, sub_ifname):
                        msgs.append(
                            f"sub-interface {sub_ifname} cannot also have addresses when it is unnumbered"
                        )
                        result = False

                if has_address(yaml, sub_ifname):
                    if not encap or not encap["exact-match"]:
                        msgs.append(
                            f"sub-interface {sub_ifname} has an address but its encapsulation is not exact-match"
                        )
                        result = False
                    if is_l2(yaml, sub_ifname):
                        msgs.append(
                            f"sub-interface {sub_ifname} is in L2 mode but has an address"
                        )
                        result = False
                    for addr in sub_iface["addresses"]:
                        if not address.is_allowed(
                            yaml, sub_ifname, sub_iface["addresses"], addr
                        ):
                            msgs.append(
                                f"sub-interface {sub_ifname} IP address {addr} conflicts with another"
                            )
                            result = False
                if not valid_encapsulation(yaml, sub_ifname):
                    msgs.append(f"sub-interface {sub_ifname} has invalid encapsulation")
                    result = False
                elif not unique_encapsulation(yaml, sub_ifname):
                    msgs.append(
                        f"sub-interface {sub_ifname} does not have unique encapsulation"
                    )
                    result = False
                if "l2xc" in sub_iface:
                    if has_lcp(yaml, sub_ifname):
                        msgs.append(
                            f"sub-interface {sub_ifname} has l2xc so it cannot have an LCP"
                        )
                        result = False
                    if has_address(yaml, sub_ifname):
                        msgs.append(
                            f"sub-interface {sub_ifname} has l2xc so it cannot have an address"
                        )
                        result = False
                    if (None, None) == get_by_name(yaml, sub_iface["l2xc"]):
                        msgs.append(
                            f"sub-interface {sub_ifname} l2xc target {sub_iface['l2xc']} does not exist"
                        )
                        result = False
                    if sub_iface["l2xc"] == sub_ifname:
                        msgs.append(
                            f"sub-interface {sub_ifname} l2xc target cannot be itself"
                        )
                        result = False
                    target_mtu = get_mtu(yaml, sub_iface["l2xc"])
                    if target_mtu != sub_mtu:
                        msgs.append(
                            f"sub-interface {sub_ifname} l2xc target MTU {int(target_mtu)} does not match source MTU {int(sub_mtu)}"
                        )
                        result = False
                    if not is_l2xc_target_interface_unique(yaml, sub_iface["l2xc"]):
                        msgs.append(
                            f"sub-interface {sub_ifname} l2xc target {sub_iface['l2xc']} is not unique"
                        )
                        result = False
                    if bridgedomain.is_bridge_interface(yaml, sub_iface["l2xc"]):
                        msgs.append(
                            f"sub-interface {sub_ifname} l2xc target {sub_iface['l2xc']} is in a bridgedomain"
                        )
                        result = False
                    if has_lcp(yaml, sub_iface["l2xc"]):
                        msgs.append(
                            f"sub-interface {sub_ifname} l2xc target {sub_iface['l2xc']} cannot have an LCP"
                        )
                        result = False
                    if has_address(yaml, sub_iface["l2xc"]):
                        msgs.append(
                            f"sub-interface {sub_ifname} l2xc target {sub_iface['l2xc']} cannot have an address"
                        )
                        result = False

    return result, msgs


def is_mpls(yaml, ifname):
    """Returns True if the interface exists and has mpls enabled. Returns false otherwise."""
    ifname, iface = get_by_name(yaml, ifname)
    try:
        if iface["mpls"]:
            return True
    except:
        pass
    return False

#!/usr/bin/env python
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
# -*- coding: utf-8 -*-
"""
The functions in this file interact with the VPP API to retrieve certain
metadata, and plan configuration changes towards a given YAML target configuration.
"""
import sys
import logging
from vppcfg.config import loopback
from vppcfg.config import interface
from vppcfg.config import bondethernet
from vppcfg.config import bridgedomain
from vppcfg.config import vxlan_tunnel
from vppcfg.config import lcp
from vppcfg.config import tap
from .vppapi import VPPApi


class Reconciler:
    """The Reconciler class first reads the running configuration of a VPP Dataplane,
    and based on an intended target YAML configuration file, plans a path to make the
    dataplane safely reflect the target config. It first prunes (removes) objects that
    are not meant to be in the dataplane, or are in the dataplane but are not of the
    correct create-time attributes; then it creates objects that are in the configuration
    but not yet in the dataplane; and finally it syncs the configuration attributes of
    objects that can be changed at runtime."""

    def __init__(
        self,
        cfg,
        vpp_api_socket="/run/vpp/api.sock",
        vpp_json_dir="/usr/share/vpp/api/",
    ):
        self.logger = logging.getLogger("vppcfg.reconciler")
        self.logger.addHandler(logging.NullHandler())

        self.vpp = VPPApi(vpp_api_socket, vpp_json_dir)
        self.cfg = cfg

        ## List of CLI calls emitted during the prune, create and sync phases.
        self.cli = {"prune": [], "create": [], "sync": []}

    def __del__(self):
        self.vpp.disconnect()

    def lcps_exist_with_lcp_enabled(self):
        """Returns False if there are LCPs defined in the configuration, but LinuxCP
        functionality is not enabled in VPP."""
        if not lcp.get_lcps(self.cfg):
            return True
        return self.vpp.lcp_enabled

    def phys_exist_in_vpp(self):
        """Return True if all PHYs in the config exist as physical interface names
        in VPP. Return False otherwise."""

        ret = True
        for ifname in interface.get_phys(self.cfg):
            if not ifname in self.vpp.cache["interface_names"]:
                self.logger.warning(f"Interface {ifname} does not exist in VPP")
                ret = False
        return ret

    def phys_exist_in_config(self):
        """Return True if all interfaces in VPP exist as physical interface names
        in the config. Return False otherwise."""

        ret = True
        for ifname in self.vpp.get_phys():
            if not ifname in interface.get_interfaces(self.cfg):
                self.logger.warning(f"Interface {ifname} does not exist in the config")
                ret = False
        return ret

    def prune(self):
        """Remove all objects from VPP that do not occur in the config. For an indepth explanation
        of how and why this particular pruning order is chosen, see README.md section on
        Reconciling."""
        ret = True
        if not self.prune_admin_state():
            self.logger.warning("Could not set interfaces down in VPP")
            ret = False
        if not self.prune_lcps():
            self.logger.warning("Could not prune LCPs from VPP")
            ret = False
        if not self.prune_bridgedomains():
            self.logger.warning("Could not prune BridgeDomains from VPP")
            ret = False
        if not self.prune_loopbacks():
            self.logger.warning("Could not prune Loopbacks from VPP")
            ret = False
        if not self.prune_l2xcs():
            self.logger.warning("Could not prune L2 Cross Connects from VPP")
            ret = False
        if not self.prune_sub_interfaces():
            self.logger.warning("Could not prune Sub Interfaces from VPP")
            ret = False
        if not self.prune_taps():
            self.logger.warning("Could not prune TAPs from VPP")
            ret = False
        if not self.prune_vxlan_tunnels():
            self.logger.warning("Could not prune VXLAN Tunnels from VPP")
            ret = False
        if not self.prune_bondethernets():
            self.logger.warning("Could not prune BondEthernets from VPP")
            ret = False
        if not self.prune_phys():
            self.logger.warning("Could not prune PHYs from VPP")
            ret = False
        return ret

    def prune_addresses(self, ifname, address_list):
        """Remove all addresses from interface ifname, except those in address_list,
        which may be an empty list, in which case all addresses are removed.
        """
        idx = self.vpp.cache["interface_names"][ifname].sw_if_index
        removed_addresses = []
        for addr in self.vpp.cache["interface_addresses"][idx]:
            if not addr in address_list:
                cli = f"set interface ip address del {ifname} {addr}"
                self.cli["prune"].append(cli)
                removed_addresses.append(addr)
            else:
                self.logger.debug(f"Address OK: {ifname} {addr}")
        for addr in removed_addresses:
            self.vpp.cache["interface_addresses"][idx].remove(addr)

    def prune_loopbacks(self):
        """Remove loopbacks from VPP, if they do not occur in the config."""
        removed_interfaces = []
        for numtags in [2, 1, 0]:
            for _idx, vpp_iface in self.vpp.cache["interfaces"].items():
                if vpp_iface.interface_dev_type != "Loopback":
                    continue
                if vpp_iface.sub_number_of_tags != numtags:
                    continue
                _config_ifname, config_iface = loopback.get_by_name(
                    self.cfg, vpp_iface.interface_name
                )
                if not config_iface:
                    self.prune_addresses(vpp_iface.interface_name, [])
                    if numtags == 0:
                        cli = f"delete loopback interface intfc {vpp_iface.interface_name}"
                        self.cli["prune"].append(cli)
                        removed_interfaces.append(vpp_iface.interface_name)
                    else:
                        cli = f"delete sub {vpp_iface.interface_name}"
                        self.cli["prune"].append(cli)
                        removed_interfaces.append(vpp_iface.interface_name)
                    continue
                self.logger.debug(f"Loopback OK: {vpp_iface.interface_name}")
                addresses = []
                if "addresses" in config_iface:
                    addresses = config_iface["addresses"]
                self.prune_addresses(vpp_iface.interface_name, addresses)

        for ifname in removed_interfaces:
            self.vpp.cache_remove_interface(ifname)

        return True

    def prune_bridgedomains(self):
        """Remove bridge-domains from VPP, if they do not occur in the config. If any interfaces are
        found in to-be removed bridge-domains, they are returned to L3 mode, and tag-rewrites removed."""
        for idx, bridge in self.vpp.cache["bridgedomains"].items():
            bridgename = f"bd{int(idx)}"
            _config_ifname, config_iface = bridgedomain.get_by_name(
                self.cfg, bridgename
            )
            if not config_iface:
                for member in bridge.sw_if_details:
                    if member.sw_if_index == bridge.bvi_sw_if_index:
                        continue
                    member_iface = self.vpp.cache["interfaces"][member.sw_if_index]
                    member_ifname = member_iface.interface_name
                    if member_iface.sub_id > 0:
                        cli = f"set interface l2 tag-rewrite {member_ifname} disable"
                        self.cli["prune"].append(cli)
                    cli = f"set interface l3 {member_ifname}"
                    self.cli["prune"].append(cli)
                if bridge.bvi_sw_if_index in self.vpp.cache["interfaces"]:
                    bviname = self.vpp.cache["interfaces"][
                        bridge.bvi_sw_if_index
                    ].interface_name
                    cli = f"set interface l3 {bviname}"
                    self.cli["prune"].append(cli)
                cli = f"create bridge-domain {int(idx)} del"
                self.cli["prune"].append(cli)
            else:
                self.logger.debug(f"BridgeDomain OK: {bridgename}")
                for member in bridge.sw_if_details:
                    member_ifname = self.vpp.cache["interfaces"][
                        member.sw_if_index
                    ].interface_name
                    if (
                        "members" in config_iface
                        and member_ifname in config_iface["members"]
                    ):
                        if interface.is_sub(self.cfg, member_ifname):
                            cli = (
                                f"set interface l2 tag-rewrite {member_ifname} disable"
                            )
                            self.cli["prune"].append(cli)
                        cli = f"set interface l3 {member_ifname}"
                        self.cli["prune"].append(cli)
                if (
                    "bvi" in config_iface
                    and bridge.bvi_sw_if_index in self.vpp.cache["interfaces"]
                ):
                    bviname = self.vpp.cache["interfaces"][
                        bridge.bvi_sw_if_index
                    ].interface_name
                    if bviname != config_iface["bvi"]:
                        cli = f"set interface l3 {bviname}"
                        self.cli["prune"].append(cli)

        return True

    def prune_l2xcs(self):
        """Remove all L2XC source interfaces from VPP, if they do not occur in the config. If they occur,
        but are crossconnected to a different interface name, also remove them. Interfaces are put
        back into L3 mode, and their tag-rewrites removed."""
        removed_l2xcs = []
        for _idx, l2xc in self.vpp.cache["l2xcs"].items():
            vpp_rx_ifname = self.vpp.cache["interfaces"][
                l2xc.rx_sw_if_index
            ].interface_name
            config_rx_ifname, config_rx_iface = interface.get_by_name(
                self.cfg, vpp_rx_ifname
            )
            if not config_rx_ifname:
                if self.vpp.cache["interfaces"][l2xc.rx_sw_if_index].sub_id > 0:
                    cli = f"set interface l2 tag-rewrite {vpp_rx_ifname} disable"
                    self.cli["prune"].append(cli)
                cli = f"set interface l3 {vpp_rx_ifname}"
                self.cli["prune"].append(cli)
                removed_l2xcs.append(vpp_rx_ifname)
                continue

            if not interface.is_l2xc_interface(self.cfg, config_rx_ifname):
                if interface.is_sub(self.cfg, config_rx_ifname):
                    cli = f"set interface l2 tag-rewrite {vpp_rx_ifname} disable"
                    self.cli["prune"].append(cli)
                cli = f"set interface l3 {vpp_rx_ifname}"
                self.cli["prune"].append(cli)
                removed_l2xcs.append(vpp_rx_ifname)
                continue
            vpp_tx_ifname = self.vpp.cache["interfaces"][
                l2xc.tx_sw_if_index
            ].interface_name
            if vpp_tx_ifname != config_rx_iface["l2xc"]:
                if interface.is_sub(self.cfg, config_rx_ifname):
                    cli = f"set interface l2 tag-rewrite {vpp_rx_ifname} disable"
                    self.cli["prune"].append(cli)
                cli = f"set interface l3 {vpp_rx_ifname}"
                self.cli["prune"].append(cli)
                removed_l2xcs.append(vpp_rx_ifname)
                continue
            self.logger.debug(f"L2XC OK: {vpp_rx_ifname} -> {vpp_tx_ifname}")
        for l2xc in removed_l2xcs:
            self.vpp.cache_remove_l2xc(l2xc)
        return True

    def __vxlan_tunnel_has_diff(self, ifname):
        """Returns True if the given ifname (vxlan_tunnel0) has different attributes between VPP
        and the given configuration, or if either does not exist.

        Returns False if they are identical."""

        if not ifname in self.vpp.cache["interface_names"]:
            return True
        vpp_iface = self.vpp.cache["interface_names"][ifname]

        if vpp_iface.sw_if_index not in self.vpp.cache["vxlan_tunnels"]:
            return True
        vpp_vxlan = self.vpp.cache["vxlan_tunnels"][vpp_iface.sw_if_index]

        _config_ifname, config_iface = vxlan_tunnel.get_by_name(self.cfg, ifname)
        if not config_iface:
            return True

        if config_iface["local"] != str(vpp_vxlan.src_address):
            return True
        if config_iface["remote"] != str(vpp_vxlan.dst_address):
            return True
        if config_iface["vni"] != vpp_vxlan.vni:
            return True
        return False

    def __tap_has_diff(self, ifname):
        """Returns True if the given ifname (tap0) has different attributes between VPP
        and the given configuration, or if either does not exist.

        Returns False if the TAP is a Linux Control Plane LIP.
        Returns False if they are identical."""
        if not ifname in self.vpp.cache["interface_names"]:
            return True
        vpp_iface = self.vpp.cache["interface_names"][ifname]
        vpp_tap = self.vpp.cache["taps"][vpp_iface.sw_if_index]

        _config_ifname, config_iface = tap.get_by_name(self.cfg, ifname)
        if not config_iface:
            return True

        if self.vpp.tap_is_lcp(ifname):
            return False

        if (
            "name" in config_iface["host"]
            and config_iface["host"]["name"] != vpp_tap.host_if_name
        ):
            return True
        if (
            "mtu" in config_iface["host"]
            and config_iface["host"]["mtu"] != vpp_tap.host_mtu_size
        ):
            return True
        if "mac" in config_iface["host"] and config_iface["host"]["mac"] != str(
            vpp_tap.host_mac_addr
        ):
            return True
        if (
            "bridge" in config_iface["host"]
            and config_iface["host"]["bridge"] != vpp_tap.host_bridge
        ):
            return True
        if (
            "namespace" in config_iface["host"]
            and config_iface["host"]["namespace"] != vpp_tap.host_namespace
        ):
            return True

        return False

    def __bond_has_diff(self, ifname):
        """Returns True if the given ifname (BondEthernet0) have different attributes,
        or if either does not exist.

        Returns False if they are identical.
        """
        if not ifname in self.vpp.cache["interface_names"]:
            return True

        vpp_iface = self.vpp.cache["interface_names"][ifname]
        if not vpp_iface.sw_if_index in self.vpp.cache["bondethernets"]:
            return True

        config_ifname, config_iface = bondethernet.get_by_name(self.cfg, ifname)
        if not config_iface:
            return True

        vpp_bond = self.vpp.cache["bondethernets"][vpp_iface.sw_if_index]
        mode = bondethernet.mode_to_int(bondethernet.get_mode(self.cfg, config_ifname))
        if mode not in (-1, vpp_bond.mode):
            return True
        loadbalance = bondethernet.lb_to_int(
            bondethernet.get_lb(self.cfg, config_ifname)
        )
        if loadbalance not in (-1, vpp_bond.lb):
            return True

        return False

    def prune_taps(self):
        """Remove all TAPs from VPP, if they are not in the config. As an exception,
        TAPs which are a part of Linux Control Plane, are left alone, to be handled
        by prune_lcps() later."""
        removed_taps = []
        for _idx, vpp_tap in self.vpp.cache["taps"].items():
            vpp_iface = self.vpp.cache["interfaces"][vpp_tap.sw_if_index]
            vpp_ifname = vpp_iface.interface_name
            if self.vpp.tap_is_lcp(vpp_ifname):
                continue
            if self.__tap_has_diff(vpp_ifname):
                removed_taps.append(vpp_ifname)
                continue
            self.logger.debug(f"TAP OK: {vpp_ifname}")

        for ifname in removed_taps:
            cli = f"delete tap {ifname}"
            self.cli["prune"].append(cli)
            self.vpp.cache_remove_interface(ifname)
        return True

    def prune_bondethernets(self):
        """Remove all BondEthernets from VPP, if they are not in the config. If the bond has members,
        remove those from the bond before removing the bond."""
        removed_interfaces = []
        removed_bondethernet_members = []
        for idx, bond in self.vpp.cache["bondethernets"].items():
            vpp_ifname = bond.interface_name
            _config_ifname, config_iface = bondethernet.get_by_name(
                self.cfg, vpp_ifname
            )

            if self.__bond_has_diff(vpp_ifname):
                self.prune_addresses(vpp_ifname, [])
                for member in self.vpp.cache["bondethernet_members"][idx]:
                    member_ifname = self.vpp.cache["interfaces"][member].interface_name
                    cli = f"bond del {member_ifname}"
                    self.cli["prune"].append(cli)
                    removed_bondethernet_members.append(member_ifname)
                cli = f"delete bond {vpp_ifname}"
                self.cli["prune"].append(cli)
                removed_interfaces.append(vpp_ifname)
                continue

            for member in self.vpp.cache["bondethernet_members"][idx]:
                member_ifname = self.vpp.cache["interfaces"][member].interface_name
                if (
                    "interfaces" in config_iface
                    and not member_ifname in config_iface["interfaces"]
                ):
                    cli = f"bond del {member_ifname}"
                    self.cli["prune"].append(cli)
                    removed_bondethernet_members.append(member_ifname)
            addresses = []
            if "addresses" in config_iface:
                addresses = config_iface["addresses"]
            self.prune_addresses(vpp_ifname, addresses)
            self.logger.debug(f"BondEthernet OK: {vpp_ifname}")

        for ifname in removed_bondethernet_members:
            self.vpp.cache_remove_bondethernet_member(ifname)

        for ifname in removed_interfaces:
            self.vpp.cache_remove_interface(ifname)

        return True

    def prune_vxlan_tunnels(self):
        """Remove all VXLAN Tunnels from VPP, if they are not in the config. If they are in the config
        but with differing attributes, remove them also."""
        removed_interfaces = []
        for idx, vpp_vxlan in self.vpp.cache["vxlan_tunnels"].items():
            vpp_ifname = self.vpp.cache["interfaces"][idx].interface_name
            config_ifname, config_iface = vxlan_tunnel.get_by_name(self.cfg, vpp_ifname)
            if not config_iface or self.__vxlan_tunnel_has_diff(config_ifname):
                self.prune_addresses(vpp_ifname, [])
                cli = (
                    f"create vxlan tunnel instance {vpp_vxlan.instance} "
                    f"src {vpp_vxlan.src_address} dst {vpp_vxlan.dst_address} vni {vpp_vxlan.vni} del"
                )
                self.cli["prune"].append(cli)
                removed_interfaces.append(vpp_ifname)
                continue
            config_ifname, config_iface = interface.get_by_name(self.cfg, vpp_ifname)
            if config_iface:
                addresses = []
                if "addresses" in config_iface:
                    addresses = config_iface["addresses"]
                self.prune_addresses(vpp_ifname, addresses)
            self.logger.debug(f"VXLAN Tunnel OK: {vpp_ifname}")

        for ifname in removed_interfaces:
            self.vpp.cache_remove_vxlan_tunnel(ifname)
            self.vpp.cache_remove_interface(ifname)

        return True

    def prune_sub_interfaces(self):
        """Remove interfaces from VPP if they are not in the config, if their encapsulation is different,
        or if the BondEthernet they reside on is different.
        Start with inner-most (QinQ/QinAD), then Dot1Q/Dot1AD."""
        removed_interfaces = []
        for numtags in [2, 1]:
            for vpp_ifname in self.vpp.get_sub_interfaces():
                vpp_iface = self.vpp.cache["interface_names"][vpp_ifname]
                if vpp_iface.sub_number_of_tags != numtags:
                    continue

                if self.vpp.tap_is_lcp(vpp_ifname):
                    continue

                prune = False
                _config_ifname, config_iface = interface.get_by_name(
                    self.cfg, vpp_ifname
                )
                if not config_iface:
                    prune = True
                elif (
                    vpp_iface.interface_dev_type == "bond"
                    and vpp_iface.sub_number_of_tags > 0
                ):
                    (
                        config_parent_ifname,
                        _config_parent_iface,
                    ) = interface.get_parent_by_name(self.cfg, vpp_ifname)
                    if self.__bond_has_diff(config_parent_ifname):
                        prune = True

                config_encap = interface.get_encapsulation(self.cfg, vpp_ifname)
                vpp_encap = self.__get_encapsulation(vpp_iface)
                if config_encap != vpp_encap:
                    prune = True

                if prune:
                    self.prune_addresses(vpp_ifname, [])
                    cli = f"delete sub {vpp_ifname}"
                    self.cli["prune"].append(cli)
                    removed_interfaces.append(vpp_ifname)
                    continue

                addresses = []
                if "addresses" in config_iface:
                    addresses = config_iface["addresses"]
                self.prune_addresses(vpp_ifname, addresses)
                self.logger.debug(f"Sub Interface OK: {vpp_ifname}")

        for ifname in removed_interfaces:
            self.vpp.cache_remove_interface(ifname)

        return True

    def prune_phys(self):
        """Set default MTU and remove IPs for PHYs that are not in the config."""
        for vpp_ifname in self.vpp.get_phys():
            vpp_iface = self.vpp.cache["interface_names"][vpp_ifname]
            _config_ifname, config_iface = interface.get_by_name(self.cfg, vpp_ifname)
            if not config_iface:
                ## Interfaces were sent DOWN in the prune_admin_state() step previously
                self.prune_addresses(vpp_ifname, [])
                if vpp_iface.link_mtu != 9000:
                    cli = f"set interface mtu 9000 {vpp_ifname}"
                    self.cli["prune"].append(cli)
                continue
            addresses = []
            if "addresses" in config_iface:
                addresses = config_iface["addresses"]
            self.prune_addresses(vpp_ifname, addresses)
            self.logger.debug(f"Interface OK: {vpp_ifname}")
        return True

    def __parent_iface_by_encap(self, sup_sw_if_index, outer, dot1ad=True):
        """Returns the sw_if_index of an interface on a given super_sw_if_index with given dot1q/dot1ad outer and inner-dot1q=0,
        in other words the intermediary Dot1Q/Dot1AD belonging to a QinX interface. If the interface doesn't exist, None is
        returned."""
        for idx, iface in self.vpp.cache["interfaces"].items():
            if iface.sup_sw_if_index != sup_sw_if_index:
                continue
            if iface.sub_inner_vlan_id > 0:
                continue
            if dot1ad and (iface.sub_if_flags & 8) and iface.sub_outer_vlan_id == outer:
                self.logger.debug(f"match: {iface.interface_name} (dot1ad)")
                return idx
            if (
                not dot1ad
                and not (iface.sub_if_flags & 8)
                and iface.sub_outer_vlan_id == outer
            ):
                self.logger.debug(f"match: {iface.interface_name} (dot1q)")
                return idx
        return None

    def __get_encapsulation(self, iface):
        """Return a dictionary-based encapsulation of the sub-interface, which helps comparing them to the same object
        returned by config.interface.get_encapsulation()."""
        if iface.sub_if_flags & 8:
            dot1ad = iface.sub_outer_vlan_id
            dot1q = 0
        else:
            dot1q = iface.sub_outer_vlan_id
            dot1ad = 0
        inner_dot1q = iface.sub_inner_vlan_id
        exact_match = iface.sub_if_flags & 16
        return {
            "dot1q": int(dot1q),
            "dot1ad": int(dot1ad),
            "inner-dot1q": int(inner_dot1q),
            "exact-match": bool(exact_match),
        }

    def prune_lcps(self):
        """Remove LCPs which are not in the configuration, starting with QinQ/QinAD interfaces, then Dot1Q/Dot1AD,
        and finally PHYs/BondEthernets/Tunnels/Loopbacks. For QinX, special care is taken to ensure that
        their intermediary interface exists, and has the correct encalsulation. If the intermediary interface
        changed, the QinX LCP is removed. The same is true for Dot1Q/Dot1AD interfaces: if their encapsulation
        has changed, we will have to re-create the underlying sub-interface, so the LCP has to be removed.

        Order is important: destroying an LCP of a PHY will invalidate its Dot1Q/Dot1AD as well as their
        downstream children in Linux.
        """
        lcps = self.vpp.cache["lcps"]

        removed_lcps = []
        for numtags in [2, 1, 0]:
            for _idx, lcp_iface in lcps.items():
                vpp_iface = self.vpp.cache["interfaces"][lcp_iface.phy_sw_if_index]
                if vpp_iface.sub_number_of_tags != numtags:
                    continue
                if vpp_iface.interface_dev_type == "Loopback":
                    config_ifname, config_iface = loopback.get_by_lcp_name(
                        self.cfg, lcp_iface.host_if_name
                    )
                else:
                    config_ifname, config_iface = interface.get_by_lcp_name(
                        self.cfg, lcp_iface.host_if_name
                    )
                if not config_iface:
                    ## Interface doesn't exist in the config
                    removed_lcps.append(lcp_iface)
                    continue
                if not "lcp" in config_iface:
                    ## Interface doesn't have an LCP
                    removed_lcps.append(lcp_iface)
                    continue
                if vpp_iface.sub_number_of_tags == 2:
                    vpp_parent_idx = self.__parent_iface_by_encap(
                        vpp_iface.sup_sw_if_index,
                        vpp_iface.sub_outer_vlan_id,
                        vpp_iface.sub_if_flags & 8,
                    )
                    vpp_parent_iface = self.vpp.cache["interfaces"][vpp_parent_idx]
                    parent_lcp = lcps[vpp_parent_iface.sw_if_index]
                    (
                        config_parent_ifname,
                        config_parent_iface,
                    ) = interface.get_by_lcp_name(self.cfg, parent_lcp.host_if_name)
                    if not config_parent_iface:
                        ## QinX's parent doesn't exist in the config
                        removed_lcps.append(lcp_iface)
                        continue
                    if not "lcp" in config_parent_iface:
                        ## QinX's parent doesn't have an LCP
                        removed_lcps.append(lcp_iface)
                        continue
                    if parent_lcp.host_if_name != config_parent_iface["lcp"]:
                        ## QinX's parent LCP name mismatch
                        removed_lcps.append(lcp_iface)
                        continue
                    config_parent_encap = interface.get_encapsulation(
                        self.cfg, config_parent_ifname
                    )
                    vpp_parent_encap = self.__get_encapsulation(vpp_parent_iface)
                    if config_parent_encap != vpp_parent_encap:
                        ## QinX's parent encapsulation mismatch
                        removed_lcps.append(lcp_iface)
                        continue

                if vpp_iface.sub_number_of_tags > 0:
                    config_encap = interface.get_encapsulation(self.cfg, config_ifname)
                    vpp_encap = self.__get_encapsulation(vpp_iface)
                    if config_encap != vpp_encap:
                        ## Encapsulation mismatch
                        removed_lcps.append(lcp_iface)
                        continue

                if vpp_iface.interface_dev_type == "Loopback":
                    ## Loopbacks will not have a PHY to check.
                    continue
                if vpp_iface.interface_dev_type == "bond":
                    bond_iface = self.vpp.cache["interfaces"][vpp_iface.sup_sw_if_index]
                    if self.__bond_has_diff(bond_iface.interface_name):
                        ## If BondEthernet changed, it has to be re-created, so all LCPs must be removed.
                        removed_lcps.append(lcp_iface)
                        continue

                phy_lcp = lcps[vpp_iface.sup_sw_if_index]
                _config_phy_ifname, config_phy_iface = interface.get_by_lcp_name(
                    self.cfg, phy_lcp.host_if_name
                )
                if not config_phy_iface:
                    ## Phy doesn't exist in the config
                    removed_lcps.append(lcp_iface)
                    continue
                if not "lcp" in config_phy_iface:
                    ## Phy doesn't have an LCP
                    removed_lcps.append(lcp_iface)
                    continue
                if phy_lcp.host_if_name != config_phy_iface["lcp"]:
                    ## Phy LCP name mismatch
                    removed_lcps.append(lcp_iface)
                    continue

                self.logger.debug(
                    f"LCP OK: {lcp_iface.host_if_name} -> (vpp={vpp_iface.interface_name}, config={config_ifname})"
                )

        for lcp_iface in removed_lcps:
            vpp_ifname = self.vpp.cache["interfaces"][
                lcp_iface.phy_sw_if_index
            ].interface_name
            cli = f"lcp delete {vpp_ifname}"
            self.cli["prune"].append(cli)
            self.vpp.cache_remove_lcp(lcp_iface.host_if_name)
        return True

    def prune_admin_state(self):
        """Set admin-state down for all interfaces that are not in the config."""
        for ifname in (
            self.vpp.get_qinx_interfaces()
            + self.vpp.get_dot1x_interfaces()
            + self.vpp.get_bondethernets()
            + self.vpp.get_phys()
            + self.vpp.get_vxlan_tunnels()
            + self.vpp.get_loopbacks()
        ):
            if not ifname in interface.get_interfaces(
                self.cfg
            ) + loopback.get_loopbacks(self.cfg):
                vpp_iface = self.vpp.cache["interface_names"][ifname]

                if self.vpp.tap_is_lcp(ifname):
                    continue

                if vpp_iface.flags & 1:  # IF_STATUS_API_FLAG_ADMIN_UP
                    cli = f"set interface state {ifname} down"
                    self.cli["prune"].append(cli)

        return True

    def create(self):
        """Create all objects in VPP that occur in the config but not in VPP. For an indepth
        explanation of how and why this particular pruning order is chosen, see README.md
        section on Reconciling."""
        ret = True
        if not self.create_loopbacks():
            self.logger.warning("Could not create Loopbacks in VPP")
            ret = False
        if not self.create_bondethernets():
            self.logger.warning("Could not create BondEthernets in VPP")
            ret = False
        if not self.create_vxlan_tunnels():
            self.logger.warning("Could not create VXLAN Tunnels in VPP")
            ret = False
        if not self.create_taps():
            self.logger.warning("Could not create TAPs in VPP")
            ret = False
        if not self.create_sub_interfaces():
            self.logger.warning("Could not create Sub Interfaces in VPP")
            ret = False
        if not self.create_bridgedomains():
            self.logger.warning("Could not create BridgeDomains in VPP")
            ret = False
        if not self.create_lcps():
            self.logger.warning("Could not create LCPs in VPP")
            ret = False
        return ret

    def create_loopbacks(self):
        """Create all loopbacks that occur in the config but not in VPP"""
        for ifname in loopback.get_loopbacks(self.cfg):
            if ifname in self.vpp.cache["interface_names"]:
                continue
            instance = int(ifname[4:])
            cli = f"create loopback interface instance {int(instance)}"
            ifname, iface = loopback.get_by_name(self.cfg, ifname)
            if "mac" in iface:
                cli += f" mac {iface['mac']}"
            self.cli["create"].append(cli)
        return True

    def create_bondethernets(self):
        """Create all bondethernets that occur in the config but not in VPP"""
        for ifname in bondethernet.get_bondethernets(self.cfg):
            if ifname in self.vpp.cache["interface_names"]:
                continue
            ifname, iface = bondethernet.get_by_name(self.cfg, ifname)
            instance = int(ifname[12:])
            mode = bondethernet.get_mode(self.cfg, ifname)
            cli = f"create bond id {int(instance)} mode {mode}"
            loadbalance = bondethernet.get_lb(self.cfg, ifname)
            if loadbalance:
                cli += f" load-balance {loadbalance}"
            if "mac" in iface:
                cli += f" hw-addr {iface['mac']}"
            self.cli["create"].append(cli)
        return True

    def create_vxlan_tunnels(self):
        """Create all vxlan_tunnels that occur in the config but not in VPP"""
        for ifname in vxlan_tunnel.get_vxlan_tunnels(self.cfg):
            if ifname in self.vpp.cache["interface_names"]:
                continue
            ifname, iface = vxlan_tunnel.get_by_name(self.cfg, ifname)
            instance = int(ifname[12:])
            cli = (
                f"create vxlan tunnel src {iface['local']} dst {iface['remote']} "
                f"instance {instance} vni {iface['vni']} decap-next l2"
            )
            self.cli["create"].append(cli)
        return True

    def create_sub_interfaces(self):
        """Create all sub-interfaces that occur in the config but not in VPP"""
        ## First create 1-tag (Dot1Q/Dot1AD), and then create 2-tag (Qin*) sub-interfaces
        for do_qinx in [False, True]:
            for ifname in interface.get_sub_interfaces(self.cfg):
                if not do_qinx == interface.is_qinx(self.cfg, ifname):
                    continue

                ifname, _iface = interface.get_by_name(self.cfg, ifname)
                if ifname in self.vpp.cache["interface_names"]:
                    continue

                ## Assemble the encapsulation string
                encap = interface.get_encapsulation(self.cfg, ifname)
                if encap["dot1ad"] > 0:
                    encapstr = f"dot1ad {int(encap['dot1ad'])}"
                else:
                    encapstr = f"dot1q {int(encap['dot1q'])}"
                if do_qinx:
                    encapstr += f" inner-dot1q {int(encap['inner-dot1q'])}"
                if encap["exact-match"]:
                    encapstr += " exact-match"
                parent, subid = ifname.split(".")
                cli = f"create sub {parent} {int(int(subid))} {encapstr}"
                self.cli["create"].append(cli)
        return True

    def create_taps(self):
        """Create all taps that occur in the config but not in VPP"""
        for ifname in tap.get_taps(self.cfg):
            ifname, iface = tap.get_by_name(self.cfg, ifname)
            if ifname in self.vpp.cache["interface_names"]:
                continue
            instance = int(ifname[3:])
            cli = f"create tap id {int(instance)} host-if-name {iface['host']['name']}"
            if "mac" in iface["host"]:
                cli += f" host-mac-addr {iface['host']['mac']}"
            if "namespace" in iface["host"]:
                cli += f" host-ns {int(iface['host']['namespace'])}"
            if "bridge" in iface["host"]:
                cli += f" host-bridge {iface['host']['bridge']}"
            if "mtu" in iface["host"]:
                cli += f" host-mtu-size {int(iface['host']['mtu'])}"
            if "rx-ring-size" in iface:
                cli += f" rx-ring-size {int(iface['rx-ring-size'])}"
            if "tx-ring-size" in iface:
                cli += f" tx-ring-size {int(iface['tx-ring-size'])}"
            self.cli["create"].append(cli)

        return True

    def create_bridgedomains(self):
        """Create all bridgedomains that occur in the config but not in VPP"""
        for ifname in bridgedomain.get_bridgedomains(self.cfg):
            ifname, _iface = bridgedomain.get_by_name(self.cfg, ifname)
            instance = int(ifname[2:])
            settings = bridgedomain.get_settings(self.cfg, ifname)
            if instance in self.vpp.cache["bridgedomains"]:
                continue
            cli = f"create bridge-domain {instance}"
            if not settings["learn"]:
                cli += " learn 0"
            if not settings["unicast-flood"]:
                cli += " flood 0"
            if not settings["unknown-unicast-flood"]:
                cli += " uu-flood 0"
            if not settings["unicast-forward"]:
                cli += " forward 0"
            if settings["arp-termination"]:
                cli += " arp-term 1"
            if settings["arp-unicast-forward"]:
                cli += " arp-ufwd 1"
            if settings["mac-age-minutes"] > 0:
                cli += f" mac-age {int(settings['mac-age-minutes'])}"
            self.cli["create"].append(cli)
        return True

    def create_lcps(self):
        """Create all LCPs that occur in the config but not in VPP"""
        lcpnames = [
            self.vpp.cache["lcps"][x].host_if_name for x in self.vpp.cache["lcps"]
        ]

        ## First create untagged ...
        for ifname in interface.get_interfaces(self.cfg) + loopback.get_loopbacks(
            self.cfg
        ):
            if interface.is_sub(self.cfg, ifname):
                continue

            if ifname.startswith("loop"):
                ifname, iface = loopback.get_by_name(self.cfg, ifname)
            else:
                ifname, iface = interface.get_by_name(self.cfg, ifname)
            if not "lcp" in iface:
                continue
            if iface["lcp"] in lcpnames:
                continue
            cli = f"lcp create {ifname} host-if {iface['lcp']}"
            self.cli["create"].append(cli)

        ## ... then 1-tag (Dot1Q/Dot1AD), and then create 2-tag (Qin*) LCPs
        for do_qinx in [False, True]:
            for ifname in interface.get_sub_interfaces(self.cfg):
                if not do_qinx == interface.is_qinx(self.cfg, ifname):
                    continue
                ifname, iface = interface.get_by_name(self.cfg, ifname)
                if not "lcp" in iface:
                    continue
                if iface["lcp"] in lcpnames:
                    continue
                cli = f"lcp create {ifname} host-if {iface['lcp']}"
                self.cli["create"].append(cli)
        return True

    def sync(self):
        """Synchronize the VPP Dataplane configuration for all objects in the config"""
        ret = True
        if not self.sync_loopbacks():
            self.logger.warning("Could not sync Loopbacks in VPP")
            ret = False
        if not self.sync_bondethernets():
            self.logger.warning("Could not sync bondethernets in VPP")
            ret = False
        if not self.sync_bridgedomains():
            self.logger.warning("Could not sync bridgedomains in VPP")
            ret = False
        if not self.sync_l2xcs():
            self.logger.warning("Could not sync L2 Cross Connects in VPP")
            ret = False
        if not self.sync_mtu():
            self.logger.warning("Could not sync interface MTU in VPP")
            ret = False
        if not self.sync_addresses():
            self.logger.warning("Could not sync interface addresses in VPP")
            ret = False
        if not self.sync_phys():
            self.logger.warning("Could not sync PHYs in VPP")
            ret = False
        if not self.sync_admin_state():
            self.logger.warning("Could not sync interface adminstate in VPP")
            ret = False
        return ret

    def sync_loopbacks(self):
        """Synchronize the VPP Dataplane configuration for loopbacks"""
        for ifname in loopback.get_loopbacks(self.cfg):
            if not ifname in self.vpp.cache["interface_names"]:
                ## New loopback
                continue
            vpp_iface = self.vpp.cache["interface_names"][ifname]
            config_ifname, config_iface = loopback.get_by_name(self.cfg, ifname)
            if "mac" in config_iface and config_iface["mac"] != str(
                vpp_iface.l2_address
            ):
                cli = f"set interface mac address {config_ifname} {config_iface['mac']}"
                self.cli["sync"].append(cli)
        return True

    def sync_phys(self):
        """Synchronize the VPP Dataplane configuration for PHYs"""
        for ifname in interface.get_phys(self.cfg):
            if not ifname in self.vpp.cache["interface_names"]:
                ## New interface
                continue
            vpp_iface = self.vpp.cache["interface_names"][ifname]
            config_ifname, config_iface = interface.get_by_name(self.cfg, ifname)
            if "mac" in config_iface and config_iface["mac"] != str(
                vpp_iface.l2_address
            ):
                cli = f"set interface mac address {config_ifname} {config_iface['mac']}"
                self.cli["sync"].append(cli)
        return True

    def sync_bondethernets(self):
        """Synchronize the VPP Dataplane configuration for bondethernets"""
        for ifname in bondethernet.get_bondethernets(self.cfg):
            if ifname in self.vpp.cache["interface_names"]:
                vpp_iface = self.vpp.cache["interface_names"][ifname]
                vpp_members = [
                    self.vpp.cache["interfaces"][x].interface_name
                    for x in self.vpp.cache["bondethernet_members"][
                        vpp_iface.sw_if_index
                    ]
                ]
            else:
                ## New BondEthernet
                vpp_iface = None
                vpp_members = []

            config_bond_ifname, config_bond_iface = bondethernet.get_by_name(
                self.cfg, ifname
            )
            if not "interfaces" in config_bond_iface:
                continue
            config_ifname, config_iface = interface.get_by_name(self.cfg, ifname)
            bondmac = None
            for member_ifname in sorted(config_bond_iface["interfaces"]):
                member_ifname, member_iface = interface.get_by_name(
                    self.cfg, member_ifname
                )
                member_iface = self.vpp.cache["interface_names"][member_ifname]
                if not member_ifname in vpp_members:
                    if len(vpp_members) == 0:
                        bondmac = member_iface.l2_address
                    cli = f"bond add {config_bond_ifname} {member_iface.interface_name}"
                    self.cli["sync"].append(cli)
            if (
                vpp_iface
                and "mac" in config_iface
                and str(vpp_iface.l2_address) != config_iface["mac"]
            ):
                cli = f"set interface mac address {config_ifname} {config_iface['mac']}"
                self.cli["sync"].append(cli)
            elif bondmac and "lcp" in config_iface:
                ## TODO(pim) - Ensure LCP has the same MAC as the BondEthernet
                ## VPP, when creating a BondEthernet, will give it an ephemeral MAC. Then, when the
                ## first member is enslaved, the MAC address changes to that of the first member.
                ## However, LinuxCP does not propagate this change to the Linux side (because there
                ## is no API callback for MAC address changes). To ensure consistency, every time we
                ## sync members, we ought to ensure the Linux device has the same MAC as its BondEthernet.
                cli = (
                    f"comment {{ ip link set {config_iface['lcp']} address {bondmac} }}"
                )
                self.cli["sync"].append(cli)
        return True

    def sync_bridgedomains(self):
        """Synchronize the VPP Dataplane configuration for bridgedomains"""
        for ifname in bridgedomain.get_bridgedomains(self.cfg):
            instance = int(ifname[2:])
            if instance in self.vpp.cache["bridgedomains"]:
                vpp_bridge = self.vpp.cache["bridgedomains"][instance]
                bvi_sw_if_index = vpp_bridge.bvi_sw_if_index
                bridge_sw_if_index_list = [
                    x.sw_if_index for x in vpp_bridge.sw_if_details
                ]
                bridge_members = [
                    self.vpp.cache["interfaces"][x].interface_name
                    for x in bridge_sw_if_index_list
                    if x in self.vpp.cache["interfaces"]
                ]
            else:
                ## New BridgeDomain
                vpp_bridge = None
                bvi_sw_if_index = -1
                bridge_members = []

            config_bridge_ifname, config_bridge_iface = bridgedomain.get_by_name(
                self.cfg, f"bd{int(instance)}"
            )
            if vpp_bridge:
                # Sync settings on existing bridge. create_bridgedomain() will have set them for new bridges.
                settings = bridgedomain.get_settings(self.cfg, config_bridge_ifname)
                if settings["learn"] != vpp_bridge.learn:
                    cli = f"set bridge-domain learn {int(instance)}"
                    if not settings["learn"]:
                        cli += " disable"
                    self.cli["sync"].append(cli)
                if settings["unicast-forward"] != vpp_bridge.forward:
                    cli = f"set bridge-domain forward {int(instance)}"
                    if not settings["unicast-forward"]:
                        cli += " disable"
                    self.cli["sync"].append(cli)
                if settings["unicast-flood"] != vpp_bridge.flood:
                    cli = f"set bridge-domain flood {int(instance)}"
                    if not settings["unicast-flood"]:
                        cli += " disable"
                    self.cli["sync"].append(cli)
                if settings["unknown-unicast-flood"] != vpp_bridge.uu_flood:
                    cli = f"set bridge-domain uu-flood {int(instance)}"
                    if not settings["unknown-unicast-flood"]:
                        cli += " disable"
                    self.cli["sync"].append(cli)
                if settings["arp-termination"] != vpp_bridge.arp_term:
                    cli = f"set bridge-domain arp term {int(instance)}"
                    if not settings["arp-termination"]:
                        cli += " disable"
                    self.cli["sync"].append(cli)
                if settings["arp-unicast-forward"] != vpp_bridge.arp_ufwd:
                    cli = f"set bridge-domain arp-ufwd {int(instance)}"
                    if not settings["arp-unicast-forward"]:
                        cli += " disable"
                    self.cli["sync"].append(cli)
                if settings["mac-age-minutes"] != vpp_bridge.mac_age:
                    cli = f"set bridge-domain mac-age {int(instance)} {int(settings['mac-age-minutes'])}"
                    self.cli["sync"].append(cli)

            if "bvi" in config_bridge_iface:
                bviname = config_bridge_iface["bvi"]
                if not (
                    bviname in self.vpp.cache["interface_names"]
                    and self.vpp.cache["interface_names"][bviname].sw_if_index
                    == bvi_sw_if_index
                ):
                    cli = f"set interface l2 bridge {bviname} {int(instance)} bvi"
                    self.cli["sync"].append(cli)

            if "interfaces" in config_bridge_iface:
                for member_ifname in config_bridge_iface["interfaces"]:
                    member_ifname, _member_iface = interface.get_by_name(
                        self.cfg, member_ifname
                    )
                    if not member_ifname in bridge_members:
                        cli = f"set interface l2 bridge {member_ifname} {int(instance)}"
                        self.cli["sync"].append(cli)
                        operation = "disable"
                        if interface.is_qinx(self.cfg, member_ifname):
                            operation = "pop 2"
                        elif interface.is_sub(self.cfg, member_ifname):
                            operation = "pop 1"
                        cli = (
                            f"set interface l2 tag-rewrite {member_ifname} {operation}"
                        )
                        self.cli["sync"].append(cli)
        return True

    def sync_l2xcs(self):
        """Synchronize the VPP Dataplane configuration for L2 cross connects"""
        for ifname in interface.get_l2xc_interfaces(self.cfg):
            config_rx_ifname, config_rx_iface = interface.get_by_name(self.cfg, ifname)
            config_tx_ifname, _config_tx_iface = interface.get_by_name(
                self.cfg, config_rx_iface["l2xc"]
            )
            vpp_rx_iface = None
            vpp_tx_iface = None
            if config_rx_ifname in self.vpp.cache["interface_names"]:
                vpp_rx_iface = self.vpp.cache["interface_names"][config_rx_ifname]
            if config_tx_ifname in self.vpp.cache["interface_names"]:
                vpp_tx_iface = self.vpp.cache["interface_names"][config_tx_ifname]

            l2xc_changed = False
            if not vpp_rx_iface or not vpp_tx_iface:
                l2xc_changed = True
            elif not vpp_rx_iface.sw_if_index in self.vpp.cache["l2xcs"]:
                l2xc_changed = True
            elif (
                not vpp_tx_iface.sw_if_index
                == self.vpp.cache["l2xcs"][vpp_rx_iface.sw_if_index].tx_sw_if_index
            ):
                l2xc_changed = True

            if l2xc_changed:
                cli = f"set interface l2 xconnect {config_rx_ifname} {config_tx_ifname}"
                self.cli["sync"].append(cli)

                operation = "disable"
                if interface.is_qinx(self.cfg, config_rx_ifname):
                    operation = "pop 2"
                elif interface.is_sub(self.cfg, config_rx_ifname):
                    operation = "pop 1"
                cli = f"set interface l2 tag-rewrite {config_rx_ifname} {operation}"
                self.cli["sync"].append(cli)
        return True

    def sync_mtu_direction(self, shrink=True):
        """Synchronize the VPP Dataplane packet MTU, where 'shrink' determines the
        direction (if shrink is True, go from inner-most (QinQ) to outer-most (untagged),
        and the other direction if shrink is False"""
        if shrink:
            tag_list = [2, 1, 0]
        else:
            tag_list = [0, 1, 2]

        for numtags in tag_list:
            for ifname in interface.get_interfaces(self.cfg) + loopback.get_loopbacks(
                self.cfg
            ):
                if numtags == 0 and interface.is_sub(self.cfg, ifname):
                    continue
                if numtags == 1 and not interface.is_sub(self.cfg, ifname):
                    continue
                if numtags == 1 and interface.is_qinx(self.cfg, ifname):
                    continue
                if numtags == 2 and not interface.is_qinx(self.cfg, ifname):
                    continue
                config_mtu = 1500
                vpp_mtu = 9000
                if ifname.startswith("loop"):
                    if ifname in self.vpp.cache["interface_names"]:
                        vpp_mtu = self.vpp.cache["interface_names"][ifname].mtu[0]
                    vpp_ifname, config_iface = loopback.get_by_name(self.cfg, ifname)
                    if "mtu" in config_iface:
                        config_mtu = config_iface["mtu"]
                else:
                    if numtags > 0:
                        vpp_mtu = 0
                    if ifname in self.vpp.cache["interface_names"]:
                        vpp_mtu = self.vpp.cache["interface_names"][ifname].mtu[0]
                    vpp_ifname, config_iface = interface.get_by_name(self.cfg, ifname)
                    config_mtu = interface.get_mtu(self.cfg, ifname)

                if shrink and config_mtu < vpp_mtu:
                    cli = f"set interface mtu packet {int(config_mtu)} {vpp_ifname}"
                    self.cli["sync"].append(cli)
                elif not shrink and config_mtu > vpp_mtu:
                    cli = f"set interface mtu packet {int(config_mtu)} {vpp_ifname}"
                    self.cli["sync"].append(cli)
        return True

    def sync_link_mtu_direction(self, shrink=True):
        """Synchronize the VPP Dataplane max frame size (link MTU), where 'shrink' determines the
        direction (if shrink is True, go from inner-most (QinQ) to outer-most (untagged),
        and the other direction if shrink is False"""
        for _idx, vpp_iface in self.vpp.cache["interfaces"].items():
            if vpp_iface.sub_number_of_tags != 0:
                continue
            if vpp_iface.interface_dev_type in ["local", "Loopback", "VXLAN", "virtio"]:
                continue

            _config_ifname, config_iface = interface.get_by_name(
                self.cfg, vpp_iface.interface_name
            )
            if not config_iface:
                self.logger.warning(
                    f"Interface {vpp_iface.interface_name} exists in VPP but not in config, this is dangerous"
                )
                continue
            if not interface.is_phy(self.cfg, vpp_iface.interface_name):
                continue
            config_mtu = interface.get_mtu(self.cfg, vpp_iface.interface_name)

            if (
                vpp_iface.interface_dev_type == "bond"
                and vpp_iface.link_mtu < config_mtu
            ):
                self.logger.warning(
                    f"{vpp_iface.interface_name} has a Max Frame Size ({vpp_iface.link_mtu}) "
                    "lower than desired MTU ({config_mtu}), this is unsupported"
                )
                continue

            if shrink and config_mtu < vpp_iface.link_mtu:
                ## If the interface is up, temporarily down it in order to change the Max Frame Size
                if vpp_iface.flags & 1:  # IF_STATUS_API_FLAG_ADMIN_UP
                    cli = f"set interface state {vpp_iface.interface_name} down"
                    self.cli["sync"].append(cli)

                cli = f"set interface mtu {int(config_mtu)} {vpp_iface.interface_name}"
                self.cli["sync"].append(cli)

                if vpp_iface.flags & 1:  # IF_STATUS_API_FLAG_ADMIN_UP
                    cli = f"set interface state {vpp_iface.interface_name} up"
                    self.cli["sync"].append(cli)
            elif not shrink and config_mtu > vpp_iface.link_mtu:
                ## If the interface is up, temporarily down it in order to change the Max Frame Size
                if vpp_iface.flags & 1:  # IF_STATUS_API_FLAG_ADMIN_UP
                    cli = f"set interface state {vpp_iface.interface_name} down"
                    self.cli["sync"].append(cli)

                cli = f"set interface mtu {int(config_mtu)} {vpp_iface.interface_name}"
                self.cli["sync"].append(cli)

                if vpp_iface.flags & 1:  # IF_STATUS_API_FLAG_ADMIN_UP
                    cli = f"set interface state {vpp_iface.interface_name} up"
                    self.cli["sync"].append(cli)
        return True

    def sync_mtu(self):
        """Synchronize the VPP Dataplane configuration for interface MTU"""
        ret = True
        if not self.sync_link_mtu_direction(shrink=False):
            self.logger.warning(
                "Could not sync growing interface Max Frame Size in VPP"
            )
            ret = False
        if not self.sync_link_mtu_direction(shrink=True):
            self.logger.warning(
                "Could not sync shrinking interface Max Frame Size in VPP"
            )
            ret = False
        if not self.sync_mtu_direction(shrink=True):
            self.logger.warning("Could not sync shrinking interface MTU in VPP")
            ret = False
        if not self.sync_mtu_direction(shrink=False):
            self.logger.warning("Could not sync growing interface MTU in VPP")
            ret = False
        return ret

    def sync_addresses(self):
        """Synchronize the VPP Dataplane configuration for interface addresses"""
        for ifname in interface.get_interfaces(self.cfg) + loopback.get_loopbacks(
            self.cfg
        ):
            config_addresses = []
            vpp_addresses = []
            if ifname.startswith("loop"):
                vpp_ifname, config_iface = loopback.get_by_name(self.cfg, ifname)
                if "addresses" in config_iface:
                    config_addresses = config_iface["addresses"]
            else:
                vpp_ifname, config_iface = interface.get_by_name(self.cfg, ifname)
                if "addresses" in config_iface:
                    config_addresses = config_iface["addresses"]
            if vpp_ifname in self.vpp.cache["interface_names"]:
                sw_if_index = self.vpp.cache["interface_names"][vpp_ifname].sw_if_index
                if sw_if_index in self.vpp.cache["interface_addresses"]:
                    vpp_addresses = [
                        str(x)
                        for x in self.vpp.cache["interface_addresses"][sw_if_index]
                    ]
            for addr in config_addresses:
                if addr in vpp_addresses:
                    continue
                cli = f"set interface ip address {vpp_ifname} {addr}"
                self.cli["sync"].append(cli)
        return True

    def sync_admin_state(self):
        """Synchronize the VPP Dataplane configuration for interface admin state"""
        for ifname in interface.get_interfaces(self.cfg) + loopback.get_loopbacks(
            self.cfg
        ):
            if ifname.startswith("loop"):
                vpp_ifname, _config_iface = loopback.get_by_name(self.cfg, ifname)
                config_admin_state = 1
            else:
                vpp_ifname, _config_iface = interface.get_by_name(self.cfg, ifname)
                config_admin_state = interface.get_admin_state(self.cfg, ifname)

            vpp_admin_state = 0
            if vpp_ifname in self.vpp.cache["interface_names"]:
                vpp_admin_state = (
                    self.vpp.cache["interface_names"][vpp_ifname].flags & 1
                )  # IF_STATUS_API_FLAG_ADMIN_UP
            if config_admin_state == vpp_admin_state:
                continue
            state = "up"
            if config_admin_state == 0:
                state = "down"
            cli = f"set interface state {vpp_ifname} {state}"
            self.cli["sync"].append(cli)
        return True

    def write(self, outfile, emit_ok=False):
        """Emit the CLI contents to stdout (if outfile=='-') or a named file otherwise.
        If the 'emit_ok' flag is False, emit a warning at the top and bottom of the file.
        """
        # Assemble the intended output into a list
        output = []
        if not emit_ok:
            output.append(
                "comment { vppcfg: Planning failed, be careful with this output! }"
            )

        for phase in ["prune", "create", "sync"]:
            ncount = len(self.cli[phase])
            if ncount > 0:
                output.append(
                    f"comment {{ vppcfg {phase}: {ncount} CLI statement(s) follow }}"
                )
                output.extend(self.cli[phase])

        if not emit_ok:
            output.append(
                "comment { vppcfg: Planning failed, be careful with this output! }"
            )

        # Emit the output list to stdout or a file
        if outfile and outfile == "-":
            file = sys.stdout
            outfile = "(stdout)"
        else:
            file = open(outfile, "w", encoding="utf-8")
        if len(output) > 0:
            print("\n".join(output), file=file)
        if file is not sys.stdout:
            file.close()

        self.logger.info(f"Wrote {len(output)} lines to {outfile}")

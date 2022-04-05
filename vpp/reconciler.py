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
import sys
import logging
import config.loopback as loopback
import config.interface as interface
import config.bondethernet as bondethernet
import config.bridgedomain as bridgedomain
import config.vxlan_tunnel as vxlan_tunnel
import config.lcp as lcp
from vpp.vppapi import VPPApi

class Reconciler():
    def __init__(self, cfg):
        self.logger = logging.getLogger('vppcfg.reconciler')
        self.logger.addHandler(logging.NullHandler())

        self.vpp = VPPApi()
        self.cfg = cfg

        ## List of CLI calls emitted during the prune, create and sync phases.
        self.cli = { "prune": [], "create": [], "sync": [] }

    def __del__(self):
        self.vpp.disconnect()

    def lcps_exist_with_lcp_enabled(self):
        """ Returns False if there are LCPs defined in the configuration, but LinuxCP
        functionality is not enabled in VPP. """
        if not lcp.get_lcps(self.cfg):
            return True
        return self.vpp.lcp_enabled

    def phys_exist_in_vpp(self):
        """ Return True if all PHYs in the config exist as physical interface names
        in VPP. Return False otherwise."""

        ret = True
        for ifname in interface.get_phys(self.cfg):
            if not ifname in self.vpp.cache['interface_names']:
                self.logger.warning("Interface %s does not exist in VPP" % ifname)
                ret = False
        return ret

    def phys_exist_in_config(self):
        """ Return True if all interfaces in VPP exist as physical interface names
        in the config. Return False otherwise."""

        ret = True
        for ifname in self.vpp.get_phys():
            if not ifname in interface.get_interfaces(self.cfg):
                self.logger.warning("Interface %s does not exist in the config" % ifname)
                ret = False
        return ret

    def vpp_readconfig(self):
        if not self.vpp.readconfig():
            self.logger.error("Could not (re)read config from VPP")
            return False
        return True

    def prune(self):
        """ Remove all objects from VPP that do not occur in the config. For an indepth explanation
            of how and why this particular pruning order is chosen, see README.md section on
            Reconciling. """
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
        """ Remove all addresses from interface ifname, except those in address_list,
            which may be an empty list, in which case all addresses are removed.
        """
        idx = self.vpp.cache['interface_names'][ifname].sw_if_index
        removed_addresses = []
        for a in self.vpp.cache['interface_addresses'][idx]:
            if not a in address_list:
                cli = "set interface ip address del %s %s" % (ifname, a)
                self.cli['prune'].append(cli);
                removed_addresses.append(a)
            else:
                self.logger.debug("Address OK: %s %s" % (ifname, a))
        for a in removed_addresses:
            self.vpp.cache['interface_addresses'][idx].remove(a)

    def prune_loopbacks(self):
        """ Remove loopbacks from VPP, if they do not occur in the config. """
        removed_interfaces=[]
        for numtags in [ 2, 1, 0 ]:
            for idx, vpp_iface in self.vpp.cache['interfaces'].items():
                if vpp_iface.interface_dev_type!='Loopback':
                    continue
                if vpp_iface.sub_number_of_tags != numtags:
                    continue
                config_ifname, config_iface = loopback.get_by_name(self.cfg, vpp_iface.interface_name)
                if not config_iface:
                    self.prune_addresses(vpp_iface.interface_name, [])
                    if numtags == 0:
                        cli = "delete loopback interface intfc %s" % (vpp_iface.interface_name)
                        self.cli['prune'].append(cli);
                        removed_interfaces.append(vpp_iface.interface_name)
                    else:
                        cli="delete sub %s" % (vpp_iface.interface_name)
                        self.cli['prune'].append(cli);
                        removed_interfaces.append(vpp_iface.interface_name)
                    continue
                self.logger.debug("Loopback OK: %s" % (vpp_iface.interface_name))
                addresses = []
                if 'addresses' in config_iface:
                    addresses = config_iface['addresses']
                self.prune_addresses(vpp_iface.interface_name, addresses)

        for ifname in removed_interfaces:
            self.vpp.cache_remove_interface(ifname)

        return True


    def prune_bridgedomains(self):
        """ Remove bridge-domains from VPP, if they do not occur in the config. If any interfaces are
            found in to-be removed bridge-domains, they are returned to L3 mode, and tag-rewrites removed. """
        for idx, bridge in self.vpp.cache['bridgedomains'].items():
            bridgename = "bd%d" % idx
            config_ifname, config_iface = bridgedomain.get_by_name(self.cfg, bridgename)
            members = []
            if not config_iface:
                for member in bridge.sw_if_details:
                    if member.sw_if_index == bridge.bvi_sw_if_index:
                        continue
                    member_iface = self.vpp.cache['interfaces'][member.sw_if_index]
                    member_ifname = member_iface.interface_name
                    if member_iface.sub_id > 0:
                        cli="set interface l2 tag-rewrite %s disable" % (member_ifname)
                        self.cli['prune'].append(cli);
                    cli="set interface l3 %s" % (member_ifname)
                    self.cli['prune'].append(cli);
                if bridge.bvi_sw_if_index in self.vpp.cache['interfaces']:
                    bviname = self.vpp.cache['interfaces'][bridge.bvi_sw_if_index].interface_name
                    cli="set interface l3 %s" % (bviname)
                    self.cli['prune'].append(cli);
                cli="create bridge-domain %d del" % (idx)
                self.cli['prune'].append(cli);
            else:
                self.logger.debug("BridgeDomain OK: %s" % (bridgename))
                for member in bridge.sw_if_details:
                    member_ifname = self.vpp.cache['interfaces'][member.sw_if_index].interface_name
                    if 'members' in config_iface and member_ifname in config_iface['members']:
                        if interface.is_sub(self.cfg, member_ifname):
                            cli="set interface l2 tag-rewrite %s disable" % (member_ifname)
                            self.cli['prune'].append(cli);
                        cli="set interface l3 %s" % (member_ifname)
                        self.cli['prune'].append(cli);
                if 'bvi' in config_iface and bridge.bvi_sw_if_index in self.vpp.cache['interfaces']:
                    bviname = self.vpp.cache['interfaces'][bridge.bvi_sw_if_index].interface_name
                    if bviname != config_iface['bvi']:
                        cli="set interface l3 %s" % (bviname)
                        self.cli['prune'].append(cli);

        return True

    def prune_l2xcs(self):
        """ Remove all L2XC source interfaces from VPP, if they do not occur in the config. If they occur,
            but are crossconnected to a different interface name, also remove them. Interfaces are put
            back into L3 mode, and their tag-rewrites removed. """
        removed_l2xcs=[]
        for idx, l2xc in self.vpp.cache['l2xcs'].items():
            vpp_rx_ifname = self.vpp.cache['interfaces'][l2xc.rx_sw_if_index].interface_name
            config_rx_ifname, config_rx_iface = interface.get_by_name(self.cfg, vpp_rx_ifname)
            if not config_rx_ifname:
                if self.vpp.cache['interfaces'][l2xc.rx_sw_if_index].sub_id > 0:
                    cli="set interface l2 tag-rewrite %s disable" % (vpp_rx_ifname)
                    self.cli['prune'].append(cli);
                cli="set interface l3 %s" % (vpp_rx_ifname)
                self.cli['prune'].append(cli);
                removed_l2xcs.append(vpp_rx_ifname)
                continue

            if not interface.is_l2xc_interface(self.cfg, config_rx_ifname):
                if interface.is_sub(self.cfg, config_rx_ifname):
                    cli="set interface l2 tag-rewrite %s disable" % (vpp_rx_ifname)
                    self.cli['prune'].append(cli);
                cli="set interface l3 %s" % (vpp_rx_ifname)
                self.cli['prune'].append(cli);
                removed_l2xcs.append(vpp_rx_ifname)
                continue
            vpp_tx_ifname = self.vpp.cache['interfaces'][l2xc.tx_sw_if_index].interface_name
            if vpp_tx_ifname != config_rx_iface['l2xc']:
                if interface.is_sub(self.cfg, config_rx_ifname):
                    cli="set interface l2 tag-rewrite %s disable" % (vpp_rx_ifname)
                    self.cli['prune'].append(cli);
                cli="set interface l3 %s" % (vpp_rx_ifname)
                self.cli['prune'].append(cli);
                removed_l2xcs.append(vpp_rx_ifname)
                continue
            self.logger.debug("L2XC OK: %s -> %s" % (vpp_rx_ifname, vpp_tx_ifname))
        for l2xc in removed_l2xcs:
            self.vpp.cache_remove_l2xc(l2xc)
        return True

    def prune_bondethernets(self):
        """ Remove all BondEthernets from VPP, if they are not in the config. If the bond has members,
            remove those from the bond before removing the bond. """
        removed_interfaces=[]
        removed_bondethernet_members=[]
        for idx, bond in self.vpp.cache['bondethernets'].items():
            vpp_ifname = bond.interface_name
            config_ifname, config_iface = bondethernet.get_by_name(self.cfg, vpp_ifname)
            if not config_iface:
                self.prune_addresses(vpp_ifname, [])
                for member in self.vpp.cache['bondethernet_members'][idx]:
                    member_ifname = self.vpp.cache['interfaces'][member].interface_name
                    cli="bond del %s" % (member_ifname)
                    self.cli['prune'].append(cli);
                    removed_bondethernet_members.append(member_ifname)
                cli="delete bond %s" % (vpp_ifname)
                self.cli['prune'].append(cli);
                removed_interfaces.append(vpp_ifname)
                continue
            for member in self.vpp.cache['bondethernet_members'][idx]:
                member_ifname = self.vpp.cache['interfaces'][member].interface_name
                if 'interfaces' in config_iface and not member_ifname in config_iface['interfaces']:
                    cli="bond del %s" % (member_ifname)
                    self.cli['prune'].append(cli);
                    removed_bondethernet_members.append(member_ifname)
            addresses = []
            if 'addresses' in config_iface:
                addresses = config_iface['addresses']
            self.prune_addresses(vpp_ifname, addresses)
            self.logger.debug("BondEthernet OK: %s" % (vpp_ifname))

        for ifname in removed_bondethernet_members:
            self.vpp.cache_remove_bondethernet_member(ifname)

        for ifname in removed_interfaces:
            self.vpp.cache_remove_interface(ifname)

        return True

    def prune_vxlan_tunnels(self):
        """ Remove all VXLAN Tunnels from VPP, if they are not in the config. If they are in the config
            but with differing attributes, remove them also. """
        removed_interfaces=[]
        for idx, vpp_vxlan in self.vpp.cache['vxlan_tunnels'].items():
            vpp_ifname = self.vpp.cache['interfaces'][idx].interface_name
            config_ifname, config_iface = vxlan_tunnel.get_by_name(self.cfg, vpp_ifname)
            if not config_iface:
                self.prune_addresses(vpp_ifname, [])
                cli="create vxlan tunnel instance %d src %s dst %s vni %d del" % (vpp_vxlan.instance, 
                    vpp_vxlan.src_address, vpp_vxlan.dst_address, vpp_vxlan.vni)
                self.cli['prune'].append(cli);
                removed_interfaces.append(vpp_ifname)
                continue
            if config_iface['local'] != str(vpp_vxlan.src_address) or config_iface['remote'] != str(vpp_vxlan.dst_address) or config_iface['vni'] != vpp_vxlan.vni:
                cli="create vxlan tunnel instance %d src %s dst %s vni %d del" % (vpp_vxlan.instance, 
                    vpp_vxlan.src_address, vpp_vxlan.dst_address, vpp_vxlan.vni)
                self.cli['prune'].append(cli);
                removed_interfaces.append(vpp_ifname)
                continue
            config_ifname, config_iface = interface.get_by_name(self.cfg, vpp_ifname)
            if config_iface:
                addresses = []
                if 'addresses' in config_iface:
                    addresses = config_iface['addresses']
                self.prune_addresses(vpp_ifname, addresses)
            self.logger.debug("VXLAN Tunnel OK: %s" % (vpp_ifname))

        for ifname in removed_interfaces:
            self.vpp.cache_remove_vxlan_tunnel(ifname)
            self.vpp.cache_remove_interface(ifname)

        return True

    def __tap_is_lcp(self, sw_if_index):
        """ Returns True if the given sw_if_index is a TAP interface belonging to an LCP,
            or False otherwise."""
        if not sw_if_index in self.vpp.cache['interfaces']:
            return False

        vpp_iface = self.vpp.cache['interfaces'][sw_if_index]
        if not vpp_iface.interface_dev_type=="virtio":
            return False

        match = False
        for idx, lcp in self.vpp.cache['lcps'].items():
            if vpp_iface.sw_if_index == lcp.host_sw_if_index:
                match = True
        return match

    def prune_sub_interfaces(self):
        """ Remove interfaces from VPP if they are not in the config, or if their encapsulation is different.
            Start with inner-most (QinQ/QinAD), then Dot1Q/Dot1AD."""
        removed_interfaces=[]
        for numtags in [ 2, 1 ]:
            for vpp_ifname in self.vpp.get_sub_interfaces():
                vpp_iface = self.vpp.cache['interface_names'][vpp_ifname]
                if vpp_iface.sub_number_of_tags != numtags:
                    continue

                if self.__tap_is_lcp(vpp_iface.sw_if_index):
                    continue

                config_ifname, config_iface = interface.get_by_name(self.cfg, vpp_ifname)
                if not config_iface:
                    self.prune_addresses(vpp_ifname, [])
                    cli="delete sub %s" % (vpp_ifname)
                    self.cli['prune'].append(cli);
                    removed_interfaces.append(vpp_ifname)
                    continue
                config_encap = interface.get_encapsulation(self.cfg, vpp_ifname)
                vpp_encap = self.__get_encapsulation(vpp_iface)
                if config_encap != vpp_encap:
                    self.prune_addresses(vpp_ifname, [])
                    cli="delete sub %s" % (vpp_ifname)
                    self.cli['prune'].append(cli);
                    removed_interfaces.append(vpp_ifname)
                    continue
                addresses = []
                if 'addresses' in config_iface:
                    addresses = config_iface['addresses']
                self.prune_addresses(vpp_ifname, addresses)
                self.logger.debug("Sub Interface OK: %s" % (vpp_ifname))

        for ifname in removed_interfaces:
            self.vpp.cache_remove_interface(ifname)

        return True

    def prune_phys(self):
        """ Set default MTU and remove IPs for PHYs that are not in the config. """
        for vpp_ifname in self.vpp.get_phys():
            vpp_iface = self.vpp.cache['interface_names'][vpp_ifname]
            config_ifname, config_iface = interface.get_by_name(self.cfg, vpp_ifname)
            if not config_iface:
                ## Interfaces were sent DOWN in the prune_admin_state() step previously
                self.prune_addresses(vpp_ifname, [])
                if vpp_iface.link_mtu != 9000:
                    cli="set interface mtu 9000 %s" % (vpp_ifname)
                    self.cli['prune'].append(cli);
                continue
            addresses = []
            if 'addresses' in config_iface:
                addresses = config_iface['addresses']
            self.prune_addresses(vpp_ifname, addresses)
            self.logger.debug("Interface OK: %s" % (vpp_ifname))
        return True

    def __parent_iface_by_encap(self, sup_sw_if_index, outer, dot1ad=True):
        """ Returns the sw_if_index of an interface on a given super_sw_if_index with given dot1q/dot1ad outer and inner-dot1q=0,
            in other words the intermediary Dot1Q/Dot1AD belonging to a QinX interface. If the interface doesn't exist, None is
            returned. """
        for idx, iface in self.vpp.cache['interfaces'].items():
            if iface.sup_sw_if_index != sup_sw_if_index:
                continue
            if iface.sub_inner_vlan_id > 0:
                continue
            if dot1ad and (iface.sub_if_flags&8) and iface.sub_outer_vlan_id == outer:
                self.logger.debug("match: %s (dot1ad)" % iface.interface_name)
                return idx
            if not dot1ad and not (iface.sub_if_flags&8) and iface.sub_outer_vlan_id == outer:
                self.logger.debug("match: %s (dot1q)" % iface.interface_name)
                return idx
        return None

    def __get_encapsulation(self, iface):
        """ Return a dictionary-based encapsulation of the sub-interface, which helps comparing them to the same object
            returned by config.interface.get_encapsulation(). """
        if iface.sub_if_flags&8:
            dot1ad = iface.sub_outer_vlan_id
            dot1q = 0
        else:
            dot1q = iface.sub_outer_vlan_id
            dot1ad = 0
        inner_dot1q = iface.sub_inner_vlan_id
        exact_match = iface.sub_if_flags&16
        return { "dot1q": int(dot1q),
                 "dot1ad": int(dot1ad),
                 "inner-dot1q": int(inner_dot1q),
                 "exact-match": bool(exact_match) }

    def prune_lcps(self):
        """ Remove LCPs which are not in the configuration, starting with QinQ/QinAD interfaces, then Dot1Q/Dot1AD,
            and finally PHYs/BondEthernets/Tunnels/Loopbacks. For QinX, special care is taken to ensure that
            their intermediary interface exists, and has the correct encalsulation. If the intermediary interface
            changed, the QinX LCP is removed. The same is true for Dot1Q/Dot1AD interfaces: if their encapsulation
            has changed, we will have to re-create the underlying sub-interface, so the LCP has to be removed.

            Order is important: destroying an LCP of a PHY will invalidate its Dot1Q/Dot1AD as well as their
            downstream children in Linux.
        """
        lcps = self.vpp.cache['lcps']

        removed_lcps = []
        for numtags in [ 2, 1, 0 ]:
            for idx, lcp in lcps.items():
                vpp_iface = self.vpp.cache['interfaces'][lcp.phy_sw_if_index]
                if vpp_iface.sub_number_of_tags != numtags:
                    continue
                if vpp_iface.interface_dev_type=='Loopback':
                    config_ifname, config_iface = loopback.get_by_lcp_name(self.cfg, lcp.host_if_name)
                else:
                    config_ifname, config_iface = interface.get_by_lcp_name(self.cfg, lcp.host_if_name)
                if not config_iface:
                    ## Interface doesn't exist in the config
                    cli="lcp delete %s" % (vpp_iface.interface_name)
                    self.cli['prune'].append(cli);
                    removed_lcps.append(lcp.host_if_name)
                    continue
                if not 'lcp' in config_iface:
                    ## Interface doesn't have an LCP
                    cli="lcp delete %s" % (vpp_iface.interface_name)
                    self.cli['prune'].append(cli);
                    removed_lcps.append(lcp.host_if_name)
                    continue
                if vpp_iface.sub_number_of_tags == 2:
                    vpp_parent_idx = self.__parent_iface_by_encap(vpp_iface.sup_sw_if_index, vpp_iface.sub_outer_vlan_id, vpp_iface.sub_if_flags&8)
                    vpp_parent_iface = self.vpp.cache['interfaces'][vpp_parent_idx]
                    parent_lcp = lcps[vpp_parent_iface.sw_if_index]
                    config_parent_ifname, config_parent_iface = interface.get_by_lcp_name(self.cfg, parent_lcp.host_if_name)
                    if not config_parent_iface:
                        ## QinX's parent doesn't exist in the config
                        cli="lcp delete %s" % (vpp_iface.interface_name)
                        self.cli['prune'].append(cli);
                        removed_lcps.append(lcp.host_if_name)
                        continue
                    if not 'lcp' in config_parent_iface:
                        ## QinX's parent doesn't have an LCP
                        cli="lcp delete %s" % (vpp_iface.interface_name)
                        self.cli['prune'].append(cli);
                        removed_lcps.append(lcp.host_if_name)
                        continue
                    if parent_lcp.host_if_name != config_parent_iface['lcp']:
                        ## QinX's parent LCP name mismatch
                        cli="lcp delete %s" % (vpp_iface.interface_name)
                        self.cli['prune'].append(cli);
                        removed_lcps.append(lcp.host_if_name)
                        continue
                    config_parent_encap = interface.get_encapsulation(self.cfg, config_parent_ifname)
                    vpp_parent_encap = self.__get_encapsulation(vpp_parent_iface)
                    if config_parent_encap != vpp_parent_encap:
                        ## QinX's parent encapsulation mismatch
                        cli="lcp delete %s" % (vpp_iface.interface_name)
                        self.cli['prune'].append(cli);
                        removed_lcps.append(lcp.host_if_name)
                        continue

                if vpp_iface.sub_number_of_tags > 1:
                    config_encap = interface.get_encapsulation(self.cfg, config_ifname)
                    vpp_encap = self.__get_encapsulation(vpp_iface)
                    if config_encap != vpp_encap:
                        ## Encapsulation mismatch
                        cli="lcp delete %s" % (vpp_iface.interface_name)
                        self.cli['prune'].append(cli);
                        removed_lcps.append(lcp.host_if_name)
                        continue

                if vpp_iface.interface_dev_type=='Loopback':
                    ## Loopbacks will not have a PHY to check.
                    continue

                phy_lcp = lcps[vpp_iface.sup_sw_if_index]
                config_phy_ifname, config_phy_iface = interface.get_by_lcp_name(self.cfg, phy_lcp.host_if_name)
                if not config_phy_iface:
                    ## Phy doesn't exist in the config
                    cli="lcp delete %s" % (vpp_iface.interface_name)
                    self.cli['prune'].append(cli);
                    removed_lcps.append(lcp.host_if_name)
                    continue
                if not 'lcp' in config_phy_iface:
                    ## Phy doesn't have an LCP
                    cli="lcp delete %s" % (vpp_iface.interface_name)
                    self.cli['prune'].append(cli);
                    removed_lcps.append(lcp.host_if_name)
                    continue
                if phy_lcp.host_if_name != config_phy_iface['lcp']:
                    ## Phy LCP name mismatch
                    cli="lcp delete %s" % (vpp_iface.interface_name)
                    self.cli['prune'].append(cli);
                    removed_lcps.append(lcp.host_if_name)
                    continue

                self.logger.debug("LCP OK: %s -> (vpp=%s, config=%s)" % (lcp.host_if_name, vpp_iface.interface_name, config_ifname))

        for lcpname in removed_lcps:
            self.vpp.cache_remove_lcp(lcpname)
        return True

    def prune_admin_state(self):
        """ Set admin-state down for all interfaces that are not in the config. """
        for ifname in self.vpp.get_qinx_interfaces() + self.vpp.get_dot1x_interfaces() + self.vpp.get_bondethernets() + self.vpp.get_phys() + self.vpp.get_vxlan_tunnels() + self.vpp.get_loopbacks():
            if not ifname in interface.get_interfaces(self.cfg) + loopback.get_loopbacks(self.cfg):
                vpp_iface = self.vpp.cache['interface_names'][ifname]

                if self.__tap_is_lcp(vpp_iface.sw_if_index):
                    continue

                if vpp_iface.flags & 1: # IF_STATUS_API_FLAG_ADMIN_UP
                    cli="set interface state %s down" % (ifname)
                    self.cli['prune'].append(cli);

        return True

    def create(self):
        """ Create all objects in VPP that occur in the config but not in VPP. For an indepth
            explanation of how and why this particular pruning order is chosen, see README.md
            section on Reconciling. """
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
        for ifname in loopback.get_loopbacks(self.cfg):
            if ifname in self.vpp.cache['interface_names']:
                continue
            instance = int(ifname[4:])
            cli="create loopback interface instance %d" % (instance)
            self.cli['create'].append(cli);
        return True

    def create_bondethernets(self):
        for ifname in bondethernet.get_bondethernets(self.cfg):
            if ifname in self.vpp.cache['interface_names']:
                continue
            ifname, iface = bondethernet.get_by_name(self.cfg, ifname)
            instance = int(ifname[12:])
            cli="create bond mode lacp load-balance l34 id %d" % (instance)
            self.cli['create'].append(cli);
        return True

    def create_vxlan_tunnels(self):
        for ifname in vxlan_tunnel.get_vxlan_tunnels(self.cfg):
            if ifname in self.vpp.cache['interface_names']:
                continue
            ifname, iface = vxlan_tunnel.get_by_name(self.cfg, ifname)
            instance = int(ifname[12:])
            cli="create vxlan tunnel src %s dst %s instance %d vni %d decap-next l2" % (
                iface['local'], iface['remote'], instance, iface['vni'])
            self.cli['create'].append(cli);
        return True

    def create_sub_interfaces(self):
        ## First create 1-tag (Dot1Q/Dot1AD), and then create 2-tag (Qin*) sub-interfaces
        for do_qinx in [False, True]:
            for ifname in interface.get_sub_interfaces(self.cfg):
                if not do_qinx == interface.is_qinx(self.cfg, ifname):
                    continue

                ifname, iface = interface.get_by_name(self.cfg, ifname)
                if ifname in self.vpp.cache['interface_names']:
                    continue

                ## Assemble the encapsulation string
                encap = interface.get_encapsulation(self.cfg, ifname)
                if encap['dot1ad'] > 0:
                    encapstr = "dot1ad %d" % encap['dot1ad']
                else:
                    encapstr = "dot1q %d" % encap['dot1q']
                if do_qinx:
                    encapstr += " inner-dot1q %d" % encap['inner-dot1q']
                if encap['exact-match'] == True:
                    encapstr += " exact-match"
                parent, subid = ifname.split('.')
                cli="create sub %s %d %s" % (parent, int(subid), encapstr)
                self.cli['create'].append(cli);
        return True

    def create_bridgedomains(self):
        for ifname in bridgedomain.get_bridgedomains(self.cfg):
            ifname, iface = bridgedomain.get_by_name(self.cfg, ifname)
            instance = int(ifname[2:])
            settings = bridgedomain.get_settings(self.cfg, ifname)
            if instance in self.vpp.cache['bridgedomains']:
                continue
            cli="create bridge-domain %s" % (instance)
            if not settings['learn']:
                cli += " learn 0"
            if not settings['unicast-flood']:
                cli += " flood 0"
            if not settings['unknown-unicast-flood']:
                cli += " uu-flood 0"
            if not settings['unicast-forward']:
                cli += " forward 0"
            if settings['arp-termination']:
                cli += " arp-term 1"
            if settings['arp-unicast-forward']:
                cli += " arp-ufwd 1"
            if settings['mac-age-minutes'] > 0:
                cli += " mac-age %d" % settings['mac-age-minutes']
            self.cli['create'].append(cli);
        return True

    def create_lcps(self):
        lcpnames = [self.vpp.cache['lcps'][x].host_if_name for x in self.vpp.cache['lcps']]

        ## First create untagged ... 
        for ifname in interface.get_interfaces(self.cfg) + loopback.get_loopbacks(self.cfg):
            if interface.is_sub(self.cfg, ifname):
                continue

            if ifname.startswith('loop'):
                ifname, iface = loopback.get_by_name(self.cfg, ifname)
            else:
                ifname, iface = interface.get_by_name(self.cfg, ifname)
            if not 'lcp' in iface:
                continue
            if iface['lcp'] in lcpnames:
                continue
            cli="lcp create %s host-if %s" % (ifname, iface['lcp'])
            self.cli['create'].append(cli);

        ## ... then 1-tag (Dot1Q/Dot1AD), and then create 2-tag (Qin*) LCPs
        for do_qinx in [False, True]:
            for ifname in interface.get_sub_interfaces(self.cfg):
                if not do_qinx == interface.is_qinx(self.cfg, ifname):
                    continue
                ifname, iface = interface.get_by_name(self.cfg, ifname)
                if not 'lcp' in iface:
                    continue
                if iface['lcp'] in lcpnames:
                    continue
                cli="lcp create %s host-if %s" % (ifname, iface['lcp'])
                self.cli['create'].append(cli);
        return True

    def sync(self):
        ret = True
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
        if not self.sync_admin_state():
            self.logger.warning("Could not sync interface adminstate in VPP")
            ret = False
        return ret

    def sync_bondethernets(self):
        for ifname in bondethernet.get_bondethernets(self.cfg):
            if ifname in self.vpp.cache['interface_names']:
                vpp_bond_sw_if_index = self.vpp.cache['interface_names'][ifname].sw_if_index
                vpp_members = [self.vpp.cache['interfaces'][x].interface_name for x in self.vpp.cache['bondethernet_members'][vpp_bond_sw_if_index]]
            else:
                ## New BondEthernet
                vpp_members = []

            config_bond_ifname, config_bond_iface = bondethernet.get_by_name(self.cfg, ifname)
            if not 'interfaces' in config_bond_iface:
                continue
            config_ifname, config_iface = interface.get_by_name(self.cfg, ifname)
            bondmac = None
            for member_ifname in sorted(config_bond_iface['interfaces']):
                member_ifname, member_iface = interface.get_by_name(self.cfg, member_ifname)
                member_iface = self.vpp.cache['interface_names'][member_ifname]
                if not member_ifname in vpp_members:
                    if len(vpp_members) == 0:
                        bondmac = member_iface.l2_address
                    cli="bond add %s %s" % (config_bond_ifname, member_iface.interface_name)
                    self.cli['sync'].append(cli);
            if bondmac and 'lcp' in config_iface:
                ## TODO(pim) - Ensure LCP has the same MAC as the BondEthernet
                ## VPP, when creating a BondEthernet, will give it an ephemeral MAC. Then, when the
                ## first member is enslaved, the MAC address changes to that of the first member.
                ## However, LinuxCP does not propagate this change to the Linux side (because there
                ## is no API callback for MAC address changes). To ensure consistency, every time we
                ## sync members, we ought to ensure the Linux device has the same MAC as its BondEthernet.
                cli="comment { ip link set %s address %s }" % (config_iface['lcp'], str(bondmac))
                self.cli['sync'].append(cli);
        return True

    def sync_bridgedomains(self):
        for ifname in bridgedomain.get_bridgedomains(self.cfg):
            instance = int(ifname[2:])
            if instance in self.vpp.cache['bridgedomains']:
                vpp_bridge = self.vpp.cache['bridgedomains'][instance]
                bvi_sw_if_index = vpp_bridge.bvi_sw_if_index
                bridge_sw_if_index_list = [x.sw_if_index for x in vpp_bridge.sw_if_details]
                bridge_members = [self.vpp.cache['interfaces'][x].interface_name for x in bridge_sw_if_index_list if x in self.vpp.cache['interfaces']]
            else:
                ## New BridgeDomain
                vpp_bridge = None
                bvi_sw_if_index = -1
                bridge_members = []

            config_bridge_ifname, config_bridge_iface = bridgedomain.get_by_name(self.cfg, "bd%d"%instance)
            if vpp_bridge:
                # Sync settings on existing bridge. create_bridgedomain() will have set them for new bridges.
                settings = bridgedomain.get_settings(self.cfg, config_bridge_ifname)
                if settings['learn'] != vpp_bridge.learn:
                    cli="set bridge-domain learn %d" % (instance)
                    if not settings['learn']:
                        cli += " disable"
                    self.cli['sync'].append(cli);
                if settings['unicast-forward'] != vpp_bridge.forward:
                    cli="set bridge-domain forward %d" % (instance)
                    if not settings['unicast-forward']:
                        cli += " disable"
                    self.cli['sync'].append(cli);
                if settings['unicast-flood'] != vpp_bridge.flood:
                    cli="set bridge-domain flood %d" % (instance)
                    if not settings['unicast-flood']:
                        cli += " disable"
                    self.cli['sync'].append(cli);
                if settings['unknown-unicast-flood'] != vpp_bridge.uu_flood:
                    cli="set bridge-domain uu-flood %d" % (instance)
                    if not settings['unknown-unicast-flood']:
                        cli += " disable"
                    self.cli['sync'].append(cli);
                if settings['arp-termination'] != vpp_bridge.arp_term:
                    cli="set bridge-domain arp term %d" % (instance)
                    if not settings['arp-termination']:
                        cli += " disable"
                    self.cli['sync'].append(cli);
                if settings['arp-unicast-forward'] != vpp_bridge.arp_ufwd:
                    cli="set bridge-domain arp-ufwd %d" % (instance)
                    if not settings['arp-unicast-forward']:
                        cli += " disable"
                    self.cli['sync'].append(cli);
                if settings['mac-age-minutes'] != vpp_bridge.mac_age:
                    cli="set bridge-domain mac-age %d %d" % (instance, settings['mac-age-minutes'])
                    self.cli['sync'].append(cli);

            if 'bvi' in config_bridge_iface:
                bviname = config_bridge_iface['bvi']
                if bviname in self.vpp.cache['interface_names'] and self.vpp.cache['interface_names'][bviname].sw_if_index == bvi_sw_if_index:
                    continue
                cli="set interface l2 bridge %s %d bvi" % (bviname, instance)
                self.cli['sync'].append(cli);

            if not 'interfaces' in config_bridge_iface:
                continue
            for member_ifname in config_bridge_iface['interfaces']:
                member_ifname, member_iface = interface.get_by_name(self.cfg, member_ifname)
                if not member_ifname in bridge_members:
                    cli="set interface l2 bridge %s %d" % (member_ifname, instance)
                    self.cli['sync'].append(cli);
                    operation="disable"
                    if interface.is_qinx(self.cfg, member_ifname):
                        operation="pop 2"
                    elif interface.is_sub(self.cfg, member_ifname):
                        operation="pop 1"
                    cli="set interface l2 tag-rewrite %s %s" % (member_ifname, operation)
                    self.cli['sync'].append(cli);
        return True

    def sync_l2xcs(self):
        for ifname in interface.get_l2xc_interfaces(self.cfg):
            config_rx_ifname, config_rx_iface = interface.get_by_name(self.cfg, ifname)
            config_tx_ifname, config_tx_iface = interface.get_by_name(self.cfg, config_rx_iface['l2xc'])
            vpp_rx_iface = None
            vpp_tx_iface = None
            if config_rx_ifname in self.vpp.cache['interface_names']:
                vpp_rx_iface = self.vpp.cache['interface_names'][config_rx_ifname]
            if config_tx_ifname in self.vpp.cache['interface_names']:
                vpp_tx_iface = self.vpp.cache['interface_names'][config_tx_ifname]

            l2xc_changed = False
            if not vpp_rx_iface or not vpp_tx_iface:
                cli="set interface l2 xconnect %s %s" % (config_rx_ifname, config_tx_ifname)
                self.cli['sync'].append(cli);
                l2xc_changed = True
            elif not vpp_rx_iface.sw_if_index in self.vpp.cache['l2xcs']:
                cli="set interface l2 xconnect %s %s" % (config_rx_ifname, config_tx_ifname)
                self.cli['sync'].append(cli);
                l2xc_changed = True
            elif not vpp_tx_iface.sw_if_index == self.vpp.cache['l2xcs'][vpp_rx_iface.sw_if_index].tx_sw_if_index:
                cli="set interface l2 xconnect %s %s" % (config_rx_ifname, config_tx_ifname)
                self.cli['sync'].append(cli);
                l2xc_changed = True
            if l2xc_changed:
                operation="disable"
                if interface.is_qinx(self.cfg, config_rx_ifname):
                    operation="pop 2"
                elif interface.is_sub(self.cfg, config_rx_ifname):
                    operation="pop 1"
                cli="set interface l2 tag-rewrite %s %s" % (config_rx_ifname, operation)
                self.cli['sync'].append(cli);
        return True

    def sync_mtu_direction(self, shrink=True):
        if shrink:
            tag_list = [ 2, 1, 0 ]
        else:
            tag_list = [ 0, 1, 2 ]

        for numtags in tag_list:
            for ifname in interface.get_interfaces(self.cfg) + loopback.get_loopbacks(self.cfg):
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
                    if ifname in self.vpp.cache['interface_names']:
                        vpp_mtu = self.vpp.cache['interface_names'][ifname].mtu[0]
                    vpp_ifname, config_iface = loopback.get_by_name(self.cfg, ifname)
                    if 'mtu' in config_iface:
                        config_mtu = config_iface['mtu']
                else:
                    if numtags > 0:
                        vpp_mtu = 0
                    if ifname in self.vpp.cache['interface_names']:
                        vpp_mtu = self.vpp.cache['interface_names'][ifname].mtu[0]
                    vpp_ifname, config_iface = interface.get_by_name(self.cfg, ifname)
                    config_mtu = interface.get_mtu(self.cfg, ifname)

                if shrink and config_mtu < vpp_mtu:
                    cli="set interface mtu packet %d %s" % (config_mtu, vpp_ifname)
                    self.cli['sync'].append(cli);
                elif not shrink and config_mtu > vpp_mtu:
                    cli="set interface mtu packet %d %s" % (config_mtu, vpp_ifname)
                    self.cli['sync'].append(cli);
        return True

    def sync_link_mtu_direction(self, shrink=True):
        for idx, vpp_iface in self.vpp.cache['interfaces'].items():
            if vpp_iface.sub_number_of_tags != 0:
                continue
            if vpp_iface.interface_dev_type in ['local', 'Loopback', 'VXLAN', 'virtio']:
                continue

            config_ifname, config_iface = interface.get_by_name(self.cfg, vpp_iface.interface_name)
            if not config_iface:
                self.logger.warning("Interface %s exists in VPP but not in config, this is dangerous" % vpp_iface.interface_name)
                continue
            if not interface.is_phy(self.cfg, vpp_iface.interface_name):
                continue
            config_mtu = interface.get_mtu(self.cfg, vpp_iface.interface_name)

            if vpp_iface.interface_dev_type=='bond' and vpp_iface.link_mtu < config_mtu:
                self.logger.warning("%s has a Max Frame Size (%d) lower than desired MTU (%d), this is unsupported" %
                        (vpp_iface.interface_name, vpp_iface.link_mtu, config_mtu))
                continue

            if shrink and config_mtu < vpp_iface.link_mtu:
                ## If the interface is up, temporarily down it in order to change the Max Frame Size
                if vpp_iface.flags & 1: # IF_STATUS_API_FLAG_ADMIN_UP
                    cli="set interface state %s down" % (vpp_iface.interface_name)
                    self.cli['sync'].append(cli);

                cli="set interface mtu %d %s" % (config_mtu, vpp_iface.interface_name)
                self.cli['sync'].append(cli);

                if vpp_iface.flags & 1: # IF_STATUS_API_FLAG_ADMIN_UP
                    cli="set interface state %s up" % (vpp_iface.interface_name)
                    self.cli['sync'].append(cli);
            elif not shrink and config_mtu > vpp_iface.link_mtu:
                ## If the interface is up, temporarily down it in order to change the Max Frame Size
                if vpp_iface.flags & 1: # IF_STATUS_API_FLAG_ADMIN_UP
                    cli="set interface state %s down" % (vpp_iface.interface_name)
                    self.cli['sync'].append(cli);

                cli="set interface mtu %d %s" % (config_mtu, vpp_iface.interface_name)
                self.cli['sync'].append(cli);

                if vpp_iface.flags & 1: # IF_STATUS_API_FLAG_ADMIN_UP
                    cli="set interface state %s up" % (vpp_iface.interface_name)
                    self.cli['sync'].append(cli);
        return True

    def sync_mtu(self):
        ret = True
        if not self.sync_link_mtu_direction(shrink=False):
            self.logger.warning("Could not sync growing interface Max Frame Size in VPP")
            ret = False
        if not self.sync_mtu_direction(shrink=True):
            self.logger.warning("Could not sync shrinking interface MTU in VPP")
            ret = False
        if not self.sync_mtu_direction(shrink=False):
            self.logger.warning("Could not sync growing interface MTU in VPP")
            ret = False
        if not self.sync_link_mtu_direction(shrink=True):
            self.logger.warning("Could not sync shrinking interface Max Frame Size in VPP")
            ret = False
        return ret

    def sync_addresses(self):
        for ifname in interface.get_interfaces(self.cfg) + loopback.get_loopbacks(self.cfg):
            config_addresses=[]
            vpp_addresses=[]
            if ifname.startswith("loop"):
                vpp_ifname, config_iface = loopback.get_by_name(self.cfg, ifname)
                if 'addresses' in config_iface:
                    config_addresses = config_iface['addresses']
            else:
                vpp_ifname, config_iface = interface.get_by_name(self.cfg, ifname)
                if 'addresses' in config_iface:
                    config_addresses = config_iface['addresses']
            if vpp_ifname in self.vpp.cache['interface_names']:
                sw_if_index = self.vpp.cache['interface_names'][vpp_ifname].sw_if_index
                if sw_if_index in self.vpp.cache['interface_addresses']:
                    vpp_addresses = [str(x) for x in self.vpp.cache['interface_addresses'][sw_if_index]]
            for a in config_addresses:
                if a in vpp_addresses:
                    continue
                cli="set interface ip address %s %s" % (vpp_ifname, a)
                self.cli['sync'].append(cli);
        return True

    def sync_admin_state(self):
        for ifname in interface.get_interfaces(self.cfg) + loopback.get_loopbacks(self.cfg):
            if ifname.startswith("loop"):
                vpp_ifname, config_iface = loopback.get_by_name(self.cfg, ifname)
                config_admin_state = 1
            else:
                vpp_ifname, config_iface = interface.get_by_name(self.cfg, ifname)
                config_admin_state = interface.get_admin_state(self.cfg, ifname)

            vpp_admin_state = 0
            if vpp_ifname in self.vpp.cache['interface_names']:
                vpp_admin_state = self.vpp.cache['interface_names'][vpp_ifname].flags & 1 # IF_STATUS_API_FLAG_ADMIN_UP
            if config_admin_state == vpp_admin_state:
                continue
            state="up"
            if config_admin_state == 0:
                state="down"
            cli="set interface state %s %s" % (vpp_ifname, state)
            self.cli['sync'].append(cli);
        return True

    def write(self, outfile, ok=False):
        """ Emit the CLI contents to stdout (if outfile=='-') or a named file otherwise.
            If the 'ok' flag is False, emit a warning at the top and bottom of the file.
        """
        # Assemble the intended output into a list
        output = []
        if not ok:
            output.append("comment { vppcfg: Planning failed, be careful with this output! }")

        for phase in [ "prune", "create", "sync" ]:
            n = len(self.cli[phase])
            if n > 0:
                output.append("comment { vppcfg %s: %d CLI statement(s) follow }" % (phase, n))
                output.extend(self.cli[phase])

        if not ok:
            output.append("comment { vppcfg: Planning failed, be careful with this output! }")

        # Emit the output list to stdout or a file
        if outfile and outfile == '-':
            fh = sys.stdout
            outfile = "(stdout)"
        else:
            fh = open(outfile, 'w')
        if len(output) > 0:
            print('\n'.join(output), file=fh)
        if fh is not sys.stdout:
            fh.close()

        self.logger.info("Wrote %d lines to %s" % (len(output), outfile))

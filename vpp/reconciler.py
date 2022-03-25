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

    def readconfig(self):
        return self.vpp.readconfig()

    def phys_exist(self, ifname_list):
        """ Return True if all interfaces in the `ifname_list` exist as physical interface names
        in VPP. Return False otherwise."""
        ret = True
        for ifname in ifname_list:
            if not ifname in self.vpp.config['interface_names']:
                self.logger.warning("Interface %s does not exist in VPP" % ifname)
                ret = False
        return ret

    def prune(self):
        """ Remove all objects from VPP that do not occur in the config. For an indepth explanation
            of how and why this particular pruning order is chosen, see README.md section on
            Reconciling. """
        ret = True
        if not self.prune_interfaces_down():
            self.logger.warning("Could not set interfaces down in VPP")
            ret = False
        if not self.prune_lcps():
            self.logger.warning("Could not prune LCPs from VPP")
            ret = False
        if not self.prune_loopbacks():
            self.logger.warning("Could not prune loopbacks from VPP")
            ret = False
        if not self.prune_bridgedomains():
            self.logger.warning("Could not prune BridgeDomains from VPP")
            ret = False
        if not self.prune_bvis():
            self.logger.warning("Could not prune BVIs from VPP")
            ret = False
        if not self.prune_l2xcs():
            self.logger.warning("Could not prune L2 Cross Connects from VPP")
            ret = False
        if not self.prune_sub_interfaces():
            self.logger.warning("Could not prune sub-interfaces from VPP")
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

        ## Report on what is left in the configuration after pruning.
        self.logger.debug("After pruning, the following config is left:")
        for idx, lcp in self.vpp.config['lcps'].items():
            self.logger.debug("LCP[%d]: %s" % (idx, lcp))
        for ifname, iface in self.vpp.config['interface_names'].items():
            self.logger.debug("Interface[%s]: %s" % (ifname, iface))
        for idx, iface in self.vpp.config['interfaces'].items():
            self.logger.debug("Interface[%d]: %s" % (idx, iface))
        for idx, iface in self.vpp.config['bondethernets'].items():
            self.logger.debug("bondethernets[%d]: %s" % (idx, iface))
        for idx, iface in self.vpp.config['bondethernet_members'].items():
            self.logger.debug("bondethernet_members[%d]: %s" % (idx, iface))
        for idx, iface in self.vpp.config['vxlan_tunnels'].items():
            self.logger.debug("vxlan_tunnels[%d]: %s" % (idx, iface))
        for idx, iface in self.vpp.config['l2xcs'].items():
            self.logger.debug("l2xcs[%d]: %s" % (idx, iface))

        return ret

    def prune_addresses(self, ifname, address_list):
        """ Remove all addresses from interface ifname, except those in address_list,
            which may be an empty list, in which case all addresses are removed.
        """
        idx = self.vpp.config['interface_names'][ifname].sw_if_index
        removed_addresses = []
        for a in self.vpp.config['interface_addresses'][idx]:
            if not a in address_list:
                self.logger.info("1> set interface ip address del %s %s" % (ifname, a))
                removed_addresses.append(a)
            else:
                self.logger.debug("Address OK: %s %s" % (ifname, a))
        for a in removed_addresses:
            self.vpp.config['interface_addresses'][idx].remove(a)

    def prune_loopbacks(self):
        """ Remove loopbacks from VPP, if they do not occur in the config. """
        removed_interfaces=[]
        for numtags in [ 2, 1, 0 ]:
            for idx, vpp_iface in self.vpp.config['interfaces'].items():
                if vpp_iface.interface_dev_type!='Loopback':
                    continue
                if vpp_iface.sub_number_of_tags != numtags:
                    continue
                config_ifname, config_iface = loopback.get_by_name(self.cfg, vpp_iface.interface_name)
                if not config_iface:
                    self.prune_addresses(vpp_iface.interface_name, [])
                    if numtags == 0:
                        self.logger.info("1> delete loopback interface intfc %s" % vpp_iface.interface_name)
                        removed_interfaces.append(vpp_iface.interface_name)
                    else:
                        self.logger.info("1> delete sub %s" % vpp_iface.interface_name)
                        removed_interfaces.append(vpp_iface.interface_name)
                    continue
                self.logger.debug("Loopback OK: %s" % (vpp_iface.interface_name))
                addresses = []
                if 'addresses' in config_iface:
                    addresses = config_iface['addresses']
                self.prune_addresses(vpp_iface.interface_name, addresses)

        for ifname in removed_interfaces:
            self.vpp.remove_interface(ifname)

        return True

    def prune_bvis(self):
        """ Remove BVIs (bridge-domain virtual interfaces) from VPP, if they do not occur in the config. """
        removed_interfaces=[]
        for numtags in [ 2, 1, 0 ]:
            for idx, vpp_iface in self.vpp.config['interfaces'].items():
                if vpp_iface.interface_dev_type!='BVI':
                    continue
                if vpp_iface.sub_number_of_tags != numtags:
                    continue
                config_ifname, config_iface = bridgedomain.get_by_bvi_name(self.cfg, vpp_iface.interface_name)
                if not config_iface:
                    self.prune_addresses(vpp_iface.interface_name, [])
                    if numtags == 0:
                        self.logger.info("1> bvi delete %s" % vpp_iface.interface_name)
                        removed_interfaces.append(vpp_iface.interface_name)
                    else:
                        self.logger.info("1> delete sub %s" % vpp_iface.interface_name)
                        removed_interfaces.append(vpp_iface.interface_name)
                    continue
                self.logger.debug("BVI OK: %s" % (vpp_iface.interface_name))
                addresses = []
                if 'addresses' in config_iface:
                    addresses = config_iface['addresses']
                self.prune_addresses(vpp_iface.interface_name, addresses)

        for ifname in removed_interfaces:
            self.vpp.remove_interface(ifname)

        return True


    def prune_bridgedomains(self):
        """ Remove bridge-domains from VPP, if they do not occur in the config. If any interfaces are
            found in to-be removed bridge-domains, they are returned to L3 mode, and tag-rewrites removed. """
        for idx, bridge in self.vpp.config['bridgedomains'].items():
            bridgename = "bd%d" % idx
            config_ifname, config_iface = bridgedomain.get_by_name(self.cfg, bridgename)
            members = []
            if not config_iface:
                for member in bridge.sw_if_details:
                    member_iface = self.vpp.config['interfaces'][member.sw_if_index]
                    member_ifname = member_iface.interface_name
                    if member_iface.sub_id > 0:
                        self.logger.info("1> set interface l2 tag-rewrite %s disable" % member_ifname)
                    self.logger.info("1> set interface l3 %s" % member_ifname)
                self.logger.info("1> create bridge-domain %d del" % idx)
            else:
                self.logger.debug("BridgeDomain OK: %s" % (bridgename))
                for member in bridge.sw_if_details:
                    member_ifname = self.vpp.config['interfaces'][member.sw_if_index].interface_name
                    if 'members' in config_iface and member_ifname in config_iface['members']:
                        if interface.is_sub(self.cfg, member_ifname):
                            self.logger.info("1> set interface l2 tag-rewrite %s disable" % member_ifname)
                        self.logger.info("1> set interface l3 %s" % member_ifname)
        return True

    def prune_l2xcs(self):
        """ Remove all L2XC source interfaces from VPP, if they do not occur in the config. If they occur,
            but are crossconnected to a different interface name, also remove them. Interfaces are put
            back into L3 mode, and their tag-rewrites removed. """
        removed_l2xcs=[]
        for idx, l2xc in self.vpp.config['l2xcs'].items():
            vpp_rx_ifname = self.vpp.config['interfaces'][l2xc.rx_sw_if_index].interface_name
            config_rx_ifname, config_rx_iface = interface.get_by_name(self.cfg, vpp_rx_ifname)
            if not config_rx_ifname:
                if self.vpp.config['interfaces'][l2xc.rx_sw_if_index].sub_id > 0:
                    self.logger.info("1> set interface l2 tag-rewrite %s disable" % vpp_rx_ifname)
                self.logger.info("1> set interface l3 %s" % vpp_rx_ifname)
                removed_l2xcs.append(vpp_rx_ifname)
                continue

            if not interface.is_l2xc_interface(self.cfg, config_rx_ifname):
                if interface.is_sub(self.cfg, config_rx_ifname):
                    self.logger.info("2> set interface l2 tag-rewrite %s disable" % vpp_rx_ifname)
                self.logger.info("2> set interface l3 %s" % vpp_rx_ifname)
                removed_l2xcs.append(vpp_rx_ifname)
                continue
            vpp_tx_ifname = self.vpp.config['interfaces'][l2xc.tx_sw_if_index].interface_name
            if vpp_tx_ifname != config_rx_iface['l2xc']:
                if interface.is_sub(self.cfg, config_rx_ifname):
                    self.logger.info("3> set interface l2 tag-rewrite %s disable" % vpp_rx_ifname)
                self.logger.info("3> set interface l3 %s" % vpp_rx_ifname)
                removed_l2xcs.append(vpp_rx_ifname)
                continue
            self.logger.debug("L2XC OK: %s -> %s" % (vpp_rx_ifname, vpp_tx_ifname))
        for l2xc in removed_l2xcs:
            self.vpp.remove_l2xc(l2xc)
        return True

    def prune_bondethernets(self):
        """ Remove all BondEthernets from VPP, if they are not in the config. If the bond has members,
            remove those from the bond before removing the bond. """
        removed_interfaces=[]
        removed_bondethernet_members=[]
        for idx, bond in self.vpp.config['bondethernets'].items():
            vpp_ifname = bond.interface_name
            config_ifname, config_iface = bondethernet.get_by_name(self.cfg, vpp_ifname)
            if not config_iface:
                self.prune_addresses(vpp_ifname, [])
                for member in self.vpp.config['bondethernet_members'][idx]:
                    member_ifname = self.vpp.config['interfaces'][member].interface_name
                    self.logger.info("1> bond del %s" % member_ifname)
                    removed_bondethernet_members.append(member_ifname)
                self.logger.info("1> delete bond %s" % (vpp_ifname))
                removed_interfaces.append(vpp_ifname)
                continue
            for member in self.vpp.config['bondethernet_members'][idx]:
                member_ifname = self.vpp.config['interfaces'][member].interface_name
                if 'interfaces' in config_iface and not member_ifname in config_iface['interfaces']:
                    self.logger.info("2> bond del %s" % member_ifname)
                    removed_bondethernet_members.append(member_ifname)
            addresses = []
            if 'addresses' in config_iface:
                addresses = config_iface['addresses']
            self.prune_addresses(vpp_ifname, addresses)
            self.logger.debug("BondEthernet OK: %s" % (vpp_ifname))

        for ifname in removed_bondethernet_members:
            self.vpp.remove_bondethernet_member(ifname)

        for ifname in removed_interfaces:
            self.vpp.remove_interface(ifname)

        return True

    def prune_vxlan_tunnels(self):
        """ Remove all VXLAN Tunnels from VPP, if they are not in the config. If they are in the config
            but with differing attributes, remove them also. """
        removed_interfaces=[]
        for idx, vpp_vxlan in self.vpp.config['vxlan_tunnels'].items():
            vpp_ifname = self.vpp.config['interfaces'][idx].interface_name
            config_ifname, config_iface = vxlan_tunnel.get_by_name(self.cfg, vpp_ifname)
            if not config_iface:
                self.logger.info("1> create vxlan tunnel instance %d src %s dst %s vni %d del" % (vpp_vxlan.instance, 
                    vpp_vxlan.src_address, vpp_vxlan.dst_address, vpp_vxlan.vni))
                removed_interfaces.append(vpp_ifname)
                continue
            if config_iface['local'] != str(vpp_vxlan.src_address) or config_iface['remote'] != str(vpp_vxlan.dst_address) or config_iface['vni'] != vpp_vxlan.vni:
                self.logger.info("2> create vxlan tunnel instance %d src %s dst %s vni %d del" % (vpp_vxlan.instance, 
                    vpp_vxlan.src_address, vpp_vxlan.dst_address, vpp_vxlan.vni))
                removed_interfaces.append(vpp_ifname)
                continue
            addresses = []
            if 'addresses' in config_iface:
                addresses = config_iface['addresses']
            self.prune_addresses(vpp_ifname, addresses)
            self.logger.debug("VXLAN Tunnel OK: %s" % (vpp_ifname))

        for ifname in removed_interfaces:
            self.vpp.remove_vxlan_tunnel(ifname)
            self.vpp.remove_interface(ifname)

        return True

    def prune_sub_interfaces(self):
        """ Remove interfaces from VPP if they are not in the config. Start with inner-most (QinQ/QinAD), then
            Dot1Q/Dot1AD."""
        removed_interfaces=[]
        for numtags in [ 2, 1 ]:
            for vpp_ifname in self.vpp.get_sub_interfaces():
                vpp_iface = self.vpp.config['interface_names'][vpp_ifname]
                if vpp_iface.sub_number_of_tags != numtags:
                    continue
                config_ifname, config_iface = interface.get_by_name(self.cfg, vpp_ifname)
                if not config_iface:
                    self.prune_addresses(vpp_ifname, [])
                    self.logger.info("1> delete sub %s" % vpp_ifname)
                    removed_interfaces.append(vpp_ifname)
                    continue
                addresses = []
                if 'addresses' in config_iface:
                    addresses = config_iface['addresses']
                self.prune_addresses(vpp_ifname, addresses)
                self.logger.debug("Sub Interface OK: %s" % (vpp_ifname))

        for ifname in removed_interfaces:
            self.vpp.remove_interface(ifname)

        return True

    def prune_phys(self):
        """ Set default MTU and remove IPs for PHYs that are not in the config. """
        for vpp_ifname in self.vpp.get_phys():
            vpp_iface = self.vpp.config['interface_names'][vpp_ifname]
            config_ifname, config_iface = interface.get_by_name(self.cfg, vpp_ifname)
            if not config_iface:
                ## Interfaces were sent DOWN in the prune_interfaces_down() step previously
                self.prune_addresses(vpp_ifname, [])
                if vpp_iface.link_mtu != 9000:
                    self.logger.info("1> set interface mtu 9000 %s" % vpp_ifname)
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
        for idx, iface in self.vpp.config['interfaces'].items():
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
            and finally PHYs/BondEthernets/Tunnels/BVIs/Loopbacks. For QinX, special care is taken to ensure that
            their intermediary interface exists, and has the correct encalsulation. If the intermediary interface
            changed, the QinX LCP is removed. The same is true for Dot1Q/Dot1AD interfaces: if their encapsulation
            has changed, we will have to re-create the underlying sub-interface, so the LCP has to be removed.

            Order is important: destroying an LCP of a PHY will invalidate its Dot1Q/Dot1AD as well as their
            downstream children in Linux.
        """
        lcps = self.vpp.config['lcps']

        removed_lcps = []
        ## Remove LCPs for QinX interfaces
        for idx, lcp in lcps.items():
            vpp_iface = self.vpp.config['interfaces'][lcp.phy_sw_if_index]
            if vpp_iface.sub_inner_vlan_id == 0:
                continue
            config_ifname, config_iface = interface.get_by_lcp_name(self.cfg, lcp.host_if_name)
            if not config_iface:
                ## QinX doesn't exist in the config
                self.logger.info("1> lcp delete %s" % vpp_iface.interface_name)
                removed_lcps.append(lcp.host_if_name)
                continue
            if not 'lcp' in config_iface:
                ## QinX doesn't have an LCP
                self.logger.info("2> lcp delete %s" % vpp_iface.interface_name)
                removed_lcps.append(lcp.host_if_name)
                continue
            vpp_parent_idx = self.__parent_iface_by_encap(vpp_iface.sup_sw_if_index, vpp_iface.sub_outer_vlan_id, vpp_iface.sub_if_flags&8)
            vpp_parent_iface = self.vpp.config['interfaces'][vpp_parent_idx]
            parent_lcp = lcps[vpp_parent_iface.sw_if_index]
            config_parent_ifname, config_parent_iface = interface.get_by_lcp_name(self.cfg, parent_lcp.host_if_name)
            if not config_parent_iface:
                ## QinX's parent doesn't exist in the config
                self.logger.info("3> lcp delete %s" % vpp_iface.interface_name)
                removed_lcps.append(lcp.host_if_name)
                continue
            if not 'lcp' in config_parent_iface:
                ## QinX's parent doesn't have an LCP
                self.logger.info("4> lcp delete %s" % vpp_iface.interface_name)
                removed_lcps.append(lcp.host_if_name)
                continue
            if parent_lcp.host_if_name != config_parent_iface['lcp']:
                ## QinX's parent LCP name mismatch
                self.logger.info("5> lcp delete %s" % vpp_iface.interface_name)
                removed_lcps.append(lcp.host_if_name)
                continue

            phy_lcp = lcps[vpp_iface.sup_sw_if_index]
            config_phy_ifname, config_phy_iface = interface.get_by_lcp_name(self.cfg, phy_lcp.host_if_name)
            if not config_phy_iface:
                ## QinX's phy doesn't exist in the config
                self.logger.info("6> lcp delete %s" % vpp_iface.interface_name)
                removed_lcps.append(lcp.host_if_name)
                continue
            if not 'lcp' in config_phy_iface:
                ## QinX's phy doesn't have an LCP
                self.logger.info("6> lcp delete %s" % vpp_iface.interface_name)
                removed_lcps.append(lcp.host_if_name)
                continue
            if phy_lcp.host_if_name != config_phy_iface['lcp']:
                ## QinX's phy LCP name mismatch
                self.logger.info("7> lcp delete %s" % vpp_iface.interface_name)
                removed_lcps.append(lcp.host_if_name)
                continue

            config_encap = interface.get_encapsulation(self.cfg, config_ifname)
            vpp_encap = self.__get_encapsulation(vpp_iface)
            config_parent_encap = interface.get_encapsulation(self.cfg, config_parent_ifname)
            vpp_parent_encap = self.__get_encapsulation(vpp_parent_iface)
            if config_encap != vpp_encap:
                ## QinX's encapsulation mismatch
                self.logger.info("8> lcp delete %s" % vpp_iface.interface_name)
                removed_lcps.append(lcp.host_if_name)
                continue
            if config_parent_encap != vpp_parent_encap:
                ## QinX's parent encapsulation mismatch
                self.logger.info("9> lcp delete %s" % vpp_iface.interface_name)
                removed_lcps.append(lcp.host_if_name)
                continue
            self.logger.debug("QinX LCP OK: %s -> (vpp=%s, config=%s)" % (lcp.host_if_name, vpp_iface.interface_name, config_ifname))

        ## Remove LCPs for sub-interfaces
        for idx, lcp in lcps.items():
            vpp_iface = self.vpp.config['interfaces'][lcp.phy_sw_if_index]
            if vpp_iface.sub_inner_vlan_id > 0 or vpp_iface.sub_outer_vlan_id == 0:
                continue
            config_ifname, config_iface = interface.get_by_lcp_name(self.cfg, lcp.host_if_name)
            if not config_iface:
                ## Sub doesn't exist in the config
                self.logger.info("11> lcp delete %s" % vpp_iface.interface_name)
                removed_lcps.append(lcp.host_if_name)
                continue
            if not 'lcp' in config_iface:
                ## Sub doesn't have an LCP
                self.logger.info("12> lcp delete %s" % vpp_iface.interface_name)
                removed_lcps.append(lcp.host_if_name)
                continue

            phy_lcp = lcps[vpp_iface.sup_sw_if_index]
            config_phy_ifname, config_phy_iface = interface.get_by_lcp_name(self.cfg, phy_lcp.host_if_name)
            if not config_phy_iface:
                ## Sub's phy doesn't exist in the config
                self.logger.info("13> lcp delete %s" % vpp_iface.interface_name)
                removed_lcps.append(lcp.host_if_name)
                continue
            if not 'lcp' in config_phy_iface:
                ## Sub's phy doesn't have an LCP
                self.logger.info("14> lcp delete %s" % vpp_iface.interface_name)
                removed_lcps.append(lcp.host_if_name)
                continue
            if phy_lcp.host_if_name != config_phy_iface['lcp']:
                ## Sub's phy LCP name mismatch
                self.logger.info("15> lcp delete %s" % vpp_iface.interface_name)
                removed_lcps.append(lcp.host_if_name)
                continue

            config_encap = interface.get_encapsulation(self.cfg, config_ifname)
            vpp_encap = self.__get_encapsulation(vpp_iface)
            if config_encap != vpp_encap:
                ## Sub's encapsulation mismatch
                self.logger.info("16> lcp delete %s" % vpp_iface.interface_name)
                removed_lcps.append(lcp.host_if_name)
                continue

            self.logger.debug("Dot1Q/Dot1AD LCP OK: %s -> (vpp=%s, config=%s)" % (lcp.host_if_name, vpp_iface.interface_name, config_ifname))

        ## Remove LCPs for interfaces, bonds, tunnels, loops, bvis
        for idx, lcp in lcps.items():
            vpp_iface = self.vpp.config['interfaces'][lcp.phy_sw_if_index]
            if vpp_iface.sub_inner_vlan_id > 0 or vpp_iface.sub_outer_vlan_id > 0:
                continue

            if vpp_iface.interface_dev_type=='Loopback':
                config_ifname, config_iface = loopback.get_by_lcp_name(self.cfg, lcp.host_if_name)
            elif vpp_iface.interface_dev_type=='BVI':
                config_ifname, config_iface = bridgedomain.get_by_lcp_name(self.cfg, lcp.host_if_name)
            else:
                config_ifname, config_iface = interface.get_by_lcp_name(self.cfg, lcp.host_if_name)

            if not config_iface:
                ## Interface doesn't exist in the config
                self.logger.info("21> lcp delete %s" % vpp_iface.interface_name)
                removed_lcps.append(lcp.host_if_name)
                continue
            if not 'lcp' in config_iface:
                ## Interface doesn't have an LCP
                self.logger.info("22> lcp delete %s" % vpp_iface.interface_name)
                removed_lcps.append(lcp.host_if_name)
                continue
            self.logger.debug("LCP OK: %s -> (vpp=%s, config=%s)" % (lcp.host_if_name, vpp_iface.interface_name, config_ifname))

        for lcpname in removed_lcps:
            self.vpp.remove_lcp(lcpname)
        return True

    def prune_interfaces_down(self):
        """ Set admin-state down for all interfaces that are not in the config. """
        for ifname in self.vpp.get_qinx_interfaces() + self.vpp.get_dot1x_interfaces() + self.vpp.get_bondethernets() + self.vpp.get_phys() + self.vpp.get_vxlan_tunnels() + self.vpp.get_bvis() + self.vpp.get_loopbacks():
            if not ifname in interface.get_interfaces(self.cfg):
                iface = self.vpp.config['interface_names'][ifname]

                ## Skip TAP interfaces belonging to an LCP
                skip = False
                for idx, lcp in self.vpp.config['lcps'].items():
                    if iface.sw_if_index == lcp.host_sw_if_index:
                        skip = True
                if skip:
                    continue

                if iface.flags & 1: # IF_STATUS_API_FLAG_ADMIN_UP
                    self.logger.info("1> set interface state %s down" % ifname)

        return True

    def create(self):
        return False

    def sync(self):
        return False

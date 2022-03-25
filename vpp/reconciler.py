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
        self.logger = logging.getLogger('vppcfg.vppapi')
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

    def prune_addresses(self, ifname, address_list):
        """ Remove all addresses from interface ifname, except those in address_list """
        idx = self.vpp.config['interface_names'][ifname].sw_if_index
        for a in self.vpp.config['interface_addresses'][idx]:
            if not a in address_list:
                self.logger.info("1> set interface ip address del %s %s" % (ifname, a))
            else:
                self.logger.debug("Address OK: %s %s" % (ifname, a))
        
    def prune(self):
        ret = True
        if not self.prune_addresses_set_interface_down():
            self.logger.warning("Could not prune addresses and set interfaces down from VPP that are not in the config")
            ret = False
        if not self.prune_lcps():
            self.logger.warning("Could not prune LCPs from VPP that are not in the config")
            ret = False
        if not self.prune_loopbacks():
            self.logger.warning("Could not prune loopbacks from VPP that are not in the config")
            ret = False
        if not self.prune_bvis():
            self.logger.warning("Could not prune BVIs from VPP that are not in the config")
            ret = False
        if not self.prune_bridgedomains():
            self.logger.warning("Could not prune BridgeDomains from VPP that are not in the config")
            ret = False
        if not self.prune_l2xcs():
            self.logger.warning("Could not prune L2 Cross Connects from VPP that are not in the config")
            ret = False
        if not self.prune_bondethernets():
            self.logger.warning("Could not prune BondEthernets from VPP that are not in the config")
            ret = False
        if not self.prune_vxlan_tunnels():
            self.logger.warning("Could not prune VXLAN Tunnels from VPP that are not in the config")
            ret = False
        if not self.prune_interfaces():
            self.logger.warning("Could not prune interfaces from VPP that are not in the config")
            ret = False
        return ret

    def prune_loopbacks(self):
        for idx, vpp_iface in self.vpp.config['interfaces'].items():
            if vpp_iface.interface_dev_type!='Loopback':
                continue
            config_ifname, config_iface = loopback.get_by_name(self.cfg, vpp_iface.interface_name)
            if not config_iface:
                self.logger.info("1> delete loopback interface intfc %s" % vpp_iface.interface_name)
                continue
            self.logger.debug("Loopback OK: %s" % (vpp_iface.interface_name))
            addresses = []
            if 'addresses' in config_iface:
                addresses = config_iface['addresses']
            self.prune_addresses(vpp_iface.interface_name, addresses)
        return True

    def prune_bvis(self):
        for idx, vpp_iface in self.vpp.config['interfaces'].items():
            if vpp_iface.interface_dev_type!='BVI':
                continue
            config_ifname, config_iface = bridgedomain.get_by_bvi_name(self.cfg, vpp_iface.interface_name)
            if not config_iface:
                self.logger.info("1> bvi delete %s" % vpp_iface.interface_name)
                continue
            self.logger.debug("BVI OK: %s" % (vpp_iface.interface_name))
            addresses = []
            if 'addresses' in config_iface:
                addresses = config_iface['addresses']
            self.prune_addresses(vpp_iface.interface_name, addresses)
        return True

    def prune_bridgedomains(self):
        for idx, bridge in self.vpp.config['bridgedomains'].items():
            bridgename = "bd%d" % idx
            config_ifname, config_iface = bridgedomain.get_by_name(self.cfg, bridgename)
            members = []
            if not config_iface:
                for member in bridge.sw_if_details:
                    member_ifname = self.vpp.config['interfaces'][member.sw_if_index].interface_name
                    if interface.is_sub(self.cfg, member_ifname):
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
        for idx, l2xc in self.vpp.config['l2xcs'].items():
            vpp_rx_ifname = self.vpp.config['interfaces'][l2xc.rx_sw_if_index].interface_name
            config_rx_ifname, config_rx_iface = interface.get_by_name(self.cfg, vpp_rx_ifname)
            if not config_rx_ifname:
                if self.vpp.config['interfaces'][l2xc.rx_sw_if_index].sub_id > 0:
                    self.logger.info("1> set interface l2 tag-rewrite %s disable" % vpp_rx_ifname)
                self.logger.info("1> set interface l3 %s" % vpp_rx_ifname)
                continue

            if not interface.is_l2xc_interface(self.cfg, config_rx_ifname):
                if interface.is_sub(self.cfg, config_rx_ifname):
                    self.logger.info("2> set interface l2 tag-rewrite %s disable" % vpp_rx_ifname)
                self.logger.info("2> set interface l3 %s" % vpp_rx_ifname)
                continue
            vpp_tx_ifname = self.vpp.config['interfaces'][l2xc.tx_sw_if_index].interface_name
            if vpp_tx_ifname != config_rx_iface['l2xc']:
                if interface.is_sub(self.cfg, config_rx_ifname):
                    self.logger.info("3> set interface l2 tag-rewrite %s disable" % vpp_rx_ifname)
                self.logger.info("3> set interface l3 %s" % vpp_rx_ifname)
                continue
            self.logger.debug("L2XC OK: %s -> %s" % (vpp_rx_ifname, vpp_tx_ifname))
        return True

    def prune_bondethernets(self):
        for idx, bond in self.vpp.config['bondethernets'].items():
            vpp_ifname = bond.interface_name
            config_ifname, config_iface = bondethernet.get_by_name(self.cfg, vpp_ifname)
            if not config_iface:
                for member in self.vpp.config['bondethernet_members'][idx]:
                    self.logger.info("1> bond del %s" % self.vpp.config['interfaces'][member].interface_name)
                self.logger.info("1> delete bond %s" % (vpp_ifname))
                continue
            for member in self.vpp.config['bondethernet_members'][idx]:
                member_ifname = self.vpp.config['interfaces'][member].interface_name
                if 'interfaces' in config_iface and not member_ifname in config_iface['interfaces']:
                    self.logger.info("2> bond del %s" % member_ifname)
            addresses = []
            if 'addresses' in config_iface:
                addresses = config_iface['addresses']
            self.prune_addresses(vpp_ifname, addresses)
            self.logger.debug("BondEthernet OK: %s" % (vpp_ifname))
        return True

    def prune_vxlan_tunnels(self):
        for idx, vpp_vxlan in self.vpp.config['vxlan_tunnels'].items():
            vpp_ifname = self.vpp.config['interfaces'][idx].interface_name
            config_ifname, config_iface = vxlan_tunnel.get_by_name(self.cfg, vpp_ifname)
            if not config_iface:
                self.logger.info("1> create vxlan tunnel instance %d src %s dst %s vni %d del" % (vpp_vxlan.instance, 
                    vpp_vxlan.src_address, vpp_vxlan.dst_address, vpp_vxlan.vni))
                continue
            if config_iface['local'] != str(vpp_vxlan.src_address) or config_iface['remote'] != str(vpp_vxlan.dst_address) or config_iface['vni'] != vpp_vxlan.vni:
                self.logger.info("2> create vxlan tunnel instance %d src %s dst %s vni %d del" % (vpp_vxlan.instance, 
                    vpp_vxlan.src_address, vpp_vxlan.dst_address, vpp_vxlan.vni))
                continue
            addresses = []
            if 'addresses' in config_iface:
                addresses = config_iface['addresses']
            self.prune_addresses(vpp_ifname, addresses)
            self.logger.debug("VXLAN Tunnel OK: %s" % (vpp_ifname))
        return True

    def prune_interfaces(self):
        for vpp_ifname in self.vpp.get_qinx_interfaces() + self.vpp.get_dot1x_interfaces() + self.vpp.get_phys():
            vpp_iface = self.vpp.config['interface_names'][vpp_ifname]
            config_ifname, config_iface = interface.get_by_name(self.cfg, vpp_ifname)
            if not config_iface:
                if vpp_iface.sub_id > 0:
                    self.logger.info("1> delete sub %s" % vpp_ifname)
                else:
                    if vpp_iface.flags & 1: # IF_STATUS_API_FLAG_ADMIN_UP
                        self.logger.info("1> set interface state %s down" % vpp_ifname)
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
        """ Returns the idx of an interface on a given super_sw_if_index with given dot1q/dot1ad outer and inner-dot1q=0 """
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
        lcps = self.vpp.config['lcps']

        ## Remove LCPs for QinX interfaces
        for idx, lcp in lcps.items():
            vpp_iface = self.vpp.config['interfaces'][lcp.phy_sw_if_index]
            if vpp_iface.sub_inner_vlan_id == 0:
                continue
            config_ifname, config_iface = interface.get_by_lcp_name(self.cfg, lcp.host_if_name)
            if not config_iface:
                ## QinX doesn't exist in the config
                self.logger.info("1> lcp delete %s" % vpp_iface.interface_name)
                continue
            if not 'lcp' in config_iface:
                ## QinX doesn't have an LCP
                self.logger.info("2> lcp delete %s" % vpp_iface.interface_name)
                continue
            vpp_parent_idx = self.__parent_iface_by_encap(vpp_iface.sup_sw_if_index, vpp_iface.sub_outer_vlan_id, vpp_iface.sub_if_flags&8)
            vpp_parent_iface = self.vpp.config['interfaces'][vpp_parent_idx]
            parent_lcp = lcps[vpp_parent_iface.sw_if_index]
            config_parent_ifname, config_parent_iface = interface.get_by_lcp_name(self.cfg, parent_lcp.host_if_name)
            if not config_parent_iface:
                ## QinX's parent doesn't exist in the config
                self.logger.info("3> lcp delete %s" % vpp_iface.interface_name)
                continue
            if not 'lcp' in config_parent_iface:
                ## QinX's parent doesn't have an LCP
                self.logger.info("4> lcp delete %s" % vpp_iface.interface_name)
                continue
            if parent_lcp.host_if_name != config_parent_iface['lcp']:
                ## QinX's parent LCP name mismatch
                self.logger.info("5> lcp delete %s" % vpp_iface.interface_name)
                continue

            phy_lcp = lcps[vpp_iface.sup_sw_if_index]
            config_phy_ifname, config_phy_iface = interface.get_by_lcp_name(self.cfg, phy_lcp.host_if_name)
            if not config_phy_iface:
                ## QinX's phy doesn't exist in the config
                self.logger.info("6> lcp delete %s" % vpp_iface.interface_name)
                continue
            if not 'lcp' in config_phy_iface:
                ## QinX's phy doesn't have an LCP
                self.logger.info("6> lcp delete %s" % vpp_iface.interface_name)
                continue
            if phy_lcp.host_if_name != config_phy_iface['lcp']:
                ## QinX's phy LCP name mismatch
                self.logger.info("7> lcp delete %s" % vpp_iface.interface_name)
                continue

            config_encap = interface.get_encapsulation(self.cfg, config_ifname)
            vpp_encap = self.__get_encapsulation(vpp_iface)
            config_parent_encap = interface.get_encapsulation(self.cfg, config_parent_ifname)
            vpp_parent_encap = self.__get_encapsulation(vpp_parent_iface)
            if config_encap != vpp_encap:
                ## QinX's encapsulation mismatch
                self.logger.info("8> lcp delete %s" % vpp_iface.interface_name)
                continue
            if config_parent_encap != vpp_parent_encap:
                ## QinX's parent encapsulation mismatch
                self.logger.info("9> lcp delete %s" % vpp_iface.interface_name)
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
                continue
            if not 'lcp' in config_iface:
                ## Sub doesn't have an LCP
                self.logger.info("12> lcp delete %s" % vpp_iface.interface_name)
                continue

            phy_lcp = lcps[vpp_iface.sup_sw_if_index]
            config_phy_ifname, config_phy_iface = interface.get_by_lcp_name(self.cfg, phy_lcp.host_if_name)
            if not config_phy_iface:
                ## Sub's phy doesn't exist in the config
                self.logger.info("13> lcp delete %s" % vpp_iface.interface_name)
                continue
            if not 'lcp' in config_phy_iface:
                ## Sub's phy doesn't have an LCP
                self.logger.info("14> lcp delete %s" % vpp_iface.interface_name)
                continue
            if phy_lcp.host_if_name != config_phy_iface['lcp']:
                ## Sub's phy LCP name mismatch
                self.logger.info("15> lcp delete %s" % vpp_iface.interface_name)
                continue

            config_encap = interface.get_encapsulation(self.cfg, config_ifname)
            vpp_encap = self.__get_encapsulation(vpp_iface)
            if config_encap != vpp_encap:
                ## Sub's encapsulation mismatch
                self.logger.info("10> lcp delete %s" % vpp_iface.interface_name)
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
                continue
            if not 'lcp' in config_iface:
                ## Interface doesn't have an LCP
                self.logger.info("22> lcp delete %s" % vpp_iface.interface_name)
                continue
            self.logger.debug("LCP OK: %s -> (vpp=%s, config=%s)" % (lcp.host_if_name, vpp_iface.interface_name, config_ifname))
        return True

    def prune_addresses_set_interface_down(self):
        for ifname in self.vpp.get_qinx_interfaces() + self.vpp.get_dot1x_interfaces() + self.vpp.get_bondethernets() + self.vpp.get_vxlan_tunnels() + self.vpp.get_phys():
            if not ifname in interface.get_interfaces(self.cfg):
                iface = self.vpp.config['interface_names'][ifname]
                if iface.flags & 1: # IF_STATUS_API_FLAG_ADMIN_UP
                    self.logger.info("1> set interface state %s down" % ifname)
                self.prune_addresses(ifname, [])

        return True

    def create(self):
        return False

    def sync(self):
        return False

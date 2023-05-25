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
The functions in this file interact with the VPP API to modify certain
interface metadata.
"""

from .vppapi import VPPApi


class Applier(VPPApi):
    """The methods in the Applier class modify the running state in the VPP dataplane
    and will ensure that the local cache is consistent after creations and
    modifications."""

    # pylint: disable=unnecessary-pass

    def __init__(
        self,
        vpp_api_socket="/run/vpp/api.sock",
        vpp_json_dir=None,
        clientname="vppcfg",
    ):
        VPPApi.__init__(self, vpp_api_socket, vpp_json_dir, clientname)
        self.logger.info("VPP Applier: changing the dataplane is enabled")

    def set_interface_ip_address(self, ifname, address, is_set=True):
        """Add (if_set=True) or remove (if_set=False) an IPv4 or IPv6 address including
        prefixlen (ie 192.0.2.0/24 or 2001:db8::1/64) to an interface given by name
        (ie GigabitEthernet3/0/0)"""
        pass

    def delete_loopback(self, ifname):
        """Delete a loopback identified by name (ie loop0)"""
        pass

    def delete_subinterface(self, ifname):
        """Delete a sub-int identified by name (ie GigabitEthernet3/0/0.100)"""
        pass

    def set_interface_l2_tag_rewrite(
        self, ifname, vtr_op, vtr_push_dot1q, vtr_tag1, vtr_tag2
    ):
        """Set l2 tag rewrite on an interface identified by name (ie GigabitEthernet3/0/0.100)
        into a certain operational mode. TODO(pim) clarify the vtr_* arguments."""
        ## somewhere in interface.api see vtr_* fields
        pass

    def set_interface_l3(self, ifname):
        """Set an interface or sub-interface identified by name (ie GigabitEthernet3/0/0)
        to L3 mode, removing it from bridges and l2xcs"""
        pass

    def delete_bridgedomain(self, bd_id):
        """Delete a bridgedomain given by instance bd_id (ie 100). Cannot delete instance==0."""
        pass

    def delete_tap(self, ifname):
        """Delete a tap identified by name (ie tap100)"""
        pass

    def bond_remove_member(self, bondname, membername):
        """Remove a member interface given by name (ie GigabitEthernet3/0/0) from a bondethernet
        interface given by name (ie BondEthernet0)"""
        pass

    def delete_bond(self, ifname):
        """Delete a bondethernet identified by name (ie BondEthernet0)"""
        pass

    def create_vxlan_tunnel(self, instance, config, is_create=True):
        """'config' is the YAML configuration for the vxlan_tunnels: entry"""
        pass

    def set_interface_link_mtu(self, ifname, link_mtu):
        """Set the max frame size of an interface given by name to the link_mtu value (typically
        1500, 9000, 9216"""

        pass

    def lcp_delete(self, lcpname):
        """Delete a linux control plane interface pair by name (ie 'xe0' or 'be10')"""
        pass

    def set_interface_packet_mtu(self, ifname, packet_mtu):
        """Set the L3 MTU of an interface given by name (ie GigabitEthernet3/0/0)"""
        pass

    def set_interface_state(self, ifname, state):
        """Set the admin link state (True is up, False is down) of an interface given
        by name (ie GigabitEthernet3/0/0)"""
        pass

    def create_loopback_interface(self, instance, config):
        """'config' is the YAML configuration for the loopbacks: entry"""
        pass

    def create_bond(self, instance, config):
        """'config' is the YAML configuration for the bondethernets: entry"""
        pass

    def create_subinterface(self, parent_ifname, sub_id, config):
        """'config' is the YAML configuration for the sub-interfaces: entry"""
        pass

    def create_tap(self, instance, config):
        """'config' is the YAML configuration for the taps: entry"""
        pass

    def create_bridgedomain(self, bd_id, config):
        """'config' is the YAML configuration for the bridgedomains: entry"""
        pass

    def lcp_create(self, ifname, host_if_name):
        """Create a linux control plane interface pair for an interface given by name
        (ie GigabitEthernet3/0/0) under a Linux TAP device name host_if_name (ie e3-0-0)
        """
        pass

    def set_interface_mac(self, ifname, mac):
        """Set the MAC address of interface given by name (ie GigabitEthernet3/0/0), the
        MAC is of form aa:bb:cc:dd:ee:ff"""
        pass

    def bond_add_member(self, bondname, membername):
        """Add a member interface given by name (ie GigabitEthernet3/0/0) to a bondethernet
        given by name (ie BondEthernet0)"""
        pass

    def sync_bridgedomain(self, bd_id, config):
        """'config' is the YAML configuration for the bridgedomains: entry"""
        pass

    def set_interface_l2_bridge_bvi(self, bd_id, ifname):
        """Set a loopback / BVI interface given by name (ie 'loop100') as a BVI of a bridge
        domain identified by bd_id (ie 100)"""
        pass

    def set_interface_l2_bridge(self, bd_id, ifname):
        """Set an interface given by name (ie 'GigabitEthernet3/0/0') into a bridge
        domain identified by bd_id (ie 100)"""
        pass

    def set_interface_l2xc(self, rx_ifname, tx_ifname):
        """Cross connect the rx_ifname (ie GigabitEthernet3/0/0) to emit into the tx_ifname
        (ie GigabitEthernet3/0/1). Note that this operation typically happens twice, once
        for the a->b crossconnect, and again for the b->a crossconnect. Note that
        crossconnecting sub-interfaces requires as well L2 rewriting (pop N for the amount
        of tags on the source interface)"""
        pass

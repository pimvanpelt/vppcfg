"""
The functions in this file interact with the VPP API to modify certain
interface metadata.
"""

from vpp.vppapi import VPPApi


class Applier(VPPApi):
    """The methods in the Applier class modify the running state in the VPP dataplane
    and will ensure that the local cache is consistent after creations and
    modifications."""

    # pylint: disable=unnecessary-pass

    def __init__(self, address="/run/vpp/api.sock", clientname="vppcfg"):
        VPPApi.__init__(self, address, clientname)
        self.logger.info("VPP Applier: changing the dataplane is enabled")

    def set_interface_ip_address(self, ifname, address, is_set=True):
        pass

    def delete_loopback(self, ifname):
        pass

    def delete_subinterface(self, ifname):
        pass

    def set_interface_l2_tag_rewrite(self, ifname, mode):
        ## somewhere in interface.api see vtr_* fields
        pass

    def set_interface_l3(self, ifname):
        pass

    def delete_bridgedomain(self, instance):
        pass

    def delete_tap(self, ifname):
        pass

    def bond_remove_member(self, bondname, membername):
        pass

    def delete_bond(self, ifname):
        pass

    def create_vxlan_tunnel(self, instance, config, is_create=True):
        """'config' is the YAML configuration for the vxlan_tunnels: entry"""
        pass

    def set_interface_link_mtu(self, ifname, link_mtu):
        pass

    def lcp_delete(self, lcpname):
        pass

    def set_interface_packet_mtu(self, ifname, packet_mtu):
        pass

    def set_interface_state(self, ifname, state):
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

    def create_bridgedomain(self, instance, config):
        """'config' is the YAML configuration for the bridgedomains: entry"""
        pass

    def lcp_create(self, ifname, host_if_name):
        pass

    def set_interface_mac(self, ifname, mac):
        pass

    def bond_add_member(self, bondname, membername):
        pass

    def sync_bridgedomain(self, instance, config):
        """'config' is the YAML configuration for the bridgedomains: entry"""
        pass

    def set_interface_l2_bridge_bvi(self, instance, ifname):
        pass

    def set_interface_l2_bridge(self, instance, ifname):
        pass

    def set_interface_l2xc(self, rx_ifname, tx_ifname):
        pass

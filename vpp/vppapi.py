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
interface metadata. Its base class will never change state. See the
derived classes VPPApiDumper() and VPPApiApplier()
"""

import os
import fnmatch
import logging
import socket
from vpp_papi import VPPApiClient


class VPPApi:
    """The VPPApi class is a base class that abstracts the vpp_papi."""

    def __init__(
        self,
        vpp_api_socket="/run/vpp/api.sock",
        vpp_json_dir="/usr/share/vpp/api/",
        clientname="vppcfg",
    ):
        self.logger = logging.getLogger("vppcfg.vppapi")
        self.logger.addHandler(logging.NullHandler())

        if not os.path.exists(vpp_api_socket):
            self.logger.error(f"VPP api socket file not found: {vpp_api_socket}")
        if not os.path.isdir(vpp_json_dir):
            self.logger.error(f"VPP api json directory not found: {vpp_json_dir}")

        self.vpp_api_socket = vpp_api_socket
        self.vpp_json_dir = vpp_json_dir
        self.connected = False
        self.clientname = clientname
        self.vpp = None
        self.cache = self.cache_clear()
        self.cache_read = False
        self.lcp_enabled = False

    def connect(self):
        """Connect to the VPP Dataplane, if we're not already connected"""
        if self.connected:
            return True

        # construct a list of all the json api files
        jsonfiles = []
        for root, _dirnames, filenames in os.walk(self.vpp_json_dir):
            for filename in fnmatch.filter(filenames, "*.api.json"):
                jsonfiles.append(os.path.join(root, filename))

        if not jsonfiles:
            self.logger.error("no json api files found")
            return False

        self.vpp = VPPApiClient(apifiles=jsonfiles, server_address=self.vpp_api_socket)
        try:
            self.logger.debug("Connecting to VPP")
            self.vpp.connect(self.clientname)
        except:
            return False

        # pylint: disable=no-member
        api_response = self.vpp.api.show_version()
        self.logger.info(f"VPP version is {api_response.version}")

        self.connected = True
        return True

    def disconnect(self):
        """Disconnect from the VPP dataplane, if we are still connected."""
        if not self.connected:
            return True
        self.vpp.disconnect()
        self.logger.debug("Disconnected from VPP")
        self.connected = False
        return True

    def cache_clear(self):
        """Remove the cached VPP configuration elements and return an empty dictionary"""
        self.cache_read = False
        return {
            "lcps": {},
            "interface_names": {},
            "interfaces": {},
            "interface_addresses": {},
            "bondethernets": {},
            "bondethernet_members": {},
            "bridgedomains": {},
            "vxlan_tunnels": {},
            "l2xcs": {},
            "taps": {},
        }

    def cache_remove_lcp(self, lcpname):
        """Removes the LCP and TAP interface, identified by lcpname, from the VPP config cache"""
        for _idx, lcp in self.cache["lcps"].items():
            if lcp.host_if_name == lcpname:
                ifname = self.cache["interfaces"][lcp.host_sw_if_index].interface_name
                del self.cache["lcps"][lcp.phy_sw_if_index]
                return self.cache_remove_interface(ifname)
        self.logger.warning(
            f"Trying to remove an LCP which is not in the config: {lcpname}"
        )
        return False

    def cache_remove_bondethernet_member(self, ifname):
        """Removes the bonderthernet member interface, identified by name, from the VPP config cache"""
        if not ifname in self.cache["interface_names"]:
            self.logger.warning(
                f"Trying to remove a bondethernet member interface which is not in the config: {ifname}"
            )
            return False

        iface = self.cache["interface_names"][ifname]
        for bond_idx, members in self.cache["bondethernet_members"].items():
            if iface.sw_if_index in members:
                self.cache["bondethernet_members"][bond_idx].remove(iface.sw_if_index)

        return True

    def cache_remove_l2xc(self, ifname):
        """Remvoes the l2xc from the VPP config cache"""
        if not ifname in self.cache["interface_names"]:
            self.logger.warning(
                f"Trying to remove an L2XC which is not in the config: {ifname}"
            )
            return False
        iface = self.cache["interface_names"][ifname]
        self.cache["l2xcs"].pop(iface.sw_if_index, None)
        return True

    def cache_remove_vxlan_tunnel(self, ifname):
        """Removes a vxlan_tunnel from the VPP config cache"""
        if not ifname in self.cache["interface_names"]:
            self.logger.warning(
                f"Trying to remove a VXLAN Tunnel which is not in the config: {ifname}"
            )
            return False

        iface = self.cache["interface_names"][ifname]
        self.cache["vxlan_tunnels"].pop(iface.sw_if_index, None)
        return True

    def cache_remove_interface(self, ifname):
        """Removes the interface, identified by name, from the VPP config cache"""
        if not ifname in self.cache["interface_names"]:
            self.logger.warning(
                f"Trying to remove an interface which is not in the config: {ifname}"
            )
            return False

        iface = self.cache["interface_names"][ifname]
        del self.cache["interfaces"][iface.sw_if_index]
        if len(self.cache["interface_addresses"][iface.sw_if_index]) > 0:
            self.logger.warning(f"Not all addresses were removed on {ifname}")
        del self.cache["interface_addresses"][iface.sw_if_index]
        del self.cache["interface_names"][ifname]

        ## Use my_dict.pop('key', None), as it allows 'key' to be absent
        if iface.sw_if_index in self.cache["bondethernet_members"]:
            if len(self.cache["bondethernet_members"][iface.sw_if_index]) != 0:
                self.logger.warning(
                    f"When removing BondEthernet {ifname}, its members are not empty: {self.cache['bondethernet_members'][iface.sw_if_index]}"
                )
            else:
                del self.cache["bondethernet_members"][iface.sw_if_index]
        self.cache["bondethernets"].pop(iface.sw_if_index, None)
        self.cache["taps"].pop(iface.sw_if_index, None)
        return True

    def readconfig(self):
        """Read the configuration out of a running VPP Dataplane and put it into a
        VPP config cache"""
        # pylint: disable=no-member
        if not self.connected and not self.connect():
            self.logger.error("Could not connect to VPP")
            return False

        self.cache_read = False

        ## Workaround LCPng and linux-cp, in order.
        self.lcp_enabled = False
        try:
            self.logger.debug("Retrieving LCPs")
            api_response = self.vpp.api.lcp_itf_pair_get()
            if isinstance(api_response, tuple) and api_response[0].retval == 0:
                for lcp in api_response[1]:
                    if lcp.phy_sw_if_index > 65535 or lcp.host_sw_if_index > 65535:
                        ## Work around endianness bug: https://gerrit.fd.io/r/c/vpp/+/35479
                        ## TODO(pim) - remove this when 22.06 ships
                        lcp = lcp._replace(
                            phy_sw_if_index=socket.ntohl(lcp.phy_sw_if_index)
                        )
                        lcp = lcp._replace(
                            host_sw_if_index=socket.ntohl(lcp.host_sw_if_index)
                        )
                        lcp = lcp._replace(vif_index=socket.ntohl(lcp.vif_index))
                        self.logger.warning(
                            f"LCP workaround for endianness issue on {lcp.host_if_name}"
                        )
                    self.cache["lcps"][lcp.phy_sw_if_index] = lcp
                self.lcp_enabled = True
        except:
            self.logger.warning(
                "linux-cp not found, will not reconcile Linux Control Plane"
            )

        self.logger.debug("Retrieving interfaces")
        api_response = self.vpp.api.sw_interface_dump()
        for iface in api_response:
            self.cache["interfaces"][iface.sw_if_index] = iface
            self.cache["interface_names"][iface.interface_name] = iface
            self.cache["interface_addresses"][iface.sw_if_index] = []
            self.logger.debug(f"Retrieving IPv4 addresses for {iface.interface_name}")
            ipr = self.vpp.api.ip_address_dump(
                sw_if_index=iface.sw_if_index, is_ipv6=False
            )
            for addr in ipr:
                self.cache["interface_addresses"][iface.sw_if_index].append(
                    str(addr.prefix)
                )
            self.logger.debug(f"Retrieving IPv6 addresses for {iface.interface_name}")
            ipr = self.vpp.api.ip_address_dump(
                sw_if_index=iface.sw_if_index, is_ipv6=True
            )
            for addr in ipr:
                self.cache["interface_addresses"][iface.sw_if_index].append(
                    str(addr.prefix)
                )

        self.logger.debug("Retrieving bondethernets")
        api_response = self.vpp.api.sw_bond_interface_dump()
        for iface in api_response:
            self.cache["bondethernets"][iface.sw_if_index] = iface
            self.cache["bondethernet_members"][iface.sw_if_index] = []
            for member in self.vpp.api.sw_member_interface_dump(
                sw_if_index=iface.sw_if_index
            ):
                self.cache["bondethernet_members"][iface.sw_if_index].append(
                    member.sw_if_index
                )

        self.logger.debug("Retrieving bridgedomains")
        api_response = self.vpp.api.bridge_domain_dump()
        for bridge in api_response:
            self.cache["bridgedomains"][bridge.bd_id] = bridge

        self.logger.debug("Retrieving vxlan_tunnels")
        api_response = self.vpp.api.vxlan_tunnel_v2_dump()
        for vxlan in api_response:
            self.cache["vxlan_tunnels"][vxlan.sw_if_index] = vxlan

        self.logger.debug("Retrieving L2 Cross Connects")
        api_response = self.vpp.api.l2_xconnect_dump()
        for l2xc in api_response:
            self.cache["l2xcs"][l2xc.rx_sw_if_index] = l2xc

        self.logger.debug("Retrieving TAPs")
        api_response = self.vpp.api.sw_interface_tap_v2_dump()
        for tap in api_response:
            self.cache["taps"][tap.sw_if_index] = tap

        self.cache_read = True
        return self.cache_read

    def phys_exist(self, ifname_list):
        """Return True if all interfaces in the `ifname_list` exist as physical interface names
        in VPP. Return False otherwise."""
        ret = True
        for ifname in ifname_list:
            if not ifname in self.cache["interface_names"]:
                self.logger.warning(f"Interface {ifname} does not exist in VPP")
                ret = False
        return ret

    def get_sub_interfaces(self):
        """Return all interfaces which have a sub-id and one or more tags"""
        subints = [
            self.cache["interfaces"][x].interface_name
            for x in self.cache["interfaces"]
            if self.cache["interfaces"][x].sub_id > 0
            and self.cache["interfaces"][x].sub_number_of_tags > 0
        ]
        return subints

    def get_qinx_interfaces(self):
        """Return all interfaces which have a sub-id and a non-zero inner vlan tag"""
        qinx_subints = [
            self.cache["interfaces"][x].interface_name
            for x in self.cache["interfaces"]
            if self.cache["interfaces"][x].sub_id > 0
            and self.cache["interfaces"][x].sub_inner_vlan_id > 0
        ]
        return qinx_subints

    def get_dot1x_interfaces(self):
        """Return all interfaces which have only an outer vlan tag (dot1q/dot1ad)"""
        dot1x_subints = [
            self.cache["interfaces"][x].interface_name
            for x in self.cache["interfaces"]
            if self.cache["interfaces"][x].sub_id > 0
            and self.cache["interfaces"][x].sub_inner_vlan_id == 0
        ]
        return dot1x_subints

    def get_loopbacks(self):
        """Return all interfaces of VPP type 'Loopback'"""
        loopbacks = [
            self.cache["interfaces"][x].interface_name
            for x in self.cache["interfaces"]
            if self.cache["interfaces"][x].interface_dev_type == "Loopback"
        ]
        return loopbacks

    def get_phys(self):
        """Return all interfaces for which the super interface has the same sw_if_index
        and aren't known to be virtual interfaces"""
        phys = [
            self.cache["interfaces"][x].interface_name
            for x in self.cache["interfaces"]
            if self.cache["interfaces"][x].sw_if_index
            == self.cache["interfaces"][x].sup_sw_if_index
            and self.cache["interfaces"][x].interface_dev_type
            not in ["virtio", "BVI", "Loopback", "VXLAN", "local", "bond"]
        ]
        return phys

    def get_bondethernets(self):
        """Return all bondethernet interfaces"""
        bonds = [
            self.cache["bondethernets"][x].interface_name
            for x in self.cache["bondethernets"]
        ]
        return bonds

    def get_vxlan_tunnels(self):
        """Return all vxlan_tunnel interfaces"""
        vxlan_tunnels = [
            self.cache["interfaces"][x].interface_name
            for x in self.cache["interfaces"]
            if self.cache["interfaces"][x].interface_dev_type in ["VXLAN"]
        ]
        return vxlan_tunnels

    def get_lcp_by_interface(self, sw_if_index):
        """Return the LCP config cache for the interface given by sw_if_index"""
        for _idx, lcp in self.cache["lcps"].items():
            if lcp.phy_sw_if_index == sw_if_index:
                return lcp
        return None

    def tap_is_lcp(self, tap_ifname):
        """Returns True if the given tap_ifname is a TAP interface belonging to an LCP,
        or False otherwise."""
        if not tap_ifname in self.cache["interface_names"]:
            return False

        vpp_iface = self.cache["interface_names"][tap_ifname]
        if not vpp_iface.interface_dev_type == "virtio":
            return False

        for _idx, lcp in self.cache["lcps"].items():
            if vpp_iface.sw_if_index == lcp.host_sw_if_index:
                return True
        return False

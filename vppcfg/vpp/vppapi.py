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
import logging
import time
from vpp_papi import VPPApiClient, VPPApiJSONFiles, MACAddress


class VPPApi:
    """The VPPApi class is a base class that abstracts the vpp_papi."""

    def __init__(
        self,
        vpp_api_socket="/run/vpp/api.sock",
        vpp_json_dir=None,
        clientname="vppcfg",
    ):
        self.logger = logging.getLogger("vppcfg.vppapi")
        self.logger.addHandler(logging.NullHandler())

        self.vpp_api_socket = vpp_api_socket
        self.vpp_json_dir = vpp_json_dir
        self.vpp_jsonfiles = []
        self.vpp_messages = {}
        self.connected = False
        self.clientname = clientname
        self.vpp = None
        self.cache_read = False
        self.cache_clear()
        self.lcp_enabled = False

        if self.vpp_json_dir is None:
            self.vpp_json_dir = VPPApiJSONFiles.find_api_dir([])
        elif not os.path.isdir(self.vpp_json_dir):
            self.logger.error(f"VPP API JSON directory not found: {self.vpp_json_dir}")

        # Construct a list of all the JSON API files
        self.vpp_jsonfiles = VPPApiJSONFiles.find_api_files(api_dir=self.vpp_json_dir)
        if not self.vpp_jsonfiles:
            self.logger.error("No JSON API files found")

        # Enumerate all VPPMessage signatures from the JSON API files, and give their
        # API namedtuple defaults so creating instances can set only those fields which
        # are relevant.
        for json_filename in self.vpp_jsonfiles:
            with open(json_filename, "r", encoding="utf-8") as file_handle:
                for name, msg in VPPApiJSONFiles.process_json_file(file_handle)[
                    0
                ].items():
                    msg.tuple.__new__.__defaults__ = (None,) * len(msg.tuple._fields)
                    self.vpp_messages[name] = msg

    def connect(self, retries=30):
        """Connect to the VPP Dataplane, if we're not already connected"""
        if self.connected:
            return True

        if not os.path.exists(self.vpp_api_socket):
            self.logger.error(f"VPP api socket file not found: {self.vpp_api_socket}")
            return False

        self.vpp = VPPApiClient(
            apifiles=self.vpp_jsonfiles, server_address=self.vpp_api_socket
        )
        self.logger.debug("Connecting to VPP")
        for i in range(retries):
            try:
                self.vpp.connect(self.clientname)
                self.connected = True
                break
            except ConnectionError as err:
                self.logger.warning(
                    f"Could not connect to VPP (attempt {i+1}/{retries}): {err}"
                )
                time.sleep(1)
                self.connected = False
        if not self.connected:
            self.logger.error(f"Could not connect to VPP (tried {retries} times)")
            return False

        # pylint: disable=no-member
        api_response = self.vpp.api.show_version()
        self.logger.info(f"VPP version is {api_response.version}")

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
        """Remove the cached VPP configuration elements and return True"""
        self.cache_read = False
        self.cache = {
            "lcps": {},
            "interface_names": {},
            "interfaces": {},
            "interface_addresses": {},
            "interface_mpls": {},
            "bondethernets": {},
            "bondethernet_members": {},
            "bridgedomains": {},
            "vxlan_tunnels": {},
            "l2xcs": {},
            "taps": {},
        }
        return True

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

        iface = self.get_interface_by_name(ifname)
        if not iface:
            self.logger.warning(
                f"Trying to remove a bondethernet member interface which is not in the config: {ifname}"
            )
            return False

        for bond_idx, members in self.cache["bondethernet_members"].items():
            if iface.sw_if_index in members:
                self.cache["bondethernet_members"][bond_idx].remove(iface.sw_if_index)

        return True

    def cache_remove_l2xc(self, ifname):
        """Remvoes the l2xc from the VPP config cache"""

        iface = self.get_interface_by_name(ifname)
        if not iface:
            self.logger.warning(
                f"Trying to remove an L2XC which is not in the config: {ifname}"
            )
            return False

        self.cache["l2xcs"].pop(iface.sw_if_index, None)
        return True

    def cache_remove_vxlan_tunnel(self, ifname):
        """Removes a vxlan_tunnel from the VPP config cache"""

        iface = self.get_interface_by_name(ifname)
        if not iface:
            self.logger.warning(
                f"Trying to remove a VXLAN Tunnel which is not in the config: {ifname}"
            )
            return False

        self.cache["vxlan_tunnels"].pop(iface.sw_if_index, None)
        return True

    def cache_remove_interface(self, ifname):
        """Removes the interface, identified by name, from the VPP config cache"""

        iface = self.get_interface_by_name(ifname)
        if not iface:
            self.logger.warning(
                f"Trying to remove an interface which is not in the config: {ifname}"
            )
            return False

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

    def mockconfig(self, yaml_config):
        """Mock a minimal configuration cache without talking to a running VPP Dataplane, by
        enumerating the 'interfaces' scope from yaml_config"""

        if not "interfaces" in yaml_config:
            self.logger.error("YAML config does not contain any interfaces")
            return False
        self.logger.debug(f"config: {yaml_config['interfaces']}")

        self.cache_clear()
        ## Add mock local0
        idx = 0
        self.cache["interfaces"][idx] = self.vpp_messages["sw_interface_details"].tuple(
            sw_if_index=idx,
            sup_sw_if_index=idx,
            l2_address=MACAddress("00:00:00:00:00:00"),
            flags=0,
            type=0,
            link_duplex=0,
            link_speed=0,
            sub_id=0,
            sub_number_of_tags=0,
            sub_outer_vlan_id=0,
            sub_inner_vlan_id=0,
            sub_if_flags=0,
            vtr_op=0,
            vtr_push_dot1q=0,
            vtr_tag1=0,
            vtr_tag2=0,
            outer_tag=0,
            link_mtu=0,
            mtu=[0, 0, 0, 0],
            interface_name="local0",
            interface_dev_type="local",
            tag="mock",
        )
        ## Add mock PHYs
        for ifname, iface in yaml_config["interfaces"].items():
            if not "device-type" in iface or iface["device-type"] not in ["dpdk"]:
                continue
            idx += 1
            self.cache["interfaces"][idx] = self.vpp_messages[
                "sw_interface_details"
            ].tuple(
                sw_if_index=idx,
                sup_sw_if_index=idx,
                l2_address=MACAddress("00:00:00:00:00:00"),
                flags=0,
                type=0,
                link_duplex=0,
                link_speed=0,
                sub_id=0,
                sub_number_of_tags=0,
                sub_outer_vlan_id=0,
                sub_inner_vlan_id=0,
                sub_if_flags=0,
                vtr_op=0,
                vtr_push_dot1q=0,
                vtr_tag1=0,
                vtr_tag2=0,
                outer_tag=0,
                link_mtu=64,
                mtu=[64, 0, 0, 0],
                interface_name=ifname,
                interface_dev_type=iface["device-type"],
                tag="mock",
            )

        ## Create interface_names and interface_address indexes
        for idx, iface in self.cache["interfaces"].items():
            self.cache["interface_names"][iface.interface_name] = idx
            self.cache["interface_addresses"][idx] = []

        self.logger.debug(f"cache(mock): {self.cache}")
        return True

    def readconfig(self):
        """Read the configuration out of a running VPP Dataplane and put it into a
        VPP config cache"""
        # pylint: disable=no-member
        if not self.connected and not self.connect():
            self.logger.error("Could not connect to VPP")
            return False

        self.cache_clear()

        self.lcp_enabled = False
        try:
            self.logger.debug("Retrieving LCPs")
            api_response = self.vpp.api.lcp_itf_pair_get()
            if isinstance(api_response, tuple) and api_response[0].retval == 0:
                for lcp in api_response[1]:
                    self.cache["lcps"][lcp.phy_sw_if_index] = lcp
                self.lcp_enabled = True
        except AttributeError as err:
            self.logger.warning(f"LinuxCP API not found - missing plugin: {err}")

        self.logger.debug("Retrieving interfaces")
        api_response = self.vpp.api.sw_interface_dump()
        for iface in api_response:
            self.cache["interfaces"][iface.sw_if_index] = iface
            self.cache["interface_names"][iface.interface_name] = iface.sw_if_index
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

        try:  ## TODO(pim): Remove after 23.10 release
            self.logger.debug("Retrieving interface MPLS state")
            api_response = self.vpp.api.mpls_interface_dump()
            for iface in api_response:
                self.cache["interface_mpls"][iface.sw_if_index] = True
        except AttributeError:
            self.logger.warning(
                f"MPLS state retrieval requires https://gerrit.fd.io/r/c/vpp/+/39022"
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

        try:
            self.logger.debug("Retrieving vxlan_tunnels")
            api_response = self.vpp.api.vxlan_tunnel_v2_dump()
            for vxlan in api_response:
                self.cache["vxlan_tunnels"][vxlan.sw_if_index] = vxlan
        except AttributeError as err:
            self.logger.warning(f"VXLAN API not found - missing plugin: {err}")

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

    def get_interface_by_name(self, name):
        """Return the VPP interface specified by name, or None if it cannot be found"""
        try:
            idx = self.cache["interface_names"][name]
            return self.cache["interfaces"][idx]
        except KeyError:
            pass
        return None

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

        vpp_iface = self.get_interface_by_name(tap_ifname)
        if not vpp_iface or not vpp_iface.interface_dev_type == "virtio":
            return False

        for _idx, lcp in self.cache["lcps"].items():
            if vpp_iface.sw_if_index == lcp.host_sw_if_index:
                return True
        return False

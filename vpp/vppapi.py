'''
The functions in this file interact with the VPP API to retrieve certain
interface metadata.
'''

from vpp_papi import VPPApiClient
import os
import fnmatch
import logging
import socket

class VPPApi():
    def __init__(self, address='/run/vpp/api.sock', clientname='vppcfg'):
        self.logger = logging.getLogger('vppcfg.vppapi')
        self.logger.addHandler(logging.NullHandler())

        self.address = address
        self.connected = False
        self.clientname = clientname
        self.vpp = None
        self.cache = self.cache_clear()
        self.cache_read = False
        self.lcp_enabled = False

    def connect(self):
        if self.connected:
            return True

        vpp_json_dir = '/usr/share/vpp/api/'
        ## vpp_json_dir = "/home/pim/src/vpp/build-root/build-vpp_debug-native/vpp/CMakeFiles/"

        # construct a list of all the json api files
        jsonfiles = []
        for root, dirnames, filenames in os.walk(vpp_json_dir):
            for filename in fnmatch.filter(filenames, '*.api.json'):
                jsonfiles.append(os.path.join(root, filename))

        if not jsonfiles:
            self.logger.error('no json api files found')
            return False

        self.vpp = VPPApiClient(apifiles=jsonfiles,
                                server_address=self.address)
        try:
            self.logger.debug('Connecting to VPP')
            self.vpp.connect(self.clientname)
        except:
            return False

        v = self.vpp.api.show_version()
        self.logger.info('VPP version is %s' % v.version)

        self.connected = True
        return True


    def disconnect(self):
        if not self.connected:
            return True
        self.vpp.disconnect()
        self.logger.debug('Disconnected from VPP')
        self.connected = False
        return True

    def cache_clear(self):
        self.cache_read = False
        return {"lcps": {}, "interface_names": {}, "interfaces": {}, "interface_addresses": {},
                "bondethernets": {}, "bondethernet_members": {},
                "bridgedomains": {}, "vxlan_tunnels": {}, "l2xcs": {}}

    def cache_remove_lcp(self, lcpname):
        """ Removes the LCP and TAP interface, identified by lcpname, from the config. """
        for idx, lcp in self.cache['lcps'].items():
            if lcp.host_if_name == lcpname:
                found = True
                break
        if not found:
            self.logger.warning("Trying to remove an LCP which is not in the config: %s" % lcpname)
            return False

        ifname = self.cache['interfaces'][lcp.host_sw_if_index].interface_name
        del self.cache['interface_names'][ifname]
        del self.cache['interface_addresses'][lcp.host_sw_if_index]
        del self.cache['interfaces'][lcp.host_sw_if_index]
        del self.cache['lcps'][lcp.phy_sw_if_index]
        return True

    def cache_remove_bondethernet_member(self, ifname):
        """ Removes the bonderthernet member interface, identified by name, from the config. """
        if not ifname in self.cache['interface_names']:
            self.logger.warning("Trying to remove a bondethernet member interface which is not in the config: %s" % ifname)
            return False

        iface = self.cache['interface_names'][ifname]
        for bond_idx, members in self.cache['bondethernet_members'].items():
            if iface.sw_if_index in members:
                self.cache['bondethernet_members'][bond_idx].remove(iface.sw_if_index)

        return True

    def cache_remove_l2xc(self, ifname):
        if not ifname in self.cache['interface_names']:
            self.logger.warning("Trying to remove an L2XC which is not in the config: %s" % ifname)
            return False
        iface = self.cache['interface_names'][ifname]
        self.cache['l2xcs'].pop(iface.sw_if_index, None)
        return True

    def cache_remove_vxlan_tunnel(self, ifname):
        if not ifname in self.cache['interface_names']:
            self.logger.warning("Trying to remove a VXLAN Tunnel which is not in the config: %s" % ifname)
            return False

        iface = self.cache['interface_names'][ifname]
        self.cache['vxlan_tunnels'].pop(iface.sw_if_index, None)
        return True

    def cache_remove_interface(self, ifname):
        """ Removes the interface, identified by name, from the config. """
        if not ifname in self.cache['interface_names']:
            self.logger.warning("Trying to remove an interface which is not in the config: %s" % ifname)
            return False

        iface = self.cache['interface_names'][ifname]
        del self.cache['interfaces'][iface.sw_if_index]
        if len(self.cache['interface_addresses'][iface.sw_if_index]) > 0:
            self.logger.warning("Not all addresses were removed on %s" % ifname)
        del self.cache['interface_addresses'][iface.sw_if_index]
        del self.cache['interface_names'][ifname]

        ## Use my_dict.pop('key', None), as it allows 'key' to be absent
        if iface.sw_if_index in self.cache['bondethernet_members']:
            if len(self.cache['bondethernet_members'][iface.sw_if_index]) != 0:
                self.logger.warning("When removing BondEthernet %s, its members are not empty: %s" % (ifname, self.cache['bondethernet_members'][iface.sw_if_index]))
            else:
                del self.cache['bondethernet_members'][iface.sw_if_index]
        self.cache['bondethernets'].pop(iface.sw_if_index, None)
        return True

    def readconfig(self):
        if not self.connected and not self.connect():
            self.logger.error("Could not connect to VPP")
            return False

        self.cache_read = False

        ## Workaround LCPng and linux-cp, in order.
        self.lcp_enabled = False
        if not self.lcp_enabled:
            try:
                self.logger.debug("Retrieving LCPs (lcpng)")
                r = self.vpp.api.lcpng_itf_pair_get()
                if isinstance(r, tuple) and r[0].retval == 0:
                    for lcp in r[1]:
                        self.cache['lcps'][lcp.phy_sw_if_index] = lcp
                self.lcp_enabled = True
            except:
                self.logger.warning("lcpng not found, trying linux-cp")
        if not self.lcp_enabled:
            try:
                self.logger.debug("Retrieving LCPs (linux-cp)")
                r = self.vpp.api.lcp_itf_pair_get()
                if isinstance(r, tuple) and r[0].retval == 0:
                    for lcp in r[1]:
                        self.cache['lcps'][lcp.phy_sw_if_index] = lcp
                self.lcp_enabled = True
            except:
                pass

        if not self.lcp_enabled:
            self.logger.warning("lcpng nor linux-cp found, will not reconcile Linux Control Plane")

        self.logger.debug("Retrieving interfaces")
        r = self.vpp.api.sw_interface_dump()
        for iface in r:
            self.cache['interfaces'][iface.sw_if_index] = iface
            self.cache['interface_names'][iface.interface_name] = iface
            self.cache['interface_addresses'][iface.sw_if_index] = []
            self.logger.debug("Retrieving IPv4 addresses for %s" % iface.interface_name)
            ipr = self.vpp.api.ip_address_dump(sw_if_index=iface.sw_if_index, is_ipv6=False)
            for ip in ipr:
                self.cache['interface_addresses'][iface.sw_if_index].append(str(ip.prefix))
            self.logger.debug("Retrieving IPv6 addresses for %s" % iface.interface_name)
            ipr = self.vpp.api.ip_address_dump(sw_if_index=iface.sw_if_index, is_ipv6=True)
            for ip in ipr:
                self.cache['interface_addresses'][iface.sw_if_index].append(str(ip.prefix))
        
        self.logger.debug("Retrieving bondethernets")
        r = self.vpp.api.sw_bond_interface_dump()
        for iface in r:
            self.cache['bondethernets'][iface.sw_if_index] = iface
            self.cache['bondethernet_members'][iface.sw_if_index] = []
            for member in self.vpp.api.sw_member_interface_dump(sw_if_index=iface.sw_if_index):
                self.cache['bondethernet_members'][iface.sw_if_index].append(member.sw_if_index)
        
        self.logger.debug("Retrieving bridgedomains")
        r = self.vpp.api.bridge_domain_dump()
        for bridge in r:
            self.cache['bridgedomains'][bridge.bd_id] = bridge
        
        self.logger.debug("Retrieving vxlan_tunnels")
        r = self.vpp.api.vxlan_tunnel_v2_dump()
        for vxlan in r:
            self.cache['vxlan_tunnels'][vxlan.sw_if_index] = vxlan
        
        self.logger.debug("Retrieving L2 Cross Connects")
        r = self.vpp.api.l2_xconnect_dump()
        for l2xc in r:
            self.cache['l2xcs'][l2xc.rx_sw_if_index] = l2xc

        self.cache_read = True
        return self.cache_read

    def get_encapsulation(self, iface):
        """ Return a string with the encapsulation of a subint """
        encap = "dot1q"
        if iface.sub_if_flags & 8:
            encap = "dot1ad"
        encap += " %d" % iface.sub_outer_vlan_id
        if iface.sub_inner_vlan_id> 0:
            encap += " inner-dot1q %d" % iface.sub_inner_vlan_id
        if iface.sub_if_flags & 16:
            encap += " exact-match"
        return encap

    def phys_exist(self, ifname_list):
        """ Return True if all interfaces in the `ifname_list` exist as physical interface names
        in VPP. Return False otherwise."""
        ret = True
        for ifname in ifname_list:
            if not ifname in self.cache['interface_names']:
                self.logger.warning("Interface %s does not exist in VPP" % ifname)
                ret = False
        return ret

    def dump(self):
        self.dump_interfaces()
        self.dump_bridgedomains()
        self.dump_phys()
        self.dump_subints()

    def get_sub_interfaces(self):
        subints = [self.cache['interfaces'][x].interface_name for x in self.cache['interfaces'] if self.cache['interfaces'][x].sub_id>0 and self.cache['interfaces'][x].sub_number_of_tags > 0]
        return subints

    def get_qinx_interfaces(self):
        qinx_subints = [self.cache['interfaces'][x].interface_name for x in self.cache['interfaces'] if self.cache['interfaces'][x].sub_id>0 and self.cache['interfaces'][x].sub_inner_vlan_id>0]
        return qinx_subints

    def get_dot1x_interfaces(self):
        dot1x_subints = [self.cache['interfaces'][x].interface_name for x in self.cache['interfaces'] if self.cache['interfaces'][x].sub_id>0 and self.cache['interfaces'][x].sub_inner_vlan_id==0]
        return dot1x_subints

    def get_loopbacks(self):
        loopbacks = [self.cache['interfaces'][x].interface_name for x in self.cache['interfaces'] if self.cache['interfaces'][x].interface_dev_type=='Loopback']
        return loopbacks

    def get_phys(self):
        phys = [self.cache['interfaces'][x].interface_name for x in self.cache['interfaces'] if self.cache['interfaces'][x].sw_if_index == self.cache['interfaces'][x].sup_sw_if_index and self.cache['interfaces'][x].interface_dev_type not in ['virtio', 'BVI', 'Loopback', 'VXLAN', 'local', 'bond']]
        return phys

    def get_bondethernets(self):
        bonds = [self.cache['bondethernets'][x].interface_name for x in self.cache['bondethernets']]
        return bonds

    def get_vxlan_tunnels(self):
        vxlan_tunnels = [self.cache['interfaces'][x].interface_name for x in self.cache['interfaces'] if self.cache['interfaces'][x].interface_dev_type in ['VXLAN']]
        return vxlan_tunnels

    def get_lcp_by_interface(self, sw_if_index):
        for idx, lcp in self.cache['lcps'].items():
            if lcp.phy_sw_if_index == sw_if_index:
                return lcp
        return None

    def dump_phys(self):
        phys = self.get_phys()
        for ifname in phys:
            iface = self.cache['interface_names'][ifname]
            self.logger.info("%s idx=%d" % (iface.interface_name, iface.sw_if_index))

    def dump_subints(self):
        self.logger.info("*** QinX ***")
        subints = self.get_qinx_interfaces()
        for ifname in subints:
            iface = self.cache['interface_names'][ifname]
            self.logger.info("%s idx=%d encap=%s" % (iface.interface_name, iface.sw_if_index, self.get_encapsulation(iface)))
        
        self.logger.info("*** .1q/.1ad ***")
        subints = self.get_dot1x_interfaces()
        for ifname in subints:
            iface = self.cache['interface_names'][ifname]
            self.logger.info("%s idx=%d encap=%s" % (iface.interface_name, iface.sw_if_index, self.get_encapsulation(iface)))

    def dump_bridgedomains(self):
        for bd_id, bridge in self.cache['bridgedomains'].items():
            self.logger.info("BridgeDomain%d" % (bridge.bd_id))
            if bridge.bvi_sw_if_index > 0 and bridge.bvi_sw_if_index < 2**32-1 :
                self.logger.info("  BVI: " + self.cache['interfaces'][bridge.bvi_sw_if_index].interface_name)
        
            members = []
            for member in bridge.sw_if_details:
                members.append(self.cache['interfaces'][member.sw_if_index].interface_name)
            if len(members) > 0:
                self.logger.info("  Members: " + ' '.join(members))
        
    def dump_interfaces(self):
        for idx, iface in self.cache['interfaces'].items():
            self.logger.info("%s idx=%d type=%s mac=%s mtu=%d flags=%d" % (iface.interface_name,
                iface.sw_if_index, iface.interface_dev_type, iface.l2_address,
                iface.mtu[0], iface.flags))
        
            if iface.interface_dev_type=='bond' and iface.sub_id == 0 and iface.sw_if_index in self.cache['bondethernet_members']:
                members = [self.cache['interfaces'][x].interface_name for x in self.cache['bondethernet_members'][iface.sw_if_index]]
                self.logger.info("  Members: %s" % ' '.join(members))
            if iface.interface_dev_type=="VXLAN":
                vxlan = self.cache['vxlan_tunnels'][iface.sw_if_index]
                self.logger.info("  VXLAN: %s:%d -> %s:%d VNI %d" % (vxlan.src_address, vxlan.src_port,
                    vxlan.dst_address, vxlan.dst_port, vxlan.vni))
        
            if iface.sub_id > 0:
                self.logger.info("  Encapsulation: %s" % (self.get_encapsulation(iface)))
        
            if iface.sw_if_index in self.cache['lcps']:
                lcp = self.cache['lcps'][iface.sw_if_index]
                tap_name = self.cache['interfaces'][lcp.host_sw_if_index].interface_name
                tap_idx = lcp.host_sw_if_index
                self.logger.info("  TAP: %s (tap=%s idx=%d)" % (lcp.host_if_name, tap_name, tap_idx))
        
            if len(self.cache['interface_addresses'][iface.sw_if_index])>0:
                self.logger.info("  L3: %s" % ' '.join(self.cache['interface_addresses'][iface.sw_if_index]))
        
            if iface.sw_if_index in self.cache['l2xcs']:
                l2xc = self.cache['l2xcs'][iface.sw_if_index]
                self.logger.info("  L2XC: %s" % self.cache['interfaces'][l2xc.tx_sw_if_index].interface_name)
        
            for bd_id, bridge in self.cache['bridgedomains'].items():
                if bridge.bvi_sw_if_index == iface.sw_if_index:
                    self.logger.info("  BVI: BridgeDomain%d" % (bd_id))
        
            pass

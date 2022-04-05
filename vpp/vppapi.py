'''
The functions in this file interact with the VPP API to retrieve certain
interface metadata.
'''

from vpp_papi import VPPApiClient
import os
import sys
import fnmatch
import logging
import socket
import yaml

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
        try:
            self.logger.debug("Retrieving LCPs")
            r = self.vpp.api.lcp_itf_pair_get()
            if isinstance(r, tuple) and r[0].retval == 0:
                for lcp in r[1]:
                    if lcp.phy_sw_if_index > 65535 or lcp.host_sw_if_index > 65535:
                        ## Work around endianness bug: https://gerrit.fd.io/r/c/vpp/+/35479
                        ## TODO(pim) - remove this when 22.06 ships
                        lcp = lcp._replace(phy_sw_if_index=socket.ntohl(lcp.phy_sw_if_index))
                        lcp = lcp._replace(host_sw_if_index=socket.ntohl(lcp.host_sw_if_index))
                        lcp = lcp._replace(vif_index=socket.ntohl(lcp.vif_index))
                        self.logger.warning("LCP workaround for endianness issue on %s" % lcp.host_if_name)
                    self.cache['lcps'][lcp.phy_sw_if_index] = lcp
                self.lcp_enabled = True
        except:
            self.logger.warning("linux-cp not found, will not reconcile Linux Control Plane")

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

    def phys_exist(self, ifname_list):
        """ Return True if all interfaces in the `ifname_list` exist as physical interface names
        in VPP. Return False otherwise."""
        ret = True
        for ifname in ifname_list:
            if not ifname in self.cache['interface_names']:
                self.logger.warning("Interface %s does not exist in VPP" % ifname)
                ret = False
        return ret

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

class VPPApiDumper(VPPApi):
    def __init__(self, address='/run/vpp/api.sock', clientname='vppcfg'):
        VPPApi.__init__(self, address, clientname)

    def write(self, outfile):
        if outfile and outfile == '-':
            fh = sys.stdout
            outfile = "(stdout)"
        else:
            fh = open(outfile, 'w')

        config = self.cache_to_config()

        print(yaml.dump(config), file=fh)

        if fh is not sys.stdout:
            fh.close()
        self.logger.info("Wrote YAML config to %s" % (outfile))

    def cache_to_config(self):
        config = {"loopbacks": {}, "bondethernets": {}, "interfaces": {}, "bridgedomains": {}, "vxlan_tunnels": {} }
        for idx, iface in self.cache['bondethernets'].items():
            bond = {"description": ""}
            if iface.sw_if_index in self.cache['bondethernet_members']:
                bond['interfaces'] = [self.cache['interfaces'][x].interface_name for x in self.cache['bondethernet_members'][iface.sw_if_index]]
            config['bondethernets'][iface.interface_name] = bond

        for numtags in [ 0, 1, 2 ]:
            for idx, iface in self.cache['interfaces'].items():
                if iface.sub_number_of_tags != numtags:
                    continue

                if iface.interface_dev_type=='Loopback':
                    if iface.sub_id > 0:
                        self.logger.warning("Refusing to export sub-interfaces of loopback devices (%s)" % iface.interface_name)
                        continue
                    loop = {"description": ""}
                    loop['mtu'] = iface.mtu[0]
                    if iface.sw_if_index in self.cache['lcps']:
                        loop['lcp'] = self.cache['lcps'][iface.sw_if_index].host_if_name
                    if iface.sw_if_index in self.cache['interface_addresses']:
                        if len(self.cache['interface_addresses'][iface.sw_if_index]) > 0:
                            loop['addresses'] = self.cache['interface_addresses'][iface.sw_if_index]
                    config['loopbacks'][iface.interface_name] = loop
                elif iface.interface_dev_type in ['bond', 'VXLAN', 'dpdk']:
                    i = {"description": "" }
                    if iface.sw_if_index in self.cache['lcps']:
                        i['lcp'] = self.cache['lcps'][iface.sw_if_index].host_if_name
                    if iface.sw_if_index in self.cache['interface_addresses']:
                        if len(self.cache['interface_addresses'][iface.sw_if_index]) > 0:
                            i['addresses'] = self.cache['interface_addresses'][iface.sw_if_index]
                    if iface.sw_if_index in self.cache['l2xcs']:
                        l2xc = self.cache['l2xcs'][iface.sw_if_index]
                        i['l2xc'] = self.cache['interfaces'][l2xc.tx_sw_if_index].interface_name
                    if not self.cache['interfaces'][idx].flags & 1: # IF_STATUS_API_FLAG_ADMIN_UP
                        i['state'] = 'down'

                    i['mtu'] = iface.mtu[0]
                    if iface.sub_number_of_tags == 0:
                        config['interfaces'][iface.interface_name] = i
                        continue
    
                    encap = {}
                    if iface.sub_if_flags&8:
                        encap['dot1ad'] = iface.sub_outer_vlan_id
                    else:
                        encap['dot1q'] = iface.sub_outer_vlan_id
                    if iface.sub_inner_vlan_id > 0:
                        encap['inner-dot1q'] = iface.sub_inner_vlan_id
                    encap['exact-match'] = bool(iface.sub_if_flags&16)
                    i['encapsulation'] = encap

                    sup_iface = self.cache['interfaces'][iface.sup_sw_if_index]
                    if iface.mtu[0] > 0:
                        i['mtu'] = iface.mtu[0]
                    else:
                        i['mtu'] = sup_iface.mtu[0]
                    if not 'sub-interfaces' in config['interfaces'][sup_iface.interface_name]:
                        config['interfaces'][sup_iface.interface_name]['sub-interfaces'] = {}
                    config['interfaces'][sup_iface.interface_name]['sub-interfaces'][iface.sub_id] = i

        for idx, iface in self.cache['vxlan_tunnels'].items():
            vpp_iface = self.cache['interfaces'][iface.sw_if_index]
            vxlan = { "description": "",
                    "vni": int(iface.vni),
                    "local": str(iface.src_address),
                    "remote": str(iface.dst_address) }
            config['vxlan_tunnels'][vpp_iface.interface_name] = vxlan

        for idx, iface in self.cache['bridgedomains'].items():
            # self.logger.info("%d: %s" % (idx, iface))
            bridge_name = "bd%d" % idx
            mtu = 1500
            bridge = {"description": ""}
            bvi = None
            if iface.bvi_sw_if_index != 2**32-1:
                bvi = self.cache['interfaces'][iface.bvi_sw_if_index]
                mtu = bvi.mtu[0]
                bridge['bvi'] = bvi.interface_name
            members = []
            for member in iface.sw_if_details:
                if bvi and bvi.interface_name == self.cache['interfaces'][member.sw_if_index].interface_name == bvi.interface_name:
                    continue
                members.append(self.cache['interfaces'][member.sw_if_index].interface_name)
                mtu = self.cache['interfaces'][member.sw_if_index].mtu[0]
            if len(members) > 0:
                bridge['interfaces'] = members
            bridge['mtu'] = mtu
            config['bridgedomains'][bridge_name] = bridge

        return config

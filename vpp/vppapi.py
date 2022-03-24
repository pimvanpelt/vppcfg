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
        self.config = self.clearconfig()


    def connect(self):
        if self.connected:
            return True

        vpp_json_dir = '/usr/share/vpp/api/'

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
        self.connected = False
        return True

    def clearconfig(self):
        return {"lcps": {}, "interfaces": {}, "interface_addresses": {}, 
                "bondethernets": {}, "bondethernet_members": {},
                "bridgedomains": {}, "vxlan_tunnels": {}, "l2xcs": {}}

    def readconfig(self):
        if not self.connected and not self.connect():
            self.logger.error("Could not connect to VPP")
            return False

        self.logger.debug("Retrieving LCPs")
        r = self.vpp.api.lcp_itf_pair_get()
        if isinstance(r, tuple) and r[0].retval == 0:
            for lcp in r[1]:
                self.config['lcps'][lcp.phy_sw_if_index] = lcp
        
        self.logger.debug("Retrieving interfaces")
        r = self.vpp.api.sw_interface_dump()
        for iface in r:
            self.config['interfaces'][iface.sw_if_index] = iface
            self.config['interface_addresses'][iface.sw_if_index] = []
            self.logger.debug("Retrieving IPv4 addresses for %s" % iface.interface_name)
            ipr = self.vpp.api.ip_address_dump(sw_if_index=iface.sw_if_index, is_ipv6=False)
            for ip in ipr:
                self.config['interface_addresses'][iface.sw_if_index].append(str(ip.prefix))
            self.logger.debug("Retrieving IPv6 addresses for %s" % iface.interface_name)
            ipr = self.vpp.api.ip_address_dump(sw_if_index=iface.sw_if_index, is_ipv6=True)
            for ip in ipr:
                self.config['interface_addresses'][iface.sw_if_index].append(str(ip.prefix))
        
        self.logger.debug("Retrieving bondethernets")
        r = self.vpp.api.sw_bond_interface_dump()
        for iface in r:
            self.config['bondethernets'][iface.sw_if_index] = iface
            self.config['bondethernet_members'][iface.sw_if_index] = []
            for member in self.vpp.api.sw_member_interface_dump(sw_if_index=iface.sw_if_index):
                self.config['bondethernet_members'][iface.sw_if_index].append(member.sw_if_index)
        
        self.logger.debug("Retrieving bridgedomains")
        r = self.vpp.api.bridge_domain_dump()
        for bridge in r:
            self.config['bridgedomains'][bridge.bd_id] = bridge
        
        self.logger.debug("Retrieving vxlan_tunnels")
        r = self.vpp.api.vxlan_tunnel_v2_dump()
        for vxlan in r:
            self.config['vxlan_tunnels'][vxlan.sw_if_index] = vxlan
        
        self.logger.debug("Retrieving L2 Cross Connects")
        r = self.vpp.api.l2_xconnect_dump()
        for l2xc in r:
            self.config['l2xcs'][l2xc.rx_sw_if_index] = l2xc

        return True

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

    def dump(self):
        self.dump_interfaces()
        self.dump_bridgedomains()
        self.dump_phys()
        self.dump_subints()

    def dump_phys(self):
        phys = [self.config['interfaces'][x].sw_if_index for x in self.config['interfaces'] if self.config['interfaces'][x].interface_dev_type=='dpdk' and self.config['interfaces'][x].sub_id==0]
        for idx in phys:
            iface = self.config['interfaces'][idx]
            self.logger.info("%s idx=%d" % (iface.interface_name, idx))

    def dump_subints(self):
        self.logger.info("*** QinX ***")
        qinx_subints = [self.config['interfaces'][x].sw_if_index for x in self.config['interfaces'] if self.config['interfaces'][x].interface_dev_type in ['dpdk','bond'] and self.config['interfaces'][x].sub_id>0 and self.config['interfaces'][x].sub_inner_vlan_id>0]
        for idx in qinx_subints:
            iface = self.config['interfaces'][idx]
            self.logger.info("%s idx=%d encap=%s" % (iface.interface_name, idx, self.get_encapsulation(iface)))
        
        self.logger.info("*** .1q/.1ad ***")
        subints = [self.config['interfaces'][x].sw_if_index for x in self.config['interfaces'] if self.config['interfaces'][x].interface_dev_type in ['dpdk','bond'] and self.config['interfaces'][x].sub_id>0 and self.config['interfaces'][x].sub_inner_vlan_id==0]
        for idx in subints:
            iface = self.config['interfaces'][idx]
            self.logger.info("%s idx=%d encap=%s" % (iface.interface_name, idx, self.get_encapsulation(iface)))

    def dump_bridgedomains(self):
        for bd_id, bridge in self.config['bridgedomains'].items():
            self.logger.info("BridgeDomain%d" % (bridge.bd_id))
            if bridge.bvi_sw_if_index > 0 and bridge.bvi_sw_if_index < 2**32-1 :
                self.logger.info("  BVI: " + self.config['interfaces'][bridge.bvi_sw_if_index].interface_name)
        
            members = []
            for member in bridge.sw_if_details:
                members.append(self.config['interfaces'][member.sw_if_index].interface_name)
            if len(members) > 0:
                self.logger.info("  Members: " + ' '.join(members))
        
    def dump_interfaces(self):
        for idx, iface in self.config['interfaces'].items():
            self.logger.info("%s idx=%d type=%s mac=%s mtu=%d flags=%d" % (iface.interface_name,
                iface.sw_if_index, iface.interface_dev_type, iface.l2_address,
                iface.mtu[0], iface.flags))
        
            if iface.interface_dev_type=='bond' and iface.sub_id == 0 and iface.sw_if_index in self.config['bondethernet_members']:
                members = [self.config['interfaces'][x].interface_name for x in self.config['bondethernet_members'][iface.sw_if_index]]
                self.logger.info("  Members: %s" % ' '.join(members))
            if iface.interface_dev_type=="VXLAN":
                vxlan = self.config['vxlan_tunnels'][iface.sw_if_index]
                self.logger.info("  VXLAN: %s:%d -> %s:%d VNI %d" % (vxlan.src_address, vxlan.src_port,
                    vxlan.dst_address, vxlan.dst_port, vxlan.vni))
        
            if iface.sub_id > 0:
                self.logger.info("  Encapsulation: %s" % (self.get_encapsulation(iface)))
        
            if iface.sw_if_index in self.config['lcps']:
                lcp = self.config['lcps'][iface.sw_if_index]
                tap_name = self.config['interfaces'][lcp.host_sw_if_index].interface_name
                tap_idx = lcp.host_sw_if_index
                self.logger.info("  TAP: %s (tap=%s idx=%d)" % (lcp.host_if_name, tap_name, tap_idx))
        
            if len(self.config['interface_addresses'][iface.sw_if_index])>0:
                self.logger.info("  L3: %s" % ' '.join(self.config['interface_addresses'][iface.sw_if_index]))
        
            if iface.sw_if_index in self.config['l2xcs']:
                l2xc = self.config['l2xcs'][iface.sw_if_index]
                self.logger.info("  L2XC: %s" % self.config['interfaces'][l2xc.tx_sw_if_index].interface_name)
        
            for bd_id, bridge in self.config['bridgedomains'].items():
                if bridge.bvi_sw_if_index == iface.sw_if_index:
                    self.logger.info("  BVI: BridgeDomain%d" % (bd_id))
        
            pass

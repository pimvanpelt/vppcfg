'''
The functions in this file interact with the VPP API to retrieve certain
interface metadata and write it to a YAML file.
'''

from vpp.vppapi import VPPApi
import sys
import yaml
import config.bondethernet as bondethernet

class Dumper(VPPApi):
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
        self.logger.info(f"Wrote YAML config to {outfile}")

    def cache_to_config(self):
        config = {"loopbacks": {}, "bondethernets": {}, "interfaces": {}, "bridgedomains": {}, "vxlan_tunnels": {}, "taps": {} }
        for idx, bond_iface in self.cache['bondethernets'].items():
            bond = {"description": ""}
            if bond_iface.sw_if_index in self.cache['bondethernet_members']:
                members = [self.cache['interfaces'][x].interface_name for x in self.cache['bondethernet_members'][bond_iface.sw_if_index]]
                if len(members) > 0:
                    bond['interfaces'] = members

            mode = bondethernet.int_to_mode(bond_iface.mode)
            bond['mode'] = mode
            if mode in ['xor', 'lacp']:
                bond['load-balance'] = bondethernet.int_to_lb(bond_iface.lb)
            iface = self.cache['interfaces'][bond_iface.sw_if_index]
            bond['mac'] = str(iface.l2_address)
            config['bondethernets'][iface.interface_name] = bond

        for numtags in [ 0, 1, 2 ]:
            for idx, iface in self.cache['interfaces'].items():
                if iface.sub_number_of_tags != numtags:
                    continue

                if iface.interface_dev_type=='Loopback':
                    if iface.sub_id > 0:
                        self.logger.warning(f"Refusing to export sub-interfaces of loopback devices ({iface.interface_name})")
                        continue
                    loop = {"description": ""}
                    loop['mtu'] = iface.mtu[0]
                    loop['mac'] = str(iface.l2_address)
                    if iface.sw_if_index in self.cache['lcps']:
                        loop['lcp'] = self.cache['lcps'][iface.sw_if_index].host_if_name
                    if iface.sw_if_index in self.cache['interface_addresses']:
                        if len(self.cache['interface_addresses'][iface.sw_if_index]) > 0:
                            loop['addresses'] = self.cache['interface_addresses'][iface.sw_if_index]
                    config['loopbacks'][iface.interface_name] = loop
                elif iface.interface_dev_type in ['bond', 'VXLAN', 'dpdk', 'virtio']:
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

                    if iface.interface_dev_type == 'dpdk' and iface.sub_number_of_tags == 0:
                        i['mac'] = str(iface.l2_address)

                    if self.tap_is_lcp(iface.interface_name):
                        continue

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

        for idx, iface in self.cache['taps'].items():
            vpp_tap = self.cache['taps'][iface.sw_if_index]
            vpp_iface = self.cache['interfaces'][vpp_tap.sw_if_index]
            if self.tap_is_lcp(vpp_iface.interface_name):
                continue

            tap = { "description": "",
                    "tx-ring-size": vpp_tap.tx_ring_sz,
                    "rx-ring-size": vpp_tap.rx_ring_sz,
                    "host": {
                        "mac": str(vpp_tap.host_mac_addr),
                        "name": vpp_tap.host_if_name,
                    } }
            if vpp_tap.host_mtu_size > 0:
                tap['host']['mtu'] = vpp_tap.host_mtu_size
            if vpp_tap.host_namespace:
                tap['host']['namespace'] = vpp_tap.host_namespace
            if vpp_tap.host_bridge:
                tap['host']['bridge'] = vpp_tap.host_bridge
            config['taps'][vpp_iface.interface_name] = tap

        for idx, iface in self.cache['bridgedomains'].items():
            # self.logger.info("%d: %s" % (idx, iface))
            bridge_name = f"bd{int(idx)}"
            mtu = 1500
            bridge = {"description": ""}
            settings = {}
            settings['learn'] = iface.learn
            settings['unicast-flood'] = iface.flood
            settings['unknown-unicast-flood'] = iface.uu_flood
            settings['unicast-forward'] = iface.forward
            settings['arp-termination'] = iface.arp_term
            settings['arp-unicast-forward'] = iface.arp_ufwd
            settings['mac-age-minutes'] = int(iface.mac_age)
            bridge['settings'] = settings

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

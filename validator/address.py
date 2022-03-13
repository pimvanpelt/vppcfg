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
import logging
import validator.interface as interface
import ipaddress

def get_all_addresses_except_ifname(yaml, except_ifname):
    """ Return a list of all ipaddress.ip_interface() instances in the entire config,
        except for those that belong to 'ifname'.
    """
    ret = []
    if 'interfaces' in yaml:
        for ifname, iface in yaml['interfaces'].items():
            if ifname == except_ifname:
                continue

            if 'addresses' in iface:
                for a in iface['addresses']:
                    ret.append(ipaddress.ip_interface(a))
            if 'sub-interfaces' in iface:
                for subid, sub_iface in iface['sub-interfaces'].items():
                    sub_ifname = "%s.%d" % (ifname, subid)
                    if sub_ifname == except_ifname:
                        continue

                    if 'addresses' in sub_iface:
                        for a in sub_iface['addresses']:
                            ret.append(ipaddress.ip_interface(a))
    if 'loopbacks' in yaml:
        for ifname, iface in yaml['loopbacks'].items():
            if ifname == except_ifname:
                continue

            if 'addresses' in iface:
                for a in iface['addresses']:
                    ret.append(ipaddress.ip_interface(a))
    if 'bridgedomains' in yaml:
        for ifname, iface in yaml['bridgedomains'].items():
            if ifname == except_ifname:
                continue

            if 'addresses' in iface:
                for a in iface['addresses']:
                    ret.append(ipaddress.ip_interface(a))

    return ret

def is_allowed(yaml, ifname, iface_addresses, ip_interface):
    """ Returns True if there is at most one occurence of the ip_interface (an IPv4/IPv6 prefix+len)
        in the entire config. That said, we need the 'iface_addresses' because VPP is a bit fickle in
        this regard.

        IP addresses from the same prefix/len can be added to a given interface (ie 192.0.2.1/24 and
        192.0.2.2/24), but other than that, any prefix can not occur as a more-specific or less-specific
        of any other interface.

        So, we will allow:
        - any ip_interface that is of equal network/len of existing one(s) _on the same interface_

        And, we will reject
        - any ip_interface that is a more specific of any existing one
        - any ip_interface that is a less specific of any existing one

        Examples:
        vpp# set interface ip address loop0 192.0.2.1/24
        vpp# set interface ip address loop0 192.0.2.2/24
        vpp# set interface ip address loop0 192.0.2.1/29
        set interface ip address: failed to add 192.0.2.1/29 on loop0 which conflicts with 192.0.2.1/24 for interface loop0
        vpp# set interface ip address loop0 192.0.2.3/23
        set interface ip address: failed to add 192.0.2.3/23 on loop0 which conflicts with 192.0.2.1/24 for interface loop0
    """
    ## print("input: (%s,%s)" % (iface_addresses, ip_interface))
    all_other_addresses = get_all_addresses_except_ifname(yaml, ifname)
    ## print("All IPs: %s" % all_other_addresses)

    my_ip_network = ipaddress.ip_network(ip_interface, strict=False)

    for ipi in all_other_addresses:
        if ipi.version != my_ip_network.version:
            continue

        if ipaddress.ip_network(ipi, strict=False) == my_ip_network:
            ## print("Same: %s == %s" % (ip_interface, ipi))
            return False

        if ipaddress.ip_network(ipi, strict=False).subnet_of(my_ip_network):
            ## print("More: %s == %s" % (ip_interface, ipi))
            return False

        if my_ip_network.subnet_of(ipaddress.ip_network(ipi, strict=False)):
            ## print("Less: %s == %s" % (ip_interface, ipi))
            return False

    for ip in iface_addresses:
        ipi = ipaddress.ip_interface(ip)
        if ipi.version != my_ip_network.version:
            continue

        if ipaddress.ip_network(ipi, strict=False) == my_ip_network:
            ## print("iface same: %s == %s" % (ip_interface, ipi))
            return True

        if ipaddress.ip_network(ipi, strict=False).subnet_of(my_ip_network):
            ## print("iface more: %s == %s" % (ip_interface, ipi))
            return False

        if my_ip_network.subnet_of(ipaddress.ip_network(ipi, strict=False)):
            ## print("iface less: %s == %s" % (ip_interface, ipi))
            return False

    return True
import logging

def is_unique(yaml, lcpname):
    """ Returns True if there is at most one occurence of the LCP name in the entire config."""
    ncount=0
    if 'interfaces' in yaml:
        for ifname, iface in yaml['interfaces'].items():
            if 'lcp' in iface and iface['lcp'] == lcpname:
                ncount = ncount + 1
            if 'sub-interfaces' in iface:
                for sub_ifname, sub_iface in iface['sub-interfaces'].items():
                    if 'lcp' in sub_iface and sub_iface['lcp'] == lcpname:
                        ncount = ncount + 1
    if 'loopbacks' in yaml:
        for ifname, iface in yaml['loopbacks'].items():
            if 'lcp' in iface and iface['lcp'] == lcpname:
                ncount = ncount + 1
    if 'bridgedomains' in yaml:
        for ifname, iface in yaml['bridgedomains'].items():
            if 'lcp' in iface and iface['lcp'] == lcpname:
                ncount = ncount + 1
    if ncount > 1:
        return False
    return True

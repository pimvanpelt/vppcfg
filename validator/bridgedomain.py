import logging
import validator.interface as interface
import validator.lcp as lcp

class NullHandler(logging.Handler):
    def emit(self, record):
        pass


def get_by_name(yaml, ifname):
    """ Return the BridgeDomain by name, if it exists. Return None otherwise. """
    try:
        if ifname in yaml['bridgedomains']:
            return yaml['bridgedomains'][ifname]
    except:
        pass
    return None


def validate_bridgedomains(yaml):
    result = True
    msgs = []
    logger = logging.getLogger('vppcfg.validator')
    logger.addHandler(NullHandler())

    if not 'bridgedomains' in yaml:
        return result, msgs

    logger.debug("Validating bridgedomains...")
    for ifname, iface in yaml['bridgedomains'].items():
        logger.debug("bridgedomain %s" % iface)
        bd_mtu = 1500
        if 'mtu' in iface:
            bd_mtu = iface['mtu']

        if 'addresses' in iface and not 'lcp' in iface:
            msgs.append("bridgedomain %s has an address but no LCP" % ifname)
            result = False
        if 'lcp' in iface and not lcp.is_unique(yaml, iface['lcp']):
            msgs.append("bridgedomain %s does not have a unique LCP name %s" % (ifname, iface['lcp']))
            result = False          

        if 'interfaces' in iface:
            for member in iface['interfaces']:
                member_iface = interface.get_by_name(yaml, member)
                if not member_iface:
                    msgs.append("bridgedomain %s member %s doesn't exist" % (ifname, member))
                    result = False
                    continue

                if interface.has_lcp(yaml, member):
                    msgs.append("bridgedomain %s member %s has an LCP" % (ifname, member))
                    result = False
                if interface.has_address(yaml, member):
                    msgs.append("bridgedomain %s member %s has an address" % (ifname, member))
                    result = False
                member_mtu = interface.get_mtu(yaml, member)
                if member_mtu != bd_mtu:
                    msgs.append("bridgedomain %s member %s has MTU %d, while bridge has %d" % (ifname, member, member_mtu, bd_mtu))
                    result = False


    return result, msgs

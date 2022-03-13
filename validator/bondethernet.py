import logging
import validator.interface as interface

class NullHandler(logging.Handler):
    def emit(self, record):
        pass


def exists(yaml, ifname):
    """ Return True if the BondEthernet exists """
    try:
        if ifname in yaml['bondethernets']:
            return True
    except:
        pass
    return False

def bondethernet(args, yaml):
    result = True
    msgs = []
    logger = logging.getLogger('vppcfg.validator')
    logger.addHandler(NullHandler())

    if not 'bondethernets' in yaml:
        return result, msgs

    for ifname, iface in yaml['bondethernets'].items():
        logger.debug("bondethernet %s: %s" % (ifname, iface))
        for member in iface['interfaces']:
            if not interface.exists(yaml, member):
                msgs.append("bondethernet %s member %s doesn't exist" % (ifname, member))
                result = False

            if interface.has_sub(yaml, member):
                msgs.append("bondethernet %s member %s has sub-interface(s)" % (ifname, member))
                result = False
            if interface.has_lcp(yaml, member):
                msgs.append("bondethernet %s member %s has an LCP" % (ifname, member))
                result = False
            if interface.has_address(yaml, member):
                msgs.append("bondethernet %s member %s has address(es)" % (ifname, member))
                result = False
    return result, msgs

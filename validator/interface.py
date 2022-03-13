import logging
import validator.bondethernet as bondethernet

class NullHandler(logging.Handler):
    def emit(self, record):
        pass

def has_sub(yaml, ifname):
    """ Returns True if this interface has sub-interfaces """
    if not 'interfaces' in yaml:
        return False

    if ifname in yaml['interfaces']:
        iface = yaml['interfaces'][ifname]
        if 'sub-interfaces' in iface and len(iface['sub-interfaces']) > 0:
            return True
    return False

def has_address(yaml, ifname):
    """ Returns True if this interface or sub-interface has one or more addresses"""
    if not 'interfaces' in yaml:
        return False

    if '.' in ifname:
        ifname, subid = ifname.split('.')
        subid = int(subid)
        try:
            if len(yaml['interfaces'][ifname]['sub-interfaces'][subid]['addresses']) > 0:
                return True
        except:
            pass
        return False

    try:
        if len(yaml['interfaces'][ifname]['addresses']) > 0:
            return True
    except:
        pass
    return False

def is_bond_member(yaml, ifname):
    """ Returns True if this interface is a member of a BondEthernet """
    if not 'bondethernets' in yaml:
        return False

    for bond, iface in yaml['bondethernets'].items():
        if not 'interfaces' in iface:
            continue
        if ifname in iface['interfaces']:
            return True
    return False

def has_lcp(yaml, ifname):
    """ Returns True if this interface or sub-interface has an LCP"""
    if not 'interfaces' in yaml:
        return False

    if '.' in ifname:
        ifname, subid = ifname.split('.')
        subid = int(subid)
        try:
            if len(yaml['interfaces'][ifname]['sub-interfaces'][subid]['lcp']) > 0:
                return True
        except:
            pass
        return False

    try:
        if len(yaml['interfaces'][ifname]['lcp']) > 0:
            return True
    except:
        pass
    return False

def exists(yaml, ifname):
    """ Returns true if ifname exists as a phy or sub-int """
    try:
        if ifname in yaml['interfaces']:
            return True
        if '.' in ifname:
            ifname, subid = ifname.split('.')
            subid = int(subid)
            if subid in yaml['interfaces'][ifname]['sub-interfaces']:
                return True
    except:
        pass
    return False

def valid_encapsulation(yaml, sub_ifname):
    try:
        ifname, subid = sub_ifname.split('.')
        subid = int(subid)
        sub_iface = yaml['interfaces'][ifname]['sub-interfaces'][subid]
    except:
        return False

    if not 'encapsulation' in sub_iface:
        return True

    encap = sub_iface['encapsulation']
    if 'dot1ad' in encap and 'dot1q' in encap:
        return False
    if 'inner-dot1q' in encap and not ('dot1ad' in encap or 'dot1q' in encap):
        return False

    return True


def interface(args, yaml):
    result = True
    msgs = []
    logger = logging.getLogger('vppcfg.validator')
    logger.addHandler(NullHandler())

    if not 'interfaces' in yaml:
        return result, msgs

    for ifname, iface in yaml['interfaces'].items():
        logger.debug("interface %s" % iface)
        if ifname.startswith("BondEthernet") and not bondethernet.exists(yaml, ifname):
            msgs.append("interface %s does not exist in bondethernets" % ifname)
            result = False

        iface_lcp = has_lcp(yaml, ifname)
        iface_address = has_address(yaml, ifname)

        if iface_address and not iface_lcp:
            msgs.append("interface %s has adddress(es) but no LCP" % ifname)
            result = False

        if has_sub(yaml, ifname):
            for sub_id, sub_iface in yaml['interfaces'][ifname]['sub-interfaces'].items():
                sub_ifname = "%s.%d" % (ifname, sub_id)
                logger.debug("sub-interface %s" % sub_iface)
                if has_lcp(yaml, sub_ifname):
                    if not iface_lcp:
                        msgs.append("sub-interface %s has LCP but %s does not have LCP" % (sub_ifname, ifname))
                        result = False
                if has_address(yaml, sub_ifname):
                    ## The sub_iface lcp is not required: it can be derived from the iface_lcp, which has to be set
                    if not iface_lcp:
                        msgs.append("sub-interface %s has address(es) but %s does not have LCP" % (sub_ifname, ifname))
                        result = False
                if not valid_encapsulation(yaml, sub_ifname):
                    msgs.append("sub-interface %s has invalid encapsulation" % (sub_ifname))
                    result = False

    return result, msgs

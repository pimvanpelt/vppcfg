import logging
import validator.bondethernet as bondethernet

class NullHandler(logging.Handler):
    def emit(self, record):
        pass

def get_parent_by_name(yaml, ifname):
    """ Returns the sub-interface's parent, or None if the sub-int doesn't exist. """
    if not '.' in ifname:
        return None
    ifname, subid = ifname.split('.')
    subid = int(subid)
    try:
        iface = yaml['interfaces'][ifname]
        return iface
    except:
        pass
    return None

def get_by_name(yaml, ifname):
    """ Returns the interface or sub-interface by a given name, or None if it does not exist """
    if '.' in ifname:
        ifname, subid = ifname.split('.')
        subid = int(subid)
        try:
            iface = yaml['interfaces'][ifname]['sub-interfaces'][subid]
            return iface
        except:
            return None

    try:
        iface = yaml['interfaces'][ifname]
        return iface
    except:
        pass
    return None


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

def unique_lcp(yaml, ifname):
    """ Returns true if this interface has a unique LCP name """
    if not 'interfaces' in yaml:
        return True
    iface = get_by_name(yaml, ifname)
    lcp = get_lcp(yaml, ifname)
    if not lcp:
        return True

    ncount = 0
    for sibling_ifname, sibling_iface in yaml['interfaces'].items():
        sibling_lcp = get_lcp(yaml, sibling_ifname)
        if sibling_lcp == lcp and sibling_ifname != ifname:
            ## print("%s overlaps with %s: %s" % (ifname, sibling_ifname, lcp))
            ncount = ncount + 1
    if ncount == 0:
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


def unique_encapsulation(yaml, sub_ifname):
    """ Ensures that for the sub_ifname specified, there exist no other sub-ints on the
    parent with the same encapsulation. """
    iface = get_by_name(yaml, sub_ifname)
    parent_iface = get_parent_by_name(yaml, sub_ifname)
    if not iface or not parent_iface:
        return False
    parent_ifname, subid = sub_ifname.split('.')

    dot1q = 0
    dot1ad = 0
    inner_dot1q = 0
    if not 'encapsulation' in iface:
        dot1q = int(subid)
    else:
        if 'dot1q' in iface['encapsulation']:
            dot1q = iface['encapsulation']['dot1q']
        elif 'dot1ad' in iface['encapsulation']:
            dot1ad = iface['encapsulation']['dot1ad']
        if 'inner-dot1q' in iface['encapsulation']:
            inner_dot1q = iface['encapsulation']['inner-dot1q']

    ncount = 0
    for subid, sibling_iface in parent_iface['sub-interfaces'].items():
        sibling_dot1q = 0
        sibling_dot1ad = 0
        sibling_inner_dot1q = 0
        sibling_ifname = "%s.%d" % (parent_ifname, subid)
        if not 'encapsulation' in sibling_iface:
            sibling_dot1q = subid
        else:
            if 'dot1q' in sibling_iface['encapsulation']:
                sibling_dot1q = sibling_iface['encapsulation']['dot1q']
            elif 'dot1ad' in sibling_iface['encapsulation']:
                sibling_dot1ad = sibling_iface['encapsulation']['dot1ad']
            if 'inner-dot1q' in sibling_iface['encapsulation']:
                sibling_inner_dot1q = sibling_iface['encapsulation']['inner-dot1q']
        if (dot1q,dot1ad,inner_dot1q) == (sibling_dot1q, sibling_dot1ad, sibling_inner_dot1q) and sub_ifname != sibling_ifname:
            ## print("%s overlaps with %s: [%d,%d,%d]" % (sub_ifname, sibling_ifname, dot1q, dot1ad, inner_dot1q))
            ncount = ncount + 1

    if (ncount == 0):
        return True
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
    if 'exact-match' in encap and encap['exact-match'] == False and is_l3(yaml, sub_ifname):
        return False

    return True


def is_l3(yaml, ifname):
    """ Returns True if the interface exists and has either an LCP or an address """
    iface = get_by_name(yaml, ifname)
    if not iface:
        return False
    if has_lcp(yaml, ifname):
        return True
    if has_address(yaml, ifname):
        return True
    return False

def get_lcp(yaml, ifname):
    """ Returns the LCP of the interface. If the interface is a sub-interface with L3
    enabled, synthesize it based on its parent, using smart QinQ syntax.
    Return None if no LCP can be found. """

    iface = get_by_name(yaml, ifname)
    parent_iface = get_parent_by_name(yaml, ifname)
    if 'lcp' in iface:
        return iface['lcp']
    if not is_l3(yaml, ifname):
        return None
    if parent_iface and not 'lcp' in parent_iface:
        return None
    if not 'encapsulation' in iface:
        if not '.' in ifname:
            ## Not a sub-int and no encap? Should not happen
            return None
        ifname, subid = ifname.split('.')
        subid = int(subid)
        return "%s.%d" % (parent_iface['lcp'], subid)

    dot1q = 0
    dot1ad = 0
    inner_dot1q = 0
    if 'dot1q' in iface['encapsulation']:
        dot1q = iface['encapsulation']['dot1q']
    elif 'dot1ad' in iface['encapsulation']:
        dot1ad = iface['encapsulation']['dot1ad']
    if 'inner-dot1q' in iface['encapsulation']:
        inner_dot1q = iface['encapsulation']['inner-dot1q']
    if inner_dot1q and dot1ad:
        lcp = "%s.%d.%d" % (parent_iface['lcp'], dot1ad, inner_dot1q)
    elif inner_dot1q and dot1q:
        lcp = "%s.%d.%d" % (parent_iface['lcp'], dot1q, inner_dot1q)
    elif dot1ad:
        lcp = "%s.%d" % (parent_iface['lcp'], dot1ad)
    elif dot1q:
        lcp = "%s.%d" % (parent_iface['lcp'], dot1q)
    else:
        return None
    return lcp

def get_mtu(yaml, ifname):
    """ Returns MTU of the interface. If it's not set, return the parent's MTU, and
    return 1500 if no MTU was set on the sub-int or the parent."""
    iface = get_by_name(yaml, ifname)
    parent_iface = get_parent_by_name(yaml, ifname)

    try:
        return iface['mtu']
        return parent_iface['mtu']
    except:
        pass
    return 1500


def validate_interfaces(yaml):
    result = True
    msgs = []
    logger = logging.getLogger('vppcfg.validator')
    logger.addHandler(NullHandler())

    if not 'interfaces' in yaml:
        return result, msgs

    for ifname, iface in yaml['interfaces'].items():
        logger.debug("interface %s" % iface)
        if ifname.startswith("BondEthernet") and not bondethernet.get_by_name(yaml, ifname):
            msgs.append("interface %s does not exist in bondethernets" % ifname)
            result = False

        iface_mtu = get_mtu(yaml, ifname)
        iface_lcp = has_lcp(yaml, ifname)
        iface_address = has_address(yaml, ifname)

        if iface_address and not iface_lcp:
            msgs.append("interface %s has an address but no LCP" % ifname)
            result = False
        if iface_lcp and not unique_lcp(yaml, ifname):
            lcp = get_lcp(yaml, ifname)
            msgs.append("interface %s does not have a unique LCP name %s" % (ifname, lcp))
            result = False

        if has_sub(yaml, ifname):
            for sub_id, sub_iface in yaml['interfaces'][ifname]['sub-interfaces'].items():
                logger.debug("sub-interface %s" % sub_iface)
                sub_ifname = "%s.%d" % (ifname, sub_id)
                if not sub_iface:
                    msgs.append("sub-interface %s has no config" % (sub_ifname))
                    result = False
                    continue

                sub_lcp = get_lcp(yaml, sub_ifname)
                if sub_lcp and len(sub_lcp)>15:
                    msgs.append("sub-interface %s has LCP with too long name '%s'" % (sub_ifname, sub_lcp))
                    result = False
                sub_mtu = get_mtu(yaml, sub_ifname)
                if sub_mtu > iface_mtu:
                    msgs.append("sub-interface %s has MTU %d higher than parent MTU %d" % (sub_ifname, sub_iface['mtu'], iface_mtu))
                    result = False
                if has_lcp(yaml, sub_ifname):
                    if not iface_lcp:
                        msgs.append("sub-interface %s has LCP but %s does not have LCP" % (sub_ifname, ifname))
                        result = False
                if has_address(yaml, sub_ifname):
                    ## The sub_iface lcp is not required: it can be derived from the iface_lcp, which has to be set
                    if not iface_lcp:
                        msgs.append("sub-interface %s has an address but %s does not have LCP" % (sub_ifname, ifname))
                        result = False
                if not valid_encapsulation(yaml, sub_ifname):
                    msgs.append("sub-interface %s has invalid encapsulation" % (sub_ifname))
                    result = False
                elif not unique_encapsulation(yaml, sub_ifname):
                    msgs.append("sub-interface %s doesn't have unique encapsulation" % (sub_ifname))
                    result = False

    return result, msgs

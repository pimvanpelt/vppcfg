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
import validator.bondethernet as bondethernet
import validator.bridgedomain as bridgedomain
import validator.lcp as lcp
import validator.address as address

class NullHandler(logging.Handler):
    def emit(self, record):
        pass

def get_qinx_parent_by_name(yaml, ifname):
    """ Returns the sub-interface which matches a QinAD or QinQ outer tag, or None,None
        if that sub-interface doesn't exist. """

    if not is_qinx(yaml, ifname):
        return None, None
    qinx_ifname, qinx_iface = get_by_name(yaml, ifname)
    if not qinx_iface:
        return None,None

    qinx_encap = get_encapsulation(yaml, ifname)
    if not qinx_encap:
        return None,None

    parent_ifname, parent_iface = get_parent_by_name(yaml, ifname)
    if not parent_iface:
        return None,None

    for subid, sub_iface in parent_iface['sub-interfaces'].items():
        sub_ifname = "%s.%d" % (parent_ifname, subid)
        sub_encap = get_encapsulation(yaml, sub_ifname)
        if not sub_encap:
            continue
        if qinx_encap['dot1q'] > 0 and sub_encap['dot1q'] == qinx_encap['dot1q']:
            return sub_ifname, sub_iface
        if qinx_encap['dot1ad'] > 0 and sub_encap['dot1ad'] == qinx_encap['dot1ad']:
            return sub_ifname, sub_iface
    return None,None


def get_parent_by_name(yaml, ifname):
    """ Returns the sub-interface's parent, or None,None if the sub-int doesn't exist. """
    if not '.' in ifname:
        return None, None
    try:
        parent_ifname, subid = ifname.split('.')
        subid = int(subid)
        iface = yaml['interfaces'][parent_ifname]
        return parent_ifname, iface
    except:
        pass
    return None,None


def get_by_name(yaml, ifname):
    """ Returns the interface or sub-interface by a given name, or None,None if it does not exist """
    if '.' in ifname:
        try:
            phy_ifname, subid = ifname.split('.')
            subid = int(subid)
            iface = yaml['interfaces'][phy_ifname]['sub-interfaces'][subid]
            return ifname, iface
        except:
            return None, None

    try:
        iface = yaml['interfaces'][ifname]
        return ifname, iface
    except:
        pass
    return None, None


def is_sub(yaml, ifname):
    """ Returns True if this interface is a sub-interface """
    parent_ifname, parent_iface = get_parent_by_name(yaml, ifname)
    return isinstance(parent_iface, dict)


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

    ifname, iface = get_by_name(yaml, ifname)
    if not iface:
        return False
    return 'addresses' in iface


def get_l2xc_interfaces(yaml):
    """ Returns a list of all interfaces that have an L2 CrossConnect """
    ret = []
    if not 'interfaces' in yaml:
        return ret
    for ifname, iface in yaml['interfaces'].items():
        if 'l2xc' in iface:
            ret.append(ifname)
        if 'sub-interfaces' in iface:
            for subid, sub_iface in iface['sub-interfaces'].items():
                sub_ifname = "%s.%d" % (ifname, subid)
                if 'l2xc' in sub_iface:
                    ret.append(sub_ifname)

    return ret


def is_l2xc_interface(yaml, ifname):
    """ Returns True if this interface has an L2 CrossConnect """

    return ifname in get_l2xc_interfaces(yaml)


def get_l2xc_target_interfaces(yaml):
    """ Returns a list of all interfaces that are the target of an L2 CrossConnect """
    ret = []
    if 'interfaces' in yaml:
        for ifname, iface in yaml['interfaces'].items():
            if 'l2xc' in iface:
                ret.append(iface['l2xc'])
            if 'sub-interfaces' in iface:
                for subid, sub_iface in iface['sub-interfaces'].items():
                    if 'l2xc' in sub_iface:
                        ret.append(sub_iface['l2xc'])

    return ret


def is_l2xc_target_interface(yaml, ifname):
    """ Returns True if this interface is the target of an L2 CrossConnect """

    return ifname in get_l2xc_target_interfaces(yaml)


def is_l2xc_target_interface_unique(yaml, ifname):
    """ Returns True if this interface is referenced as an l2xc target zero or one times """

    ifs = get_l2xc_target_interfaces(yaml)
    return ifs.count(ifname) < 2


def has_lcp(yaml, ifname):
    """ Returns True if this interface or sub-interface has an LCP """

    ifname, iface = get_by_name(yaml, ifname)
    if not iface:
        return False
    return 'lcp' in iface


def valid_encapsulation(yaml, ifname):
    """ Returns True if the sub interface has a valid encapsulation, or
        none at all """
    ifname, iface = get_by_name(yaml, ifname)
    if not iface:
        return True
    if not 'encapsulation' in iface:
        return True

    encap = iface['encapsulation']
    if 'dot1ad' in encap and 'dot1q' in encap:
        return False
    if 'inner-dot1q' in encap and not ('dot1ad' in encap or 'dot1q' in encap):
        return False
    if 'exact-match' in encap and encap['exact-match'] == False and has_lcp(yaml, ifname):
        return False

    return True


def get_encapsulation(yaml, ifname):
    """ Returns the encapsulation of an interface name as a fully formed dictionary:

        dot1q: int (default 0)
        dot1ad: int (default 0)
        inner-dot1q: int (default 0)
        exact-match: bool (default False)

        If the interface is not a sub-int with valid encapsulation, None is returned.
    """
    if not valid_encapsulation(yaml, ifname):
        return None

    ifname, iface = get_by_name(yaml, ifname)
    if not iface:
        return None

    parent_ifname, parent_iface = get_parent_by_name(yaml, ifname)
    if not iface or not parent_iface:
        return None
    parent_ifname, subid = ifname.split('.')

    dot1q = 0
    dot1ad = 0
    inner_dot1q = 0
    exact_match = False
    if not 'encapsulation' in iface:
        dot1q = int(subid)
    else:
        if 'dot1q' in iface['encapsulation']:
            dot1q = iface['encapsulation']['dot1q']
        elif 'dot1ad' in iface['encapsulation']:
            dot1ad = iface['encapsulation']['dot1ad']
        if 'inner-dot1q' in iface['encapsulation']:
            inner_dot1q = iface['encapsulation']['inner-dot1q']
        if 'exact-match' in iface['encapsulation']:
            exact_match = iface['encapsulation']['exact-match']

    return {
      "dot1q": int(dot1q),
      "dot1ad": int(dot1ad),
      "inner-dot1q": int(inner_dot1q),
      "exact-match": bool(exact_match)
      }


def get_interfaces(yaml):
    """ Return a list of all interface and sub-interface names """
    ret = []
    if not 'interfaces' in yaml:
        return ret
    for ifname, iface in yaml['interfaces'].items():
        ret.append(ifname)
        if not 'sub-interfaces' in iface:
            continue
        for subid, sub_iface in iface['sub-interfaces'].items():
            ret.append("%s.%d" % (ifname, subid))
    return ret


def get_sub_interfaces(yaml):
    """ Return all interfaces which are a subinterface. """
    ret = []
    for ifname in get_interfaces(yaml):
        if is_sub(yaml, ifname):
            ret.append(ifname)
    return ret

def get_qinx_interfaces(yaml):
    """ Return all interfaces which are double-tagged, either QinAD or QinQ.
        These interfaces will always have a valid encapsulation with 'inner-dot1q'
        set to non-zero.

        Note: this is always a strict subset of get_sub_interfaces()
    """
    ret = []
    for ifname in get_interfaces(yaml):
        if not is_sub(yaml, ifname):
            continue
        encap = get_encapsulation(yaml, ifname)
        if not encap:
            continue
        if encap['inner-dot1q'] > 0:
            ret.append(ifname)
    return ret


def is_qinx(yaml, ifname):
    """ Returns True if the interface is a double-tagged (QinQ or QinAD) interface """
    return ifname in get_qinx_interfaces(yaml)


def unique_encapsulation(yaml, sub_ifname):
    """ Ensures that for the sub_ifname specified, there exist no other sub-ints on the
    parent with the same encapsulation. """
    new_ifname, iface = get_by_name(yaml, sub_ifname)
    parent_ifname, parent_iface = get_parent_by_name(yaml, new_ifname)
    if not iface or not parent_iface:
        return False

    sub_encap = get_encapsulation(yaml, new_ifname)
    if not sub_encap:
        return False

    ncount = 0
    for subid, sibling_iface in parent_iface['sub-interfaces'].items():
        sibling_ifname = "%s.%d" % (parent_ifname, subid)
        sibling_encap = get_encapsulation(yaml, sibling_ifname)
        if sub_encap == sibling_encap and new_ifname != sibling_ifname:
            ## print("%s overlaps with %s" % (sub_encap, sibling_encap))
            ncount = ncount + 1

    return ncount == 0


def is_l2(yaml, ifname):
    """ Returns True if the interface is an L2XC source, L2XC target or a member of a bridgedomain """
    if bridgedomain.is_bridge_interface(yaml, ifname):
        return True
    if is_l2xc_interface(yaml, ifname):
        return True
    if is_l2xc_target_interface(yaml, ifname):
        return True
    return False


def is_l3(yaml, ifname):
    """ Returns True if the interface exists and is neither l2xc target nor bridgedomain """
    return not is_l2(yaml, ifname)


def get_lcp(yaml, ifname):
    """ Returns the LCP of the interface. If the interface is a sub-interface with L3
    enabled, synthesize it based on its parent, using smart QinQ syntax.
    Return None if no LCP can be found. """

    ifname, iface = get_by_name(yaml, ifname)
    if iface and 'lcp' in iface:
        return iface['lcp']
    return None

def get_mtu(yaml, ifname):
    """ Returns MTU of the interface. If it's not set, return the parent's MTU, and
    return 1500 if no MTU was set on the sub-int or the parent."""
    ifname, iface = get_by_name(yaml, ifname)
    if not iface:
        return 1500

    parent_ifname, parent_iface = get_parent_by_name(yaml, ifname)

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
        if ifname.startswith("BondEthernet") and (None,None) == bondethernet.get_by_name(yaml, ifname):
            msgs.append("interface %s does not exist in bondethernets" % ifname)
            result = False

        iface_mtu = get_mtu(yaml, ifname)
        iface_lcp = get_lcp(yaml, ifname)
        iface_address = has_address(yaml, ifname)

        if iface_address and not iface_lcp:
            msgs.append("interface %s has an address but no LCP" % ifname)
            result = False
        if is_l2(yaml, ifname) and iface_lcp:
            msgs.append("interface %s is in L2 mode but has LCP name %s" % (ifname, iface_lcp))
            result = False
        if is_l2(yaml, ifname) and iface_address:
            msgs.append("interface %s is in L2 mode but has an address" % ifname)
            result = False
        if iface_lcp and not lcp.is_unique(yaml, iface_lcp):
            msgs.append("interface %s does not have a unique LCP name %s" % (ifname, iface_lcp))
            result = False

        if 'addresses' in iface:
            for a in iface['addresses']:
                if not address.is_allowed(yaml, ifname, iface['addresses'], a):
                    msgs.append("interface %s IP address %s conflicts with another" % (ifname, a))
                    result = False

        if 'l2xc' in iface:
            if has_sub(yaml, ifname):
                msgs.append("interface %s has l2xc so it cannot have sub-interfaces" % (ifname))
                result = False
            if iface_lcp:
                msgs.append("interface %s has l2xc so it cannot have an LCP" % (ifname))
                result = False
            if iface_address:
                msgs.append("interface %s has l2xc so it cannot have an address" % (ifname))
                result = False
            if (None,None) == get_by_name(yaml, iface['l2xc']):
                msgs.append("interface %s l2xc target %s does not exist" % (ifname, iface['l2xc']))
                result = False
            if iface['l2xc'] == ifname:
                msgs.append("interface %s l2xc target cannot be itself" % (ifname))
                result = False
            target_mtu = get_mtu(yaml, iface['l2xc'])
            if target_mtu != iface_mtu:
                msgs.append("interface %s l2xc target MTU %d does not match source MTU %d" % (ifname, target_mtu, iface_mtu))
                result = False
            if not is_l2xc_target_interface_unique(yaml, iface['l2xc']):
                msgs.append("interface %s l2xc target %s is not unique" % (ifname, iface['l2xc']))
                result = False
            if bridgedomain.is_bridge_interface(yaml, iface['l2xc']):
                msgs.append("interface %s l2xc target %s is in a bridgedomain" % (ifname, iface['l2xc']))
                result = False
            if has_lcp(yaml, iface['l2xc']):
                msgs.append("interface %s l2xc target %s cannot have an LCP" % (ifname, iface['l2xc']))
                result = False
            if has_address(yaml, iface['l2xc']):
                msgs.append("interface %s l2xc target %s cannot have an address" % (ifname, iface['l2xc']))
                result = False

        if has_sub(yaml, ifname):
            for sub_id, sub_iface in yaml['interfaces'][ifname]['sub-interfaces'].items():
                logger.debug("sub-interface %s" % sub_iface)
                sub_ifname = "%s.%d" % (ifname, sub_id)
                if not sub_iface:
                    msgs.append("sub-interface %s has no config" % (sub_ifname))
                    result = False
                    continue

                sub_mtu = get_mtu(yaml, sub_ifname)
                if sub_mtu > iface_mtu:
                    msgs.append("sub-interface %s has MTU %d higher than parent MTU %d" % (sub_ifname, sub_iface['mtu'], iface_mtu))
                    result = False

                sub_lcp = get_lcp(yaml, sub_ifname)
                if sub_lcp and not lcp.is_unique(yaml, sub_lcp):
                    msgs.append("sub-interface %s does not have a unique LCP name %s" % (sub_ifname, sub_lcp))
                    result = False
                if sub_lcp and not iface_lcp:
                    msgs.append("sub-interface %s has LCP name %s but %s does not have LCP" % (sub_ifname, sub_lcp, ifname))
                    result = False
                if sub_lcp and is_qinx(yaml, sub_ifname):
                    mid_ifname, mid_iface = get_qinx_parent_by_name(yaml, sub_ifname)
                    if not mid_iface:
                        msgs.append("sub-interface %s is QinX and has LCP name %s which requires a parent" % (sub_ifname, sub_lcp))
                        result = False
                    elif not get_lcp(yaml, mid_ifname):
                        msgs.append("sub-interface %s is QinX and has LCP name %s but %s does not have LCP" % (sub_ifname, sub_lcp, mid_ifname))
                        result = False
                if sub_lcp and 'encapsulation' in sub_iface and 'exact-match' in sub_iface['encapsulation'] and not sub_iface['encapsulation']['exact-match']:
                    msgs.append("sub-interface %s has LCP name %s but its encapsulation is not exact-match" % (sub_ifname, sub_lcp))
                    result = False


                if has_address(yaml, sub_ifname):
                    ## The sub_iface lcp is not required: it can be derived from the iface_lcp, which has to be set
                    if not iface_lcp:
                        msgs.append("sub-interface %s has an address but %s does not have LCP" % (sub_ifname, ifname))
                        result = False
                    for a in sub_iface['addresses']:
                        if not address.is_allowed(yaml, sub_ifname, sub_iface['addresses'], a):
                            msgs.append("sub-interface %s IP address %s conflicts with another" % (sub_ifname, a))
                            result = False
                if not valid_encapsulation(yaml, sub_ifname):
                    msgs.append("sub-interface %s has invalid encapsulation" % (sub_ifname))
                    result = False
                elif not unique_encapsulation(yaml, sub_ifname):
                    msgs.append("sub-interface %s does not have unique encapsulation" % (sub_ifname))
                    result = False
                if 'l2xc' in sub_iface:
                    if has_lcp(yaml, sub_ifname):
                        msgs.append("sub-interface %s has l2xc so it cannot have an LCP" % (sub_ifname))
                        result = False
                    if has_address(yaml, sub_ifname):
                        msgs.append("sub-interface %s has l2xc so it cannot have an address" % (sub_ifname))
                        result = False
                    if (None, None) == get_by_name(yaml, sub_iface['l2xc']):
                        msgs.append("sub-interface %s l2xc target %s does not exist" % (sub_ifname, sub_iface['l2xc']))
                        result = False
                    if sub_iface['l2xc'] == sub_ifname:
                        msgs.append("sub-interface %s l2xc target cannot be itself" % (sub_ifname))
                        result = False
                    target_mtu = get_mtu(yaml, sub_iface['l2xc'])
                    if target_mtu != sub_mtu:
                        msgs.append("sub-interface %s l2xc target MTU %d does not match source MTU %d" % (ifname, target_mtu, sub_mtu))
                        result = False
                    if not is_l2xc_target_interface_unique(yaml, sub_iface['l2xc']):
                        msgs.append("sub-interface %s l2xc target %s is not unique" % (sub_ifname, sub_iface['l2xc']))
                        result = False
                    if bridgedomain.is_bridge_interface(yaml, sub_iface['l2xc']):
                        msgs.append("sub-interface %s l2xc target %s is in a bridgedomain" % (sub_ifname, sub_iface['l2xc']))
                        result = False
                    if has_lcp(yaml, sub_iface['l2xc']):
                        msgs.append("sub-interface %s l2xc target %s cannot have an LCP" % (sub_ifname, sub_iface['l2xc']))
                        result = False
                    if has_address(yaml, sub_iface['l2xc']):
                        msgs.append("sub-interface %s l2xc target %s cannot have an address" % (sub_ifname, sub_iface['l2xc']))
                        result = False


    return result, msgs

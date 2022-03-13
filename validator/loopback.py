import logging

class NullHandler(logging.Handler):
    def emit(self, record):
        pass

def exists(yaml, ifname):
    """ Returns true if ifname exists as a loopback """
    try:
        if ifname in yaml['loopbacks']:
            return True
    except:
        pass
    return False


def loopback(args, yaml):
    result = True
    msgs = []
    logger = logging.getLogger('vppcfg.validator')
    logger.addHandler(NullHandler())

    if not 'loopbacks' in yaml:
        return result, msgs

    logger.debug("Validating loopbacks...")
    for ifname, iface in yaml['loopbacks'].items():
        logger.debug("loopback %s" % iface)
    return result, msgs

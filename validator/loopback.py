import logging

class NullHandler(logging.Handler):
    def emit(self, record):
        pass

def get_by_name(yaml, ifname):
    """ Return the loopback by name, if it exists. Return None otherwise. """
    try:
        if ifname in yaml['loopbacks']:
            return yaml['loopbacks'][ifname]
    except:
        pass
    return None


def validate_loopbacks(yaml):
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

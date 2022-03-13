import logging

class NullHandler(logging.Handler):
    def emit(self, record):
        pass


def loopback(args, yaml):
    result = True
    msgs = []
    logger = logging.getLogger('vppcfg.validator')
    logger.addHandler(NullHandler())

    logger.debug("Validating loopbacks...")
    return result, msgs

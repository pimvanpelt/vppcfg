import logging

class NullHandler(logging.Handler):
    def emit(self, record):
        pass


def bridgedomain(args, yaml):
    result = True
    msgs = []
    logger = logging.getLogger('vppcfg.validator')
    logger.addHandler(NullHandler())

    logger.debug("Validating bridgedomains...")
    return result, msgs

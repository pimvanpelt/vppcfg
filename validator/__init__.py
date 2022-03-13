#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import (
    absolute_import,
    division,
    print_function,
)

import logging
try:
    import yamale
except ImportError:
    print("ERROR: install yamale manually: sudo pip install yamale")
    sys.exit(-2)
from validator.loopback import loopback
from validator.bondethernet import bondethernet
from validator.interface import interface
from validator.bridgedomain import bridgedomain

class NullHandler(logging.Handler):
    def emit(self, record):
        pass


class Validator(object):
    def __init__(self, args):
        self.logger = logging.getLogger('vppcfg.validator')
        self.logger.addHandler(NullHandler())

        self.args = args

    def validate(self, yaml):
        ret_rv = True
        ret_msgs = []
        if self.args.schema:
            try:
                self.logger.info("Validating against schema %s" % self.args.schema)
                schema = yamale.make_schema(self.args.schema)
                data = yamale.make_data(content=str(yaml))
                yamale.validate(schema, data)
                self.logger.debug("Schema correctly validated by yamale")
            except ValueError as e:
                ret_rv = False
                for result in e.results:
                    for error in result.errors:
                        ret_msgs.extend(['yamale: %s' % error])
                return ret_rv, ret_msgs
        else:
            self.logger.warning("Schema validation disabled")

        self.logger.debug("Validating Semantics...")

        rv, msgs = bondethernet(self.args, yaml)
        if msgs:
            ret_msgs.extend(msgs)
        if not rv:
            ret_rv = False

        rv, msgs = interface(self.args, yaml)
        if msgs:
            ret_msgs.extend(msgs)
        if not rv:
            ret_rv = False

        rv, msgs = loopback(self.args, yaml)
        if msgs:
            ret_msgs.extend(msgs)
        if not rv:
            ret_rv = False

        rv, msgs = bridgedomain(self.args, yaml)
        if msgs:
            ret_msgs.extend(msgs)
        if not rv:
            ret_rv = False

        return ret_rv, ret_msgs

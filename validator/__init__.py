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
from validator.loopback import validate_loopbacks
from validator.bondethernet import validate_bondethernets
from validator.interface import validate_interfaces
from validator.bridgedomain import validate_bridgedomains

from yamale.validators import DefaultValidators, Validator
import ipaddress

class IPInterfaceWithPrefixLength(Validator):
    """ Custom IPAddress validator - takes IP/prefixlen as input:
        192.0.2.1/29 or 2001:db8::1/64 are correct. The PrefixLength
        is required, and must be a number (0-32 for IPv4 and 0-128 for
        IPv6).
    """
    tag = 'ip_interface'

    def _is_valid(self, value):
        try:
            network = ipaddress.ip_interface(value)
        except:
            return False
        if not '/' in value:
            return False
        e = value.split('/')
        if not len(e) == 2:
            return False
        if not e[1].isnumeric():
            return False
        return True



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
                validators = DefaultValidators.copy()
                validators[IPInterfaceWithPrefixLength.tag] = IPInterfaceWithPrefixLength
                schema = yamale.make_schema(self.args.schema, validators=validators)
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

        rv, msgs = validate_bondethernets(self.args, yaml)
        if msgs:
            ret_msgs.extend(msgs)
        if not rv:
            ret_rv = False

        rv, msgs = validate_interfaces(self.args, yaml)
        if msgs:
            ret_msgs.extend(msgs)
        if not rv:
            ret_rv = False

        rv, msgs = validate_loopbacks(self.args, yaml)
        if msgs:
            ret_msgs.extend(msgs)
        if not rv:
            ret_rv = False

        rv, msgs = validate_bridgedomains(self.args, yaml)
        if msgs:
            ret_msgs.extend(msgs)
        if not rv:
            ret_rv = False

        return ret_rv, ret_msgs

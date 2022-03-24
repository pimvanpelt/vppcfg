#!/usr/bin/env python
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
from config.loopback import validate_loopbacks
from config.bondethernet import validate_bondethernets
from config.interface import validate_interfaces
from config.bridgedomain import validate_bridgedomains
from config.vxlan_tunnel import validate_vxlan_tunnels

from yamale.validators import DefaultValidators, Validator
import ipaddress

class IPInterfaceWithPrefixLength(Validator):
    """ Custom IPAddress config - takes IP/prefixlen as input:
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
        if not isinstance(value, str):
            return False
        if not '/' in value:
            return False
        e = value.split('/')
        if not len(e) == 2:
            return False
        if not e[1].isnumeric():
            return False
        return True



class Validator(object):
    def __init__(self, schema):
        self.logger = logging.getLogger('vppcfg.config')
        self.logger.addHandler(logging.NullHandler())

        self.schema = schema

    def validate(self, yaml):
        ret_rv = True
        ret_msgs = []
        if not yaml:
            return ret_rv, ret_msgs

        if self.schema:
            try:
                self.logger.debug("Validating against schema %s" % self.schema)
                validators = DefaultValidators.copy()
                validators[IPInterfaceWithPrefixLength.tag] = IPInterfaceWithPrefixLength
                schema = yamale.make_schema(self.schema, validators=validators)
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

        rv, msgs = validate_bondethernets(yaml)
        if msgs:
            ret_msgs.extend(msgs)
        if not rv:
            ret_rv = False

        rv, msgs = validate_interfaces(yaml)
        if msgs:
            ret_msgs.extend(msgs)
        if not rv:
            ret_rv = False

        rv, msgs = validate_loopbacks(yaml)
        if msgs:
            ret_msgs.extend(msgs)
        if not rv:
            ret_rv = False

        rv, msgs = validate_bridgedomains(yaml)
        if msgs:
            ret_msgs.extend(msgs)
        if not rv:
            ret_rv = False

        rv, msgs = validate_vxlan_tunnels(yaml)
        if msgs:
            ret_msgs.extend(msgs)
        if not rv:
            ret_rv = False

        if ret_rv:
            self.logger.debug("Semantics correctly validated")
        return ret_rv, ret_msgs

    def valid_config(self, yaml):
        """ Validate the given YAML configuration in 'yaml' against syntax
        validation given in the yamale 'schema', and all semantic configs.

        Returns True if the configuration is valid, False otherwise.
        """

        rv, msgs = self.validate(yaml)
        if not rv:
            for m in msgs:
                self.logger.error(m)
            return False

        self.logger.info("Configuration validated successfully")
        return True

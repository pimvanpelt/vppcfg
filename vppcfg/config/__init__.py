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
""" A vppcfg configuration module that exposes its semantic/syntax validators """
from __future__ import (
    absolute_import,
    division,
    print_function,
)

import logging
import ipaddress
import os.path
import sys

try:
    import yamale
except ImportError:
    print("ERROR: install yamale manually: sudo pip install yamale")
    sys.exit(-2)
from yamale import validators

from .loopback import validate_loopbacks
from .bondethernet import validate_bondethernets
from .interface import validate_interfaces
from .bridgedomain import validate_bridgedomains
from .vxlan_tunnel import validate_vxlan_tunnels
from .tap import validate_taps
from .prefixlist import validate_prefixlists
from .acl import validate_acls


class IPInterfaceWithPrefixLength(validators.Validator):
    """Custom IPAddress config - takes IP/prefixlen as input:
    192.0.2.1/29 or 2001:db8::1/64 are correct. The PrefixLength
    is required, and must be a number (0-32 for IPv4 and 0-128 for
    IPv6).
    """

    tag = "ip_interface"

    def _is_valid(self, value):
        try:
            _network = ipaddress.ip_interface(value)
        except ValueError:
            return False
        if not isinstance(value, str):
            return False
        if not "/" in value:
            return False
        elems = value.split("/")
        if not len(elems) == 2:
            return False
        if not elems[1].isnumeric():
            return False
        return True


class Validator:
    """The Validator class takes a schema filename (which may be None, in which
    case a built-in default is used), and a given YAML file represented as a string,
    and holds it against syntax and semantic validators, returning a tuple of (bool,list)
    where the boolean signals success/failure, and the list of strings are messages
    that were added when validating the YAML config.

    The purpose is to  ensure that the YAML file is both syntactically correct,
    which is ensured by Yamale, and semantically correct, which is ensured by a set
    of built-in validators, and user-added validators (see the add_validator() method).
    """

    def __init__(self, schema):
        self.logger = logging.getLogger("vppcfg.config")
        self.logger.addHandler(logging.NullHandler())

        self.schema = schema
        self.validators = [
            validate_bondethernets,
            validate_interfaces,
            validate_loopbacks,
            validate_bridgedomains,
            validate_vxlan_tunnels,
            validate_taps,
            validate_prefixlists,
            validate_acls,
        ]

    def validate(self, yaml):
        """Validate the semantics of all YAML maps, by calling self.validators in turn,
        and then optionally calling validators that were added with add_validator()"""
        ret_retval = True
        ret_msgs = []
        if not yaml:
            return ret_retval, ret_msgs

        _validators = validators.DefaultValidators.copy()
        _validators[IPInterfaceWithPrefixLength.tag] = IPInterfaceWithPrefixLength
        if self.schema:
            fname = self.schema
            self.logger.debug(f"Validating against --schema {fname}")
        else:
            ## See setup.py data files that includes schema.yaml into the bundle
            self.logger.debug("Validating against built-in schema")
            fname = os.path.abspath(
                os.path.join(os.path.dirname(__file__), "..", "schema.yaml")
            )

        if not os.path.isfile(fname):
            self.logger.error(f"Cannot file schema file: {fname}")
            return False, ret_msgs

        try:
            schema = yamale.make_schema(fname, validators=_validators)
            data = yamale.make_data(content=str(yaml))
            yamale.validate(schema, data)
            self.logger.debug("Schema correctly validated by yamale")
        except yamale.YamaleError as err:
            ret_retval = False
            for result in err.results:
                for error in result.errors:
                    ret_msgs.extend([f"yamale: {error}"])
            return ret_retval, ret_msgs

        self.logger.debug("Validating Semantics...")

        for validator in self.validators:
            retval, msgs = validator(yaml)
            if msgs:
                ret_msgs.extend(msgs)
            if not retval:
                ret_retval = False

        if ret_retval:
            self.logger.debug("Semantics correctly validated")
        return ret_retval, ret_msgs

    def valid_config(self, yaml):
        """Validate the given YAML configuration in 'yaml' against syntax
        validation given in the yamale 'schema', and all semantic configs.

        Returns True if the configuration is valid, False otherwise.
        """

        retval, msgs = self.validate(yaml)
        if not retval:
            for msg in msgs:
                self.logger.error(msg)
            return False

        self.logger.info("Configuration validated successfully")
        return True

    def add_validator(self, func):
        """Add a validator function, which strictly takes the prototype
           rv, msgs = func(yaml)
        returning a Boolean success value in rv and a List of strings
        in msgs. The function will be passed the configuration YAML and
        gets to opine if it's valid or not.

        Note: will only be called iff Yamale syntax-check succeeded,
              and it will be called after all built-in validators.
        """
        self.validators.append(func)

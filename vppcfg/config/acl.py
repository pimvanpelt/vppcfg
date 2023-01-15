#
# Copyright (c) 2023 Pim van Pelt
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
""" A vppcfg configuration module that validates acls """
import logging


def get_aclx(yaml):
    """Return a list of all acls."""
    ret = []
    if "acls" in yaml:
        for aclname, _acl in yaml["acls"].items():
            ret.append(aclname)
    return ret


def get_by_name(yaml, aclname):
    """Return the acl by name, if it exists. Return None otherwise."""
    try:
        if aclname in yaml["acls"]:
            return aclname, yaml["acls"][aclname]
    except KeyError:
        pass
    return None, None


def validate_acls(yaml):
    """Validate the semantics of all YAML 'acls' entries"""
    result = True
    msgs = []
    logger = logging.getLogger("vppcfg.config")
    logger.addHandler(logging.NullHandler())

    if not "acls" in yaml:
        return result, msgs

    for aclname, acl in yaml["acls"].items():
        logger.debug(f"acl {acl}")
        terms = 0
        for acl_term in acl["terms"]:
            terms += 1
            if "family" in acl_term and "any" in acl_term["family"]:
                if "source" in acl_term:
                    msgs.append(f"acl term {terms} family any cannot have source")
                    result = False
                if "destination" in acl_term:
                    msgs.append(f"acl term {terms} family any cannot have destination")
                    result = False

    return result, msgs

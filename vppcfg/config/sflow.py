#
# Copyright (c) 2024 Pim van Pelt
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
""" A vppcfg configuration module that validates sflow config """
import logging


def validate_sflow(yaml):
    """Validate the semantics of all YAML 'sflow' config entries"""
    result = True
    msgs = []
    logger = logging.getLogger("vppcfg.config")
    logger.addHandler(logging.NullHandler())

    if not "sflow" in yaml:
        return result, msgs

    ## NOTE(pim): Nothing to validate. sflow config values are all
    ##            integers and enforced by yamale.
    return result, msgs

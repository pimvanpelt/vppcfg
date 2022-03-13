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
import logging
import validator.interface as interface

class NullHandler(logging.Handler):
    def emit(self, record):
        pass


def get_by_name(yaml, ifname):
    """ Return the BondEthernet by name, if it exists. Return None otherwise. """
    try:
        if ifname in yaml['bondethernets']:
            return yaml['bondethernets'][ifname]
    except:
        pass
    return None


def validate_bondethernets(yaml):
    result = True
    msgs = []
    logger = logging.getLogger('vppcfg.validator')
    logger.addHandler(NullHandler())

    if not 'bondethernets' in yaml:
        return result, msgs

    for ifname, iface in yaml['bondethernets'].items():
        logger.debug("bondethernet %s: %s" % (ifname, iface))
        for member in iface['interfaces']:
            if not interface.get_by_name(yaml, member):
                msgs.append("bondethernet %s member %s doesn't exist" % (ifname, member))
                result = False

            if interface.has_sub(yaml, member):
                msgs.append("bondethernet %s member %s has sub-interface(s)" % (ifname, member))
                result = False
            if interface.has_lcp(yaml, member):
                msgs.append("bondethernet %s member %s has an LCP" % (ifname, member))
                result = False
            if interface.has_address(yaml, member):
                msgs.append("bondethernet %s member %s has an address" % (ifname, member))
                result = False
    return result, msgs

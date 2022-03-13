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
import validator.lcp as lcp
import validator.address as address

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
        if 'addresses' in iface and not 'lcp' in iface:
            msgs.append("loopback %s has an address but no LCP" % ifname)
            result = False
        if 'lcp' in iface and not lcp.is_unique(yaml, iface['lcp']):
            msgs.append("loopback %s does not have a unique LCP name %s" % (ifname, iface['lcp']))
            result = False
        if 'addresses' in iface:
            for a in iface['addresses']:
                if not address.is_allowed(yaml, ifname, iface['addresses'], a):
                    msgs.append("loopback %s IP address %s is not allowed" % (ifname, a))
                    result = False

    return result, msgs

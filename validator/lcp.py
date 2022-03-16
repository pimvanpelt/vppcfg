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

def is_unique(yaml, lcpname):
    """ Returns True if there is at most one occurence of the LCP name in the entire config."""
    ncount=0
    if 'interfaces' in yaml:
        for ifname, iface in yaml['interfaces'].items():
            if 'lcp' in iface and iface['lcp'] == lcpname:
                ncount = ncount + 1
            if 'sub-interfaces' in iface:
                for sub_ifname, sub_iface in iface['sub-interfaces'].items():
                    if 'lcp' in sub_iface and sub_iface['lcp'] == lcpname:
                        ncount = ncount + 1
    if 'loopbacks' in yaml:
        for ifname, iface in yaml['loopbacks'].items():
            if 'lcp' in iface and iface['lcp'] == lcpname:
                ncount = ncount + 1
    if 'bridgedomains' in yaml:
        for ifname, iface in yaml['bridgedomains'].items():
            if 'lcp' in iface and iface['lcp'] == lcpname:
                ncount = ncount + 1
    return ncount < 2
